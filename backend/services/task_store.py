from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASK_FILE = PROJECT_ROOT / "data" / "parse_tasks.json"

_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load() -> dict[str, dict[str, Any]]:
    if not TASK_FILE.exists():
        return {}
    try:
        return json.loads(TASK_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(tasks: dict[str, dict[str, Any]]) -> None:
    TASK_FILE.parent.mkdir(parents=True, exist_ok=True)
    TASK_FILE.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def create_task(
    task_id: str,
    *,
    company: str,
    year: str,
    quarter: str,
    market: str,
    source_file: str,
) -> dict[str, Any]:
    task = {
        "task_id": task_id,
        "company": company,
        "year": year,
        "quarter": quarter,
        "market": market,
        "source_file": source_file,
        "status": "waiting",
        "progress": 0,
        "stage": "等待开始",
        "steps": [],
        "logs": [],
        "created_at": _now(),
        "updated_at": _now(),
        "error": "",
        "result_file": "",
        "result_rows": 0,
        "output_name": "",
        "chunks_path": "",
        "database_path": "",
        "save_to_database": True,
        "database_imported": False,
    }
    with _lock:
        tasks = _load()
        tasks[task_id] = task
        _save(tasks)
    return task


def get_task(task_id: str) -> dict[str, Any] | None:
    with _lock:
        tasks = _load()
        return tasks.get(task_id)


def list_tasks() -> list[dict[str, Any]]:
    with _lock:
        tasks = _load()
        return sorted(
            tasks.values(),
            key=lambda item: item.get("created_at", ""),
            reverse=True,
        )


def update_task(task_id: str, **changes: Any) -> dict[str, Any] | None:
    with _lock:
        tasks = _load()
        task = tasks.get(task_id)
        if task is None:
            return None
        task.update(changes)
        task["updated_at"] = _now()
        _save(tasks)
        return task


def append_log(task_id: str, line: str) -> None:
    with _lock:
        tasks = _load()
        task = tasks.get(task_id)
        if task is None:
            return
        logs = task.setdefault("logs", [])
        logs.append(str(line).rstrip())
        task["logs"] = logs[-500:]
        task["updated_at"] = _now()
        _save(tasks)


def cancel_task(task_id: str, reason: str = "用户手动终止") -> dict[str, Any] | None:
    with _lock:
        tasks = _load()
        task = tasks.get(task_id)
        if task is None:
            return None
        task["status"] = "cancelled"
        task["stage"] = "已取消"
        task["progress"] = 0
        task["error"] = reason
        task["updated_at"] = _now()
        _save(tasks)
        return task


def append_step(task_id: str, name: str, progress: int, stage: str) -> None:
    with _lock:
        tasks = _load()
        task = tasks.get(task_id)
        if task is None:
            return
        steps = task.setdefault("steps", [])
        steps.append(
            {
                "name": name,
                "progress": progress,
                "stage": stage,
                "time": _now(),
                "status": "running",
            }
        )
        task["progress"] = progress
        task["stage"] = stage
        task["updated_at"] = _now()
        _save(tasks)


def finish_step(task_id: str, name: str, status: str = "completed") -> None:
    with _lock:
        tasks = _load()
        task = tasks.get(task_id)
        if task is None:
            return
        for step in task.get("steps", []):
            if step.get("name") == name:
                step["status"] = status
                step["time"] = _now()
                break
        task["updated_at"] = _now()
        _save(tasks)
