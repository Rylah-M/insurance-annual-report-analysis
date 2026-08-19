from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "data" / "llm_settings.json"
DEFAULT_BASE_URL = "https://api.nwafu-ai.cn/v1"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_settings(api_key: str, base_url: str) -> dict[str, Any]:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings = {
        "api_key": api_key.strip(),
        "base_url": (base_url.strip().rstrip("/") or DEFAULT_BASE_URL),
        "updated_at": _now(),
    }
    SETTINGS_FILE.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        SETTINGS_FILE.chmod(0o600)
    except Exception:
        pass
    return settings


def mask_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}{'*' * 8}{api_key[-4:]}"


def effective_llm_env() -> dict[str, str]:
    """Return LLM environment variables for agent subprocesses."""
    settings = load_settings()
    env = os.environ.copy()
    if settings.get("api_key"):
        env["OPENAI_API_KEY"] = settings["api_key"]
    else:
        env.setdefault("OPENAI_API_KEY", "")
    env["LLM_BASE_URL"] = settings.get("base_url") or env.get(
        "LLM_BASE_URL", DEFAULT_BASE_URL
    )
    return env
