from __future__ import annotations

import json
import os
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "data" / "llm_settings.json"
DEFAULT_BASE_URL = "https://api.nwafu-ai.cn/v1"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@lru_cache(maxsize=1)
def machine_id() -> str:
    """Return a stable identifier for the current machine."""
    try:
        output = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        for line in output.splitlines():
            if "IOPlatformUUID" in line:
                parts = line.split('"')
                if len(parts) >= 4 and parts[-2]:
                    return f"mac:{parts[-2]}"
    except Exception:
        pass
    try:
        value = Path("/etc/machine-id").read_text(encoding="utf-8").strip()
        if value:
            return f"linux:{value}"
    except Exception:
        pass
    return f"node:{platform.node()}:{uuid.getnode():x}"


def _write_settings(data: dict[str, Any]) -> None:
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    try:
        SETTINGS_FILE.chmod(0o600)
    except Exception:
        pass


def load_settings() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if data.get("api_key") and not is_current_owner(data):
                # 当前 Key 未绑定本机，立即清除明文，避免被其他电脑直接读取。
                data["foreign_key_detected"] = True
                data.pop("api_key", None)
                data.pop("owner_machine_id", None)
                _write_settings(data)
            return data
    except Exception:
        pass
    return {}


def is_current_owner(settings: dict[str, Any] | None = None) -> bool:
    settings = settings or load_settings()
    owner = settings.get("owner_machine_id")
    return bool(owner) and owner == machine_id()


def save_settings(api_key: str, base_url: str) -> dict[str, Any]:
    settings = {
        "api_key": api_key.strip(),
        "base_url": (base_url.strip().rstrip("/") or DEFAULT_BASE_URL),
        "owner_machine_id": machine_id(),
        "updated_at": _now(),
        "foreign_key_detected": False,
    }
    _write_settings(settings)
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
    if settings.get("api_key") and is_current_owner(settings):
        env["OPENAI_API_KEY"] = settings["api_key"]
    else:
        env.setdefault("OPENAI_API_KEY", "")
    env["LLM_BASE_URL"] = settings.get("base_url") or env.get(
        "LLM_BASE_URL", DEFAULT_BASE_URL
    )
    return env
