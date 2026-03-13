import re
import os
from tools import copy_files, list_directory, read_file, open_file, start_share, stop_share, check_share_status
from openai import OpenAI
from app_config import AppConfig, load_config, save_config

class Agent:
    def __init__(self):
        self.tools = {
            "copy": copy_files,
            "list": list_directory,
            "read": read_file,
            "open": open_file,
            "start_share": start_share,
            "stop_share": stop_share,
            "check_share_status": check_share_status
        }
        
        self.load_config()

    def load_config(self):
        cfg = load_config()
        self.config = cfg
        self.api_key = cfg.api_key
        self.base_url = cfg.base_url
        self.model = cfg.model
        self.share_dir = cfg.share_dir

        self._init_client()

    def _init_client(self):
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            print(f"Agent Client Re-initialized: URL={self.base_url}, Model={self.model}")

    def update_config(self, api_key, base_url, model, share_dir=None):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        if isinstance(share_dir, str):
            self.share_dir = share_dir.strip()

        cfg = AppConfig(
            api_key=self.api_key or "",
            base_url=self.base_url or "",
            model=self.model or "gpt-3.5-turbo",
            share_dir=(self.share_dir or "").replace("\\", "/"),
        )
        save_config(cfg)
        self.config = cfg
            
        self._init_client()
        return True

    def process_message(self, message: str, mode: str = "smart") -> tuple[str, str | None]:
        """
        Process the user message and return a response and an optional action link.
        """
        print(f"Processing message in {mode} mode: {message}")
        
        # If mode is explicitly regex/standard, skip LLM
        if mode == "regex":
             return self._process_with_regex(message, fallback_mode=False)

        # 1. Try LLM first if available and not in regex mode
        if self.client:
            try:
                return self._process_with_llm(message)
            except Exception as e:
                print(f"LLM Error: {e}. Falling back to regex.")
                # Return the specific error to the user instead of generic fallback message
                # This helps debugging why LLM failed despite having a key
                # But we still try regex just in case it matches perfectly
                regex_result = self._process_with_regex(message, fallback_mode=True)
                if regex_result[0].startswith("抱歉，我没有理解"):
                     return f"智能识别遇到错误: {str(e)}\n\n同时也无法通过标准指令格式识别。请检查后台日志或 API 配置。", None
                return regex_result
        
        # 2. Fallback to Regex (Legacy Logic)
        return self._process_with_regex(message, fallback_mode=False)

    def _process_with_llm(self, message: str) -> tuple[str, str | None]:
        """
        Use LLM to extract intent and parameters.
        """
        
        system_prompt = """
        You are an intelligent file management assistant. Your goal is to understand the user's intent and extract parameters for file operations.
        
        Available Tools:
        1. copy_files(source_dir, dest_dir, pattern)
           - Copies files matching a pattern from source to destination.
           - pattern defaults to "*" if not specified. If user mentions "tables" or "excel", pattern should be "tables".
        
        2. list_directory(path)
           - Lists files and directories in the given path.
           - Use this when user asks to "show", "list", "view", or "check" directory contents.

        3. read_file(path)
           - Reads the content of a file (txt, md, py, docx, etc.).
           - Use this when user asks to "read", "cat", or "show content".
           
        4. open_file(path)
           - Launches the file with the system default application (e.g., .bat, .exe, .pdf, .mp4, or any file user wants to "open" or "run").
           - Use this when user asks to "open", "launch", "run" a file.

        5. start_share()
           - Starts a local LAN file sharing service.
           - Use this when user asks to "start share", "begin sharing", "share files", "开始共享".
           - No arguments required.
           
        6. stop_share()
           - Stops the local LAN file sharing service.
           - Use this when user asks to "stop share", "end sharing", "stop service", "停止共享".
           - No arguments required.

        Output Format:
        You must return ONLY a raw JSON object (no markdown, no ```json blocks).
        {
            "tool": "copy" | "list" | "read" | "open" | "start_share" | "stop_share" | "unknown",
            "args": {
                "source_dir": "path",
                "dest_dir": "path",
                "pattern": "optional_pattern",
                "path": "path_for_list_or_read_or_open"
            },
            "reply": "A friendly confirmation message to the user describing what you are about to do."
        }
        
        Path Normalization Rules:
        - "D盘" -> "D:/"
        - "里" -> "/"
        - "路径" -> ""
        - ALWAYS use forward slashes "/" for paths in JSON arguments. Do NOT use backslashes "\\".
        - Example: "D盘里Note" -> "D:/Note"
        - Example: "D:\\Note" -> "D:/Note"
        
        If the intent is unclear, set "tool" to "unknown" and ask for clarification in "reply".
        If the user asks to list/show files in a drive like "D:", interpret it as "D:/".
        """
        
        try:
            print(f"Agent processing message: {message}") # Debug log
            
            # Minimax compatibility check: some models/versions don't support response_format="json_object"
            # Or they might return Markdown code blocks even when asked for JSON
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                # response_format={"type": "json_object"}, # Commented out to improve compatibility with some Minimax models
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            print(f"LLM Raw Output: {content}") # Debug log

            # Clean up content if it contains markdown code blocks
            if content.startswith("```"):
                # Remove first line (```json or ```)
                content = content.split("\n", 1)[1]
                # Remove last line (```)
                if content.endswith("```"):
                    content = content.rsplit("\n", 1)[0]
            
            content = content.strip()
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to find JSON object within the text if parsing failed
                # Improved logic: Find the LAST valid JSON object in the text.
                # This handles cases where LLM outputs thoughts or multiple JSONs.
                # We search backwards from the last '}' to find a matching '{'.
                
                valid_json_found = False
                # Find all closing braces
                closing_braces = [m.start() for m in re.finditer(r"\}", content)]
                
                # Iterate backwards from the last closing brace
                for end_idx in reversed(closing_braces):
                    # For this closing brace, find all preceding opening braces
                    opening_braces = [m.start() for m in re.finditer(r"\{", content[:end_idx])]
                    
                    # Iterate backwards through opening braces to find the smallest valid JSON
                    # Actually, we want the largest valid JSON ending at end_idx? 
                    # No, usually the JSON is a single block. Let's try matching braces.
                    
                    for start_idx in reversed(opening_braces):
                        candidate = content[start_idx : end_idx + 1]
                        try:
                            parsed = json.loads(candidate)
                            # Check if it looks like our command object
                            if "tool" in parsed:
                                data = parsed
                                valid_json_found = True
                                break
                        except json.JSONDecodeError:
                            continue
                    
                    if valid_json_found:
                        break
                
                if not valid_json_found:
                     print(f"FAILED to parse JSON from content: {content}") # Debug log
                     raise ValueError(f"Could not parse JSON from LLM response (nested error): {content}")
            
            print(f"Parsed JSON Data: {data}") # Debug log
            
            tool_name = data.get("tool")
            args = data.get("args", {})
            reply = data.get("reply")
            
            if tool_name == "copy":
                result = self.tools["copy"](
                    source_dir=args.get("source_dir"), 
                    dest_dir=args.get("dest_dir"), 
                    pattern=args.get("pattern", "*")
                )
                return f"{reply}\n\n执行结果: {result}", f"file:///{args.get('dest_dir').replace(os.sep, '/')}"
            
            elif tool_name == "list":
                path = args.get("path")
                # Handle cases where LLM might put path in source_dir or dest_dir by mistake
                if not path and args.get("source_dir"):
                     path = args.get("source_dir")
                
                if not os.path.exists(path):
                    return f"未找到该目录: {path}", None

                result = self.tools["list"](path)
                return f"{reply}\n\n{result}", f"file:///{path.replace(os.sep, '/')}"

            elif tool_name == "read":
                path = args.get("path")
                # Handle cases where LLM might put path in source_dir or dest_dir by mistake
                if not path and args.get("source_dir"):
                     path = args.get("source_dir")
                
                if not path:
                    return "Error: Could not determine file path from request.", None

                # Normalize path separators
                path = path.replace("\\", "/")
                
                if not os.path.exists(path):
                    return f"未找到该文件: {path}", None

                result = self.tools["read"](path)
                print(f"DEBUG: read tool result length: {len(result)}") # Debug log
                
                # Combine reply and result
                final_response = f"{reply}\n\n{result}"
                return final_response, f"file:///{path.replace(os.sep, '/')}"

            elif tool_name == "open":
                path = args.get("path")
                if not path and args.get("source_dir"):
                     path = args.get("source_dir")
                
                if not path:
                    return "Error: Could not determine file path from request.", None

                if not os.path.exists(path):
                    return f"未找到该文件: {path}", None

                result = self.tools["open"](path)
                # For open, we might not need to return a file link, but maybe the directory
                return f"{reply}\n\n{result}", None

            elif tool_name == "start_share":
                result = self.tools["start_share"]()
                return f"{reply}\n\n{result}", None

            elif tool_name == "stop_share":
                result = self.tools["stop_share"]()
                return f"{reply}\n\n{result}", None

            else:
                return reply, None
                
        except Exception as e:
            print(f"LLM Processing Error: {e}")
            raise e

    def _process_with_regex(self, message: str, fallback_mode: bool = False) -> tuple[str, str | None]:
        # Normalize message for easier parsing
        msg = message.strip()

        # --- Simplified Shortcuts (Non-Smart Mode) ---

        # 1. List Directory: show <path> or ls <path>
        # Matches: "show D:/aicontrol" or "ls D:\Data"
        list_match = re.search(r"^(?:show|ls)\s+(.+)$", msg, re.IGNORECASE)
        if list_match:
            path = self._normalize_path(list_match.group(1))
            if not os.path.exists(path):
                return f"未找到该目录: {path}", None
            result = self.tools["list"](path)
            return f"已为您列出目录内容：\n\n{result}", f"file:///{path.replace(os.sep, '/')}"

        # 2. Read File: read <path> or cat <path>
        # Matches: "read D:/file.txt" or "cat D:\file.txt"
        read_match = re.search(r"^(?:read|cat)\s+(.+)$", msg, re.IGNORECASE)
        if read_match:
            path = self._normalize_path(read_match.group(1))
            if not os.path.exists(path):
                return f"未找到该文件: {path}", None
            result = self.tools["read"](path)
            return f"文件内容如下：\n\n{result}", f"file:///{path.replace(os.sep, '/')}"

        # 3. Open File: open <path> or run <path>
        # Matches: "open D:/app.exe" or "run D:\script.bat"
        open_match = re.search(r"^(?:open|run)\s+(.+)$", msg, re.IGNORECASE)
        if open_match:
            path = self._normalize_path(open_match.group(1))
            if not os.path.exists(path):
                return f"未找到该文件: {path}", None
            result = self.tools["open"](path)
            return f"已尝试打开文件：\n\n{result}", None

        # 4. Copy Files: copy <src> <dest> [pattern] or cp <src> <dest> [pattern]
        # Matches: "copy D:/src D:/dest" or "cp D:/src D:/dest *.txt"
        # Note: This simple regex splits by space. For paths with spaces, user might need quotes (not fully handled here for simplicity, or we can use shlex)
        # Let's use a simple split first.
        if msg.lower().startswith("copy ") or msg.lower().startswith("cp "):
            parts = msg.split()
            if len(parts) >= 3:
                # parts[0] is command
                # parts[1] is source (might be quoted?)
                # parts[2] is dest
                # parts[3] is pattern (optional)
                
                # A better way for basic usage without quotes support:
                source_path = self._normalize_path(parts[1])
                dest_path = self._normalize_path(parts[2])
                pattern = parts[3] if len(parts) > 3 else "*"
                
                result = self.tools["copy"](source_path, dest_path, pattern)
                return f"复制操作已完成：\n{result}", f"file:///{dest_path.replace(os.sep, '/')}"

        # 5. Share: start share / stop share
        if msg.lower() == "start share":
            return self.tools["start_share"](), None
        if msg.lower() == "stop share":
            return self.tools["stop_share"](), None
        if msg.lower() == "check share":
            return self.tools["check_share_status"](), None

        # --- Legacy Chinese Sentences ---

        # Regex for Copy Command
        copy_pattern = r"把(.*?)路径下的(.*?)文件,?\s*都复制到(.*?)路径下"
        copy_match = re.search(copy_pattern, msg)

        if copy_match:
            source_raw = copy_match.group(1)
            file_type = copy_match.group(2)
            dest_raw = copy_match.group(3)
            
            source_path = self._normalize_path(source_raw)
            dest_path = self._normalize_path(dest_raw)
            
            pattern = "*"
            if "表格" in file_type:
                pattern = "tables"
            
            result = self.tools["copy"](source_path, dest_path, pattern=pattern)
            return f"已为你完成, 请点击如下链接跳转确认.\n{result}", f"file:///{dest_path.replace(os.sep, '/')}"

        return "抱歉，我没有理解您的指令。\n\n**非智能模式支持的指令格式：**\n1. 查看目录: `show <路径>` (例如: `show D:/aicontrol`)\n2. 读取文件: `read <路径>` (例如: `read D:/test.txt`)\n3. 打开文件: `open <路径>` (例如: `open D:/app.exe`)\n4. 复制文件: `copy <源路径> <目标路径> [类型]`\n5. 局域网共享: `start share` 或 `stop share`\n\n或者使用完整的中文句式：'把...复制到...'", None

    def _normalize_path(self, path_str: str) -> str:
        r"""
        Convert natural language path to system path.
        Example: "我D盘里Note" -> "D:/Note"
        Example: "D:\Note" -> "D:/Note"
        """
        # Remove "我" (my) if present
        path_str = path_str.replace("我", "")
        
        # Handle "D盘" -> "D:"
        if "盘" in path_str:
            path_str = path_str.replace("盘", ":")
            
        # Handle "里" -> "/"
        if "里" in path_str:
             path_str = path_str.replace("里", "/")
             
        # Handle "路径" -> "" (cleanup)
        path_str = path_str.replace("路径", "")
        
        # Normalize all slashes to forward slashes
        path_str = path_str.replace("\\", "/")
        
        # Strip whitespace
        path_str = path_str.strip()
        
        # Handle bare drive letter "D:" -> "D:/"
        # regex to match exactly "X:"
        if re.match(r"^[a-zA-Z]:$", path_str):
            path_str += "/"
            
        return path_str
