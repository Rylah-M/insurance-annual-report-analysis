from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from .task_store import append_log, append_step, finish_step, get_task, update_task
from .llm_settings import effective_llm_env


AGENTS_ROOT = Path(__file__).resolve().parents[2] / "agents"
AGENT_DIR = AGENTS_ROOT / "zd-agent0811"
CODE_DIR = AGENT_DIR / "code"
OUTPUT_DIR = AGENT_DIR / "output"
DB_DIR = AGENT_DIR / "database_result"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DATABASE_DIR = PROJECT_ROOT / "database"
PROJECT_DATABASE_CSV = PROJECT_DATABASE_DIR / "database_result.csv"

STEPS = [
    ("指标召回", "chunk_indicator_match.py", 20),
    ("候选增强", "indicator_match_enhance.py", 40),
    ("候选排序", "chunk_rerank.py", 60),
    ("LLM 指标提取", "indicator_extract_agent.py", 85),
    ("数据生成", "generate_indicator_database.py", 100),
]


def agent_env() -> dict[str, str]:
    return effective_llm_env()


def run_script(task_id: str, script: str, tag: str) -> None:
    append_log(task_id, f"运行 {script}（tag={tag}）")
    process = subprocess.Popen(
        [sys.executable, str(CODE_DIR / script), tag],
        cwd=str(CODE_DIR),
        env=agent_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    chunks: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        chunks.append(line.rstrip())
        if len(chunks) >= 20:
            append_log(task_id, "\n".join(chunks))
            chunks = []
        if get_task(task_id) and get_task(task_id).get("status") == "cancelled":
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()
            append_log(task_id, f"{script} 已被用户取消")
            raise RuntimeError(f"{script} 已取消")
    if chunks:
        append_log(task_id, "\n".join(chunks))
    process.wait(timeout=60)
    if process.returncode != 0:
        raise RuntimeError(f"{script} 执行失败（exit={process.returncode}）")


def read_result(tag: str) -> list[dict[str, Any]]:
    path = OUTPUT_DIR / f"extracted_indicator_result_{tag}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def update_database_from_csv() -> Path:
    """Sync the indicator agent's generated CSV into the web database."""
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    csv_file = DB_DIR / "database.csv"
    if not csv_file.exists():
        raise FileNotFoundError(f"指标数据库 CSV 不存在: {csv_file}")
    PROJECT_DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    PROJECT_DATABASE_CSV.write_bytes(csv_file.read_bytes())
    from database import sync_from_csv  # type: ignore

    result = sync_from_csv(csv_path=PROJECT_DATABASE_CSV)
    try:
        import data_loader

        data_loader.load_database.cache_clear()
    except Exception:
        pass
    return result


def import_database_for_task(task_id: str) -> dict[str, Any]:
    task = get_task(task_id) or {}
    if task.get("status") != "success" or not task.get("result_rows"):
        raise RuntimeError("任务尚未完成提取，无法写入数据库")
    db_path = update_database_from_csv()
    update_task(
        task_id,
        database_imported=True,
        database_path=str(db_path),
        save_to_database=True,
    )
    append_log(task_id, "已按用户操作将提取结果写入数据库")
    return {
        "task_id": task_id,
        "status": "imported",
        "database_path": str(db_path),
    }


def run_extraction(task_id: str) -> dict[str, Any]:
    task = get_task(task_id) or {}
    tag = task.get("output_name") or task.get("company", "").replace(" ", "_")
    if not tag:
        raise RuntimeError("任务缺少 output_name，无法启动指标提取")

    chunks_path = task.get("chunks_path")
    if chunks_path:
        source = Path(chunks_path)
        if source.exists():
            target = AGENT_DIR / "chunk" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            append_log(task_id, f"chunks 已同步到指标提取 Agent：{target.name}")

    update_task(task_id, status="extracting", progress=0, stage="准备指标提取")
    for name, script, progress in STEPS[:-1]:
        if get_task(task_id) and get_task(task_id).get("status") == "cancelled":
            append_log(task_id, f"任务已取消，跳过 {name}")
            return {"task_id": task_id, "status": "cancelled"}
        append_step(task_id, name, progress, name)
        append_log(task_id, f"[{name}] 开始")
        try:
            run_script(task_id, script, tag)
        except Exception as exc:
            if get_task(task_id) and get_task(task_id).get("status") == "cancelled":
                append_log(task_id, "任务已取消，忽略执行失败")
                return {"task_id": task_id, "status": "cancelled"}
            append_log(task_id, f"[{name}] 失败: {exc}")
            finish_step(task_id, name, status="failed")
            update_task(task_id, status="failed", stage=name, error=str(exc))
            raise
        if get_task(task_id) and get_task(task_id).get("status") == "cancelled":
            append_log(task_id, "任务已取消，停止后续步骤")
            return {"task_id": task_id, "status": "cancelled"}
        append_log(task_id, f"[{name}] 完成")
        finish_step(task_id, name)
        update_task(task_id, progress=progress, stage=name)

    rows = read_result(tag)
    append_step(task_id, "数据生成", 100, "数据生成")
    append_log(task_id, "[数据生成] 开始")
    run_script(task_id, "generate_indicator_database.py", tag)
    append_log(task_id, "[数据生成] 完成")
    finish_step(task_id, "数据生成")
    append_log(task_id, f"指标提取完成，共 {len(rows)} 条结果；尚未写入数据库，可在页面点击写入")
    update_task(
        task_id,
        status="success",
        progress=100,
        stage="数据生成",
        result_rows=len(rows),
        database_imported=False,
        database_path="",
        result_file=str(OUTPUT_DIR / f"extracted_indicator_result_{tag}.json"),
    )
    return {
        "task_id": task_id,
        "status": "success",
        "result_file": str(OUTPUT_DIR / f"extracted_indicator_result_{tag}.json"),
        "rows": len(rows),
    }


def start_extraction_background(task_id: str) -> None:
    thread = threading.Thread(
        target=run_extraction,
        args=(task_id,),
        daemon=True,
        name=f"extract-{task_id}",
    )
    thread.start()
