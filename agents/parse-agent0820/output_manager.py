"""output_manager.py：统一输出目录与文件命名管理。

命名规范（与数据库标准一致）：
    <公司>_<年份>_<报告时间>_<市场>/<公司>_<年份>_<报告时间>_<市场>.*

例如：中国平安_2012_Q3_A股/
    中国平安_2012_Q3_A股.md
    中国平安_2012_Q3_A股_chunks.json
    中国平安_2012_Q3_A股_metadata.json

company / year / quarter / market 均由调用方（parse agent）传入，不硬编码。
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"

NAME_SEPARATOR = "_"

_OUTPUT_NAME_RE = re.compile(r"^(.*?)_(\d{4})_(Q[1-4])_(A股|港股|H股)$")
_OUTPUT_NAME_RE_OLD = re.compile(r"^(.*?)_(\d{4})_(A股|港股|H股)$")
_OUTPUT_NAME_RE_NO_MARKET = re.compile(r"^(.*?)_(\d{4})_(Q[1-4])$")


def build_output_name(
    company: str,
    year: str | int,
    market: str,
    quarter: str | None = None,
) -> str:
    """按数据库命名规范生成目录/文件名：<公司>_<年份>_<报告时间>_<市场>。"""
    parts = [str(company), str(year)]
    if quarter:
        parts.append(quarter)
    if market:
        parts.append(str(market))
    return NAME_SEPARATOR.join(parts)


def get_output_dir(
    company: str,
    year: str | int,
    market: str,
    quarter: str | None = None,
) -> Path:
    return OUTPUT_DIR / build_output_name(company, year, market, quarter)


def ensure_output_dir(
    company: str,
    year: str | int,
    market: str,
    quarter: str | None = None,
    *,
    root: Path | None = None,
) -> Path:
    """创建并返回输出目录。"""
    base = root or OUTPUT_DIR
    output_dir = base / build_output_name(company, year, market, quarter)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def resolve_output_files(output_dir: Path, output_name: str) -> dict[str, Path]:
    """返回输出目录中的三个结果文件路径。"""
    return {
        "md": output_dir / f"{output_name}.md",
        "chunks": output_dir / f"{output_name}_chunks.json",
        "metadata": output_dir / f"{output_name}_metadata.json",
    }


def write_json_file(data, path: Path) -> Path:
    """以 UTF-8 写入 JSON（保留中文、带缩进）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def write_metadata(
    company: str,
    year: str | int,
    market: str,
    source_file: str,
    total_chunks: int,
    *,
    quarter: str | None = None,
    output_dir: Path | None = None,
    created_time: str | None = None,
) -> Path:
    """生成 <输出名>_metadata.json。"""
    metadata = {
        "company": company,
        "year": int(year) if str(year).isdigit() else year,
        "source_file": source_file,
        "total_chunks": total_chunks,
        "created_time": created_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if quarter:
        metadata["quarter"] = quarter
    if market:
        metadata["market"] = market
    target_dir = output_dir or get_output_dir(company, year, market, quarter)
    output_name = build_output_name(company, year, market, quarter)
    return write_json_file(metadata, target_dir / f"{output_name}_metadata.json")


def list_completed(root: Path | None = None) -> list[dict]:
    """列出已完成解析的输出目录及其基本信息（兼容新旧命名）。"""
    base = root or OUTPUT_DIR
    result: list[dict] = []
    if not base.exists():
        return result
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        info: dict = {"name": d.name, "path": d}
        output_name = d.name
        files = resolve_output_files(d, output_name)
        chunks_file = files["chunks"] if files["chunks"].exists() else d / "chunks.json"
        raw_file = files["md"] if files["md"].exists() else d / "raw.md"
        if chunks_file.exists():
            try:
                chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
                info["total_chunks"] = len(chunks)
            except Exception:
                info["total_chunks"] = 0
        if raw_file.exists():
            info["raw_size_kb"] = round(raw_file.stat().st_size / 1024, 1)
        result.append(info)
    return result


def discover_companies(root: Path | None = None) -> list[str]:
    """从已有解析输出目录中动态发现公司名（作为下拉快捷选项）。"""
    base = root or OUTPUT_DIR
    companies: set[str] = set()
    if not base.exists():
        return []
    for d in base.iterdir():
        if not d.is_dir():
            continue
        match = (
            _OUTPUT_NAME_RE.match(d.name)
            or _OUTPUT_NAME_RE_OLD.match(d.name)
            or _OUTPUT_NAME_RE_NO_MARKET.match(d.name)
        )
        if match:
            companies.add(match.group(1))
    return sorted(companies)
