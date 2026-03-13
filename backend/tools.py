import os
import shutil
import glob
import pandas as pd
from docx import Document
from docx.shared import Inches
import subprocess
import sys
import socket
import signal
from app_config import load_config

# Global variable to store the share server process
SHARE_PROCESS = None
SHARE_PID_FILE = os.path.join(os.path.dirname(__file__), "share.pid")

def _is_pid_running(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False

    if sys.platform == "win32":
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            if (
                "No tasks are running" in output
                or "没有运行的任务" in output
                or "信息:" in output
            ):
                return False
            return f"\"{pid}\"" in output
        except Exception:
            return False

    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def get_lan_ip():
    def _udp_guess() -> str:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            s.close()

    def _all_ipv4() -> list[str]:
        candidates: list[str] = []
        try:
            hostname = socket.gethostname()
            _, _, ips = socket.gethostbyname_ex(hostname)
            candidates.extend(ips)
        except Exception:
            pass

        guess = _udp_guess()
        candidates.append(guess)

        cleaned: list[str] = []
        for ip in candidates:
            if not isinstance(ip, str):
                continue
            ip = ip.strip()
            if not ip or ip == "127.0.0.1" or ip.startswith("169.254."):
                continue
            if ip not in cleaned:
                cleaned.append(ip)
        return cleaned

    def _score(ip: str) -> int:
        if ip.startswith("192.168."):
            return 300
        if ip.startswith("10."):
            return 200
        if ip.startswith("172."):
            try:
                second = int(ip.split(".")[1])
                if 16 <= second <= 31:
                    return 150
            except Exception:
                pass
        return 50

    ips = _all_ipv4()
    if not ips:
        return "127.0.0.1"
    ips.sort(key=_score, reverse=True)
    return ips[0]

def get_share_dir() -> str:
    return load_config().share_dir

def check_share_status():
    """Checks if the file sharing server is running."""
    if os.path.exists(SHARE_PID_FILE):
        try:
            with open(SHARE_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            if _is_pid_running(pid):
                ip = get_lan_ip()
                return f"running|http://{ip}:8081"
            try:
                os.remove(SHARE_PID_FILE)
            except OSError:
                pass
            return "stopped"
        except (ValueError, OSError, Exception):
            # Process doesn't exist or invalid PID
            return "stopped"
    return "stopped"

def start_share():
    """Starts the local file sharing server."""
    global SHARE_PROCESS
    
    # Check if already running via PID file
    if os.path.exists(SHARE_PID_FILE):
        try:
            with open(SHARE_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            if _is_pid_running(pid):
                return f"共享服务已在运行中: http://{get_lan_ip()}:8081"
            try:
                os.remove(SHARE_PID_FILE)
            except OSError:
                pass
        except (ValueError, OSError, Exception):
            # Process doesn't exist or invalid PID, clean up
            try:
                os.remove(SHARE_PID_FILE)
            except OSError:
                pass

    try:
        share_dir = get_share_dir()

        # Path to share_server.py
        server_script = os.path.join(os.path.dirname(__file__), "share_server.py")
        
        # Start process
        # Use Popen to run in background
        if sys.platform == 'win32':
             # CREATE_NEW_CONSOLE = 0x00000010
             SHARE_PROCESS = subprocess.Popen(
                 [sys.executable, server_script, "--shared-dir", share_dir],
                 creationflags=subprocess.CREATE_NEW_CONSOLE,
             )
        else:
             SHARE_PROCESS = subprocess.Popen([sys.executable, server_script, "--shared-dir", share_dir])
             
        # Save PID
        with open(SHARE_PID_FILE, 'w') as f:
            f.write(str(SHARE_PROCESS.pid))
            
        ip = get_lan_ip()
        lan_url = f"http://{ip}:8081"
        local_url = "http://127.0.0.1:8081"
        return f"✅ 局域网文件共享已开启！\n\n**本机访问(当前电脑):** [{local_url}]({local_url})\n**局域网访问(其他设备):** [{lan_url}]({lan_url})\n**本地共享文件夹:** `{share_dir}`\n\n1. 您现在可以将文件复制到该共享文件夹中。\n2. 其他设备需与本机处于同一网络/同一 Wi-Fi 才能访问局域网地址。\n3. 如提示拒绝连接，请检查防火墙是否允许端口 8081。"
    except Exception as e:
        return f"启动共享服务失败: {str(e)}"

def stop_share():
    """Stops the local file sharing server."""
    global SHARE_PROCESS
    
    pid = None
    if os.path.exists(SHARE_PID_FILE):
        try:
            with open(SHARE_PID_FILE, 'r') as f:
                pid = int(f.read().strip())
        except ValueError:
            pass
            
    if not pid and not SHARE_PROCESS:
        return "共享服务未运行。"
        
    try:
        if sys.platform == 'win32' and pid:
            # On Windows, use taskkill to kill the process tree
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True)
        elif pid:
            os.kill(pid, signal.SIGTERM)
            
        if SHARE_PROCESS:
            SHARE_PROCESS.terminate()
            SHARE_PROCESS = None
            
        # Small delay to allow OS to clean up
        import time
        time.sleep(0.5)
            
        if os.path.exists(SHARE_PID_FILE):
            try:
                os.remove(SHARE_PID_FILE)
            except OSError:
                pass
            
        return "🛑 局域网共享已停止。"
    except Exception as e:
        # Final attempt to remove PID file even if error occurred
        if os.path.exists(SHARE_PID_FILE):
            try:
                os.remove(SHARE_PID_FILE)
            except:
                pass
        return f"停止服务时出错: {str(e)}"

def copy_files(source_dir: str, dest_dir: str, pattern: str = "*"):
    """Copies files matching pattern from source to destination."""
    if not os.path.exists(source_dir):
        return f"Error: Source directory '{source_dir}' does not exist."
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)
        
    copied_count = 0
    errors = []
    
    # Simple pattern matching, can be enhanced
    if pattern == "表格文件" or pattern == "tables" or pattern == "spreadsheets":
        file_patterns = ['*.xlsx', '*.xls', '*.csv']
    else:
        file_patterns = [pattern] # Assume it's a glob pattern or '*'

    files_to_copy = []
    for pat in file_patterns:
        full_pattern = os.path.join(source_dir, pat)
        files_to_copy.extend(glob.glob(full_pattern))
    
    # Remove duplicates if any
    files_to_copy = list(set(files_to_copy))
    
    if not files_to_copy:
         return f"No files found matching '{pattern}' in '{source_dir}'."

    for file_path in files_to_copy:
        try:
            shutil.copy2(file_path, dest_dir)
            copied_count += 1
        except Exception as e:
            errors.append(f"Failed to copy {os.path.basename(file_path)}: {str(e)}")
            
    result_msg = f"Successfully copied {copied_count} files to '{dest_dir}'."
    if errors:
        result_msg += f"\nErrors: {'; '.join(errors)}"
        
    return result_msg

import datetime

import urllib.parse

def get_dir_size(path: str) -> int:
    """Recursively calculates directory size."""
    total_size = 0
    try:
        with os.scandir(path) as it:
            for entry in it:
                try:
                    if entry.is_file():
                        total_size += entry.stat().st_size
                    elif entry.is_dir():
                        total_size += get_dir_size(entry.path)
                except OSError:
                    pass # Skip unreadable files/dirs
    except OSError:
        pass # Skip unreadable dirs
    return total_size

def format_size(size: int) -> str:
    """Formats size in bytes to human readable string (B, KB, MB, GB, TB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}".replace(".0 ", " ")
        size /= 1024
    return f"{size:.1f} PB"

def list_directory(path: str) -> str:
    """Lists files and directories in the given path."""
    # Ensure path uses forward slashes to avoid escaping issues in Markdown links
    path = path.replace("\\", "/")
    
    # Fix: "D:" in python refers to CWD on D drive, not root. "D:/" is needed.
    if path.endswith(":"):
        path += "/"
        
    if not os.path.exists(path):
        return f"Error: Path '{path}' does not exist."
    
    try:
        items = os.listdir(path)
        
        # Parent directory
        parent_path = os.path.dirname(path)
        if parent_path == path: # Root directory
            back_link = ""
        else:
            # URL encode path in back link
            encoded_parent = urllib.parse.quote(parent_path)
            back_link = f"[⬅️ 返回上一级](cmd:list:{encoded_parent})"

        if not items:
            return f"{back_link}\n\nDirectory '{path}' is empty."
            
        data = []
        for item in items:
            full_path = os.path.join(path, item).replace("\\", "/")
            try:
                stats = os.stat(full_path)
                
                # Type
                is_dir = os.path.isdir(full_path)
                type_icon = "📁" if is_dir else "📄"
                
                # Size
                if is_dir:
                    # Calculate directory size recursively
                    # Note: This might be slow for large directories. 
                    # For better UX, we could make this optional or async, but for now we implement as requested.
                    size_bytes = get_dir_size(full_path)
                    size_str = format_size(size_bytes)
                else:
                    size_bytes = stats.st_size
                    size_str = format_size(size_bytes)
                
                # Date
                mtime = datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                
                # Generate Clickable Link
                # URL encode path to handle spaces and special chars
                encoded_path = urllib.parse.quote(full_path)
                
                if is_dir:
                    link = f"[{item}](cmd:list:{encoded_path})"
                else:
                    # Check extension
                    ext = os.path.splitext(item)[1].lower()
                    if ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.log', '.csv', '.ini', '.yaml', '.yml', '.docx']:
                        link = f"[{item}](cmd:read:{encoded_path})"
                    else:
                        link = f"[{item}](cmd:open:{encoded_path})"
                
                data.append({
                    "name_link": link,
                    "name": item, # for sorting
                    "type": type_icon,
                    "size": size_str,
                    "date": mtime,
                    "is_dir": is_dir
                })
            except Exception:
                # Skip files we can't access
                continue
        
        # Sort: Directories first, then files
        data.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        
        # Build Markdown Table
        # Use HTML &nbsp; for spacing
        result = f"### Contents of `{path}`\n\n"
        if back_link:
             result += f"{back_link}\n\n"
             
        result += "| 类型 | 名称 | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;大小&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;修改日期&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; |\n"
        result += "| :---: | :--- | :--- | :--- |\n"
        
        for item in data:
            # Pad size and date for better visual spacing in some renderers
            size_display = f"{item['size']}"
            date_display = f"{item['date']}"
            result += f"| {item['type']} | {item['name_link']} | {size_display} | {date_display} |\n"
            
        return result
    except Exception as e:
        return f"Error listing directory '{path}': {str(e)}"

def read_file(path: str) -> str:
    """Reads the content of a file."""
    if not os.path.exists(path):
        return f"Error: File '{path}' does not exist."
    
    try:
        ext = os.path.splitext(path)[1].lower()
        
        if ext == '.docx':
            doc = Document(path)
            content = "\n".join([para.text for para in doc.paragraphs])
            return f"### Content of `{os.path.basename(path)}`\n\n{content}"
            
        else:
            # Try reading as text
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read(2000) # Read first 2000 chars to avoid huge context
                if len(content) == 2000:
                    content += "\n...(content truncated)..."
            
            # Determine language for code block
            lang = ext[1:] if ext else ""
            return f"### Content of `{os.path.basename(path)}`\n\n```{lang}\n{content}\n```"
            
    except Exception as e:
        return f"Error reading file '{path}': {str(e)}"

def open_file(path: str) -> str:
    """Opens a file with the system default application."""
    if not os.path.exists(path):
        return f"Error: File '{path}' does not exist."
        
    try:
        os.startfile(path)
        return f"Successfully launched '{os.path.basename(path)}' with system default application."
    except Exception as e:
        return f"Error opening file '{path}': {str(e)}"
