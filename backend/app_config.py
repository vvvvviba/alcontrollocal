import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


def default_share_dir() -> str:
    if os.name == "nt":
        return "D:/aicontrol/shared"
    return os.path.expanduser("~/aicontrol/shared").replace("\\", "/")


class AppConfig(BaseModel):
    api_key: str = ""
    base_url: str = ""
    model: str = "gpt-3.5-turbo"
    share_dir: str = ""


_BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = _BACKEND_DIR / ".env"
CONFIG_FILE = _BACKEND_DIR / "config.json"


def load_config() -> AppConfig:
    load_dotenv(ENV_FILE)

    cfg = AppConfig(
        api_key=os.getenv("OPENAI_API_KEY", "") or "",
        base_url=os.getenv("OPENAI_BASE_URL", "") or "",
        model=os.getenv("LLM_MODEL", "gpt-3.5-turbo") or "gpt-3.5-turbo",
        share_dir=os.getenv("AICONTROL_SHARED_DIR", "") or "",
    )

    if not cfg.share_dir:
        cfg.share_dir = default_share_dir()

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = cfg.model_dump()
                for k in ("api_key", "base_url", "model", "share_dir"):
                    v = data.get(k)
                    if isinstance(v, str) and v.strip():
                        merged[k] = v.strip()
                cfg = AppConfig(**merged)
        except Exception:
            pass

    cfg.share_dir = (cfg.share_dir or default_share_dir()).replace("\\", "/")
    return cfg


def save_config(cfg: AppConfig) -> None:
    payload = cfg.model_dump()
    payload["share_dir"] = (payload.get("share_dir") or default_share_dir()).replace("\\", "/")
    CONFIG_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
