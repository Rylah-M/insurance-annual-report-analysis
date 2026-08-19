from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = PROJECT_ROOT / "data" / "mineru_api.log"
PORT = 8001

_FALLBACK_EXECUTABLES = [
    "/Users/mowan/miniconda3/envs/annual_report/bin/mineru-api",
]


def _mineru_executable() -> str:
    candidates = [str(Path(sys.executable).parent / "mineru-api")]
    candidates.extend(_FALLBACK_EXECUTABLES)
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return candidates[0]


def _pid_by_port(port: int = PORT) -> int | None:
    try:
        output = subprocess.run(
            ["lsof", "-nP", "-iTCP", f":{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
        for line in output.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                return int(parts[1])
    except Exception:
        return None
    return None


def is_running(port: int = PORT) -> bool:
    return _pid_by_port(port) is not None


def stop_mineru(port: int = PORT) -> bool:
    pid = _pid_by_port(port)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if _pid_by_port(port) is None:
                return True
            time.sleep(0.3)
        os.kill(pid, signal.SIGKILL)
        return True
    except ProcessLookupError:
        return True
    except Exception:
        return False


def start_mineru(port: int = PORT) -> bool:
    if is_running(port):
        return True
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    executable = _mineru_executable()
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        subprocess.Popen(
            [executable, "--host", "127.0.0.1", "--port", str(port)],
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return True


def restart_mineru(port: int = PORT) -> None:
    stop_mineru(port)
    start_mineru(port)
