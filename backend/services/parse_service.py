from __future__ import annotations

import sys
import threading
import os
from pathlib import Path

from .task_store import append_log, append_step, get_task, update_task


AGENTS_ROOT = Path(__file__).resolve().parents[2] / "agents"
PARSE_V1_DIR = AGENTS_ROOT / "Annual_Report_Analysis" / "parse_v1"
MINERU_API_BASE_URL = "http://127.0.0.1:8001"


def parse_v1_ready() -> bool:
    return (PARSE_V1_DIR / "parser.py").exists()


def run_parse(
    task_id: str,
    pdf_path: Path,
    company: str,
    year: str,
    quarter: str,
    market: str,
    *,
    start_page: int = 1,
    end_page: int | None = None,
    page_mode: str = "label",
    output_name: str | None = None,
) -> dict:
    """Run the existing parse_v1 pipeline without modifying its logic."""
    os.environ["NO_PROXY"] = "127.0.0.1,localhost"
    os.environ["no_proxy"] = "127.0.0.1,localhost"
    os.environ["MINERU_API_BASE_URL"] = os.environ.get(
        "MINERU_API_BASE_URL", MINERU_API_BASE_URL
    )
    sys.path.insert(0, str(PARSE_V1_DIR))
    from parser import parse_pdf  # type: ignore

    def emit(line: str) -> None:
        append_log(task_id, line)

    update_task(task_id, status="processing", progress=10, stage="PDF 上传完成")
    append_step(task_id, "PDF 上传完成", 10, "PDF 上传完成")

    try:
        result = parse_pdf(
            pdf_path,
            company,
            year,
            market,
            quarter=quarter,
            start_page=start_page,
            end_page=end_page,
            page_mode=page_mode,
            overwrite=True,
            log_callback=emit,
        )
    except Exception as exc:
        if get_task(task_id) and get_task(task_id).get("status") == "cancelled":
            append_log(task_id, "任务已取消，忽略解析失败")
            return {}
        append_log(task_id, f"解析失败: {exc}")
        update_task(task_id, status="failed", stage="解析失败", error=str(exc))
        raise

    if get_task(task_id) and get_task(task_id).get("status") == "cancelled":
        append_log(task_id, "任务已取消，忽略本次解析结果")
        return {}

    final_dir = result.final_dir
    auto_name = result.output_name
    if output_name and output_name != auto_name:
        renamed = final_dir.parent / output_name
        if renamed.exists():
            import shutil

            shutil.rmtree(renamed)
        final_dir.rename(renamed)
        for suffix in (".md", "_chunks.json", "_metadata.json"):
            old_file = renamed / f"{auto_name}{suffix}"
            if old_file.exists():
                old_file.rename(renamed / f"{output_name}{suffix}")
        final_dir = renamed
        result.output_name = output_name
        result.markdown_path = renamed / f"{output_name}.md"
        result.chunks_path = renamed / f"{output_name}_chunks.json"
        result.metadata_path = renamed / f"{output_name}_metadata.json"

    append_log(
        task_id,
        f"解析完成：{result.total_chunks} 个 chunk，耗时 {result.duration_seconds:.1f} 秒",
    )
    append_step(task_id, "MinerU 解析", 40, "MinerU 解析")
    append_step(task_id, "Markdown 生成", 70, "Markdown 生成")
    append_step(task_id, "Chunk 切片完成", 100, "Chunk 切片完成")
    update_task(
        task_id,
        status="success",
        progress=100,
        stage="Chunk 切片完成",
        output_name=result.output_name,
        chunks_path=str(result.chunks_path),
        result_file=str(result.chunks_path),
    )
    return {
        "task_id": task_id,
        "status": "success",
        "output_name": result.output_name,
        "chunks_path": str(result.chunks_path),
        "total_chunks": result.total_chunks,
    }


def start_parse_background(
    task_id: str,
    pdf_path: Path,
    company: str,
    year: str,
    quarter: str,
    market: str,
    *,
    start_page: int = 1,
    end_page: int | None = None,
    page_mode: str = "label",
    output_name: str | None = None,
) -> None:
    thread = threading.Thread(
        target=run_parse,
        args=(task_id, pdf_path, company, year, quarter, market),
        kwargs={
            "start_page": start_page,
            "end_page": end_page,
            "page_mode": page_mode,
            "output_name": output_name,
        },
        daemon=True,
        name=f"parse-{task_id}",
    )
    thread.start()
