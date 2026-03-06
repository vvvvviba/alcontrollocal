from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import os
import subprocess
import sys
from agent import Agent

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = Agent()

class ChatRequest(BaseModel):
    message: str
    mode: str = "smart"

class ChatResponse(BaseModel):
    response: str
    action_link: str | None = None

class OpenRequest(BaseModel):
    path: str

class ConfigRequest(BaseModel):
    api_key: str
    base_url: str
    model: str

@app.get("/api/config")
async def get_config():
    return {
        "api_key": agent.api_key or "",
        "base_url": agent.base_url or "",
        "model": agent.model or ""
    }

@app.post("/api/config")
async def update_config(request: ConfigRequest):
    agent.update_config(request.api_key, request.base_url, request.model)
    return {"status": "success"}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        response, action_link = agent.process_message(request.message, request.mode)
        return ChatResponse(response=response, action_link=action_link)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/open")
async def open_path(request: OpenRequest):
    path = request.path
    # Strip file:/// if present
    if path.startswith("file:///"):
        path = path[8:]
    
    # Fix slashes for Windows
    path = path.replace("/", "\\")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
        return {"status": "opened"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_path = os.path.join(os.path.dirname(current_dir), "frontend")

if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"Warning: Frontend path {frontend_path} not found.")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
