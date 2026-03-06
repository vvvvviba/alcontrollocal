# AI Control - 本地智能文件管理助手

AI Control 是一个基于 Python FastAPI 和现代 Web 技术构建的本地文件管理助手。它结合了 LLM（大语言模型）的智能理解能力与高效的本地文件操作工具，旨在简化您的日常文件管理任务。

## ✨ 核心特性

### 1. 双模式交互 (Dual Mode)
- **✨ 智能模式 (Smart Mode)**：
  - 基于 LLM（支持 OpenAI, DeepSeek, Ollama, Minimax 等）。
  - 支持自然语言指令，例如："帮我看看 D 盘有什么文件" 或 "把 Downloads 里的图片复制到 D:/Photos"。
- **⚡ 非智能模式 (Regex Mode)**：
  - 无需 API Key，基于正则表达式匹配，响应速度极快。
  - 支持快捷指令：`show`, `read`, `open`, `copy`, `start share`, `stop share`。

### 2. 📂 局域网文件共享 (LAN Share)
- **一键开启**：在聊天界面点击"开启共享"或输入 `start share`。
- **一键关闭**：在聊天界面点击"关闭共享"或输入 `stop share`。
- **跨设备访问**：自动生成局域网访问链接（如 `http://192.168.1.5:8081`）。
- **手机/平板支持**：同一 Wi-Fi 下的设备均可访问，支持文件上传与下载。
- **可视化管理**：清晰的 Web 界面展示共享文件列表。

### 3. 🛠️ 实用工具箱
- **文件操作**：
  - **查看目录**：以 Markdown 表格形式展示文件列表，支持点击进入子目录。
  - **读取文件**：支持直接预览文本文件 (.txt, .md, .py, .json 等) 内容。
  - **打开文件**：调用系统默认应用打开文件（如 .exe, .mp4, .docx）。
  - **批量复制**：支持按文件类型（如表格、图片）批量复制。
- **历史记录**：自动保存聊天记录到本地浏览器，支持一键清空。
- **主题适配**：完美支持深色模式 (Dark Mode) 和浅色模式 (Light Mode)。

---

## 🚀 快速开始

### 1. 环境准备
确保已安装 Python 3.10 或更高版本。

### 2. 安装依赖
在项目根目录下运行：
```bash
pip install -r backend/requirements.txt
```

### 3. 启动服务
在项目根目录下运行：
```bash
python backend/main.py
```
或者进入 `backend` 目录运行：
```bash
cd backend
python main.py
```

### 4. 访问应用
打开浏览器访问：[http://localhost:8000](http://localhost:8000)

---

## 📖 使用指南

### 界面概览
- **顶部工具栏**：
  - **模式切换**：点击 "✨ 智能模式" / "⚡ 非智能模式" 按钮切换。
  - **设置 (⚙️)**：配置 LLM 模型、API Key 和 Base URL。
  - **局域网共享**：点击共享图标开启/关闭文件服务。
- **聊天区域**：与 AI 助手对话，查看操作结果。
- **底部输入框**：输入指令，左侧有清空历史记录按钮 (🗑️)。

### ⚡ 非智能模式指令 (Regex Mode)
无需配置 API Key 即可使用以下快捷指令：

| 指令格式 | 示例 | 说明 |
| :--- | :--- | :--- |
| `show <路径>` | `show D:/aicontrol` | 查看目录内容 |
| `read <路径>` | `read D:/note.txt` | 读取文件内容 |
| `open <路径>` | `open D:/game.exe` | 使用系统默认应用打开文件 |
| `copy <源> <目标> [类型]` | `copy D:/src D:/dst *.jpg` | 复制文件 (支持通配符) |
| `start share` | `start share` | 开启局域网共享服务 |
| `stop share` | `stop share` | 停止局域网共享服务 |

### ✨ 智能模式配置 (Smart Mode)
点击右上角 **设置 (⚙️)** 按钮进行配置：

1.  **API Key**: 输入您的 LLM API Key。
2.  **Base URL**: 输入 API 服务地址 (例如 `https://api.openai.com/v1` 或 `https://api.deepseek.com`)。
3.  **Model Name**: 选择或输入模型名称 (如 `gpt-3.5-turbo`, `deepseek-chat`)。

**配置示例 (DeepSeek)**:
- Base URL: `https://api.deepseek.com`
- Model: `deepseek-chat`

**配置示例 (本地 Ollama)**:
- Base URL: `http://localhost:11434/v1`
- Model: `llama3`

---

## ❓ 常见问题

**Q: 局域网共享无法访问？**
A: 请确保您的电脑和手机连接在同一个 Wi-Fi 网络下。如果仍然无法访问，请检查电脑防火墙是否允许 Python 程序通过端口 8081。

**Q: 智能模式提示"无法理解指令"？**
A: 请检查 API Key 和 Base URL 是否配置正确。如果配置无误，尝试切换到"非智能模式"使用标准指令测试功能是否正常。

**Q: 如何清空聊天记录？**
A: 点击输入框左侧的垃圾桶图标 (🗑️)，确认后即可清空所有历史记录。

---

## 🛠️ 技术栈
- **后端**: Python, FastAPI, Uvicorn
- **前端**: HTML5, TailwindCSS, Marked.js, Axios
- **LLM 集成**: OpenAI SDK (兼容所有类 OpenAI 接口)
