from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import socket
from typing import List
import urllib.parse
import argparse

def _resolve_shared_dir() -> str:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--shared-dir", dest="shared_dir", type=str, default=None)
    args, _ = parser.parse_known_args()

    if isinstance(args.shared_dir, str) and args.shared_dir.strip():
        return args.shared_dir.strip().replace("\\", "/")

    env_dir = os.getenv("AICONTROL_SHARED_DIR")
    if isinstance(env_dir, str) and env_dir.strip():
        return env_dir.strip().replace("\\", "/")

    return "D:/aicontrol/shared" if os.name == "nt" else os.path.expanduser("~/aicontrol/shared").replace("\\", "/")

SHARED_DIR = _resolve_shared_dir()
if not os.path.exists(SHARED_DIR):
    os.makedirs(SHARED_DIR)

app = FastAPI()

# Mount the shared directory for downloading files
app.mount("/files", StaticFiles(directory=SHARED_DIR), name="files")

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

@app.get("/", response_class=HTMLResponse)
async def list_files():
    files = os.listdir(SHARED_DIR)
    files_html = ""
    for f in files:
        # URL encode filename for link
        safe_name = urllib.parse.quote(f)
        files_html += f'<li><a href="/files/{safe_name}" target="_blank">{f}</a></li>'
    
    if not files:
        files_html = "<li>暂无文件</li>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Control 局域网共享</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f9fafb; color: #1f2937; }}
            .container {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }}
            h1 {{ color: #2563eb; font-size: 24px; margin: 0; }}
            .upload-box {{ border: 2px dashed #cbd5e1; border-radius: 8px; padding: 40px; text-align: center; margin-bottom: 30px; transition: border-color 0.3s; }}
            .upload-box:hover {{ border-color: #3b82f6; }}
            input[type="file"] {{ margin-bottom: 10px; }}
            button {{ background-color: #2563eb; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 16px; transition: background-color 0.2s; }}
            button:hover {{ opacity: 0.9; }}
            ul {{ list-style-type: none; padding: 0; }}
            li {{ padding: 12px; border-bottom: 1px solid #e5e7eb; display: flex; align-items: center; }}
            li:last-child {{ border-bottom: none; }}
            a {{ text-decoration: none; color: #4b5563; font-weight: 500; display: block; width: 100%; }}
            a:hover {{ color: #2563eb; }}
            .ip-info {{ background-color: #eff6ff; color: #1e40af; padding: 10px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <button onclick="window.history.back()" style="background-color: #64748b; padding: 8px 16px; font-size: 14px;">⬅ 返回</button>
                <h1 style="margin: 0; flex-grow: 1; text-align: center;">📂 局域网文件共享</h1>
                <div style="width: 60px;"></div> <!-- Spacer for centering -->
            </div>
            
            <div class="ip-info">
                本机 IP: <strong>{get_ip()}</strong> | 端口: <strong>8081</strong>
            </div>

            <div class="upload-box">
                <form action="/upload" method="post" enctype="multipart/form-data">
                    <h3 style="margin-top:0; color:#64748b;">上传文件</h3>
                    <input type="file" name="files" multiple required>
                    <br><br>
                    <button type="submit">开始上传</button>
                </form>
            </div>

            <h2>已共享文件</h2>
            <ul>
                {files_html}
            </ul>
        </div>
    </body>
    </html>
    """
    return html_content

@app.post("/upload", response_class=HTMLResponse)
async def upload_files(files: List[UploadFile] = File(...)):
    uploaded_names = []
    for file in files:
        try:
            file_path = os.path.join(SHARED_DIR, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            uploaded_names.append(file.filename)
        except Exception as e:
            print(f"Error saving {file.filename}: {e}")
    
    return f"""
    <html>
        <head>
            <meta http-equiv="refresh" content="2;url=/" />
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background-color: #f0fdf4; color: #166534; }}
                .box {{ text-align: center; padding: 40px; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            </style>
        </head>
        <body>
            <div class="box">
                <h2>✅ 上传成功!</h2>
                <p>已保存: {', '.join(uploaded_names)}</p>
                <p>正在返回文件列表...</p>
                <a href="/">如果未自动跳转，请点击这里</a>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    print(f"Starting Share Server on port 8081...")
    uvicorn.run(app, host="0.0.0.0", port=8081)
