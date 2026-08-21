"""把本地数据中残留的旧公司全称统一规范化为新短名(人保/太保/太平/平安/阳光/众安)。

处理范围:
- chunk JSON 的 company / chunk_id 字段
- 指标提取结果 JSON 的 company / chunk_id / source_chunk_id 字段
- database_result.csv 与 agents/zd-agent0811/database_result/database.csv 的公司列
- 重建 SQLite 指标库与知识库索引

注意:年报正文 content 里出现的公司全称属于原文,不做替换。
"""

from __future__ import annotations

import csv
import glob
import json
import os
import subprocess
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[3]
OLD_TO_NEW = {
    "中国人保": "人保",
    "中国太保": "太保",
    "中国太平": "太平",
    "中国平安": "平安",
    "中国阳光": "阳光",
    "众安在线": "众安",
}


def short_name(value: str) -> str:
    return OLD_TO_NEW.get(value, value)


def short_prefix(value: str) -> str:
    for old, new in OLD_TO_NEW.items():
        if isinstance(value, str) and value.startswith(old):
            return new + value[len(old):]
    return value


def normalize_json(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False

    def walk(node):
        nonlocal changed
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if key == "company" and isinstance(value, str) and value in OLD_TO_NEW:
                    node[key] = short_name(value)
                    changed = True
                elif key in ("chunk_id", "source_chunk_id") and isinstance(value, str):
                    new_value = short_prefix(value)
                    if new_value != value:
                        node[key] = new_value
                        changed = True
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    if changed:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_csv(path: Path) -> None:
    if not path.exists():
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    kept = []
    changed = False
    for row in rows:
        company = (row.get("company") or "").strip()
        if not company:
            continue  # 丢弃公司名为空的脏数据
        new_company = short_name(company)
        if new_company != company:
            row["company"] = new_company
            changed = True
        if "source_chunk_id" in row and row.get("source_chunk_id"):
            new_chunk = short_prefix(row["source_chunk_id"])
            if new_chunk != row["source_chunk_id"]:
                row["source_chunk_id"] = new_chunk
                changed = True
        kept.append(row)
    if changed or len(kept) != len(rows):
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept)


def main() -> None:
    chunk_files = (
        list(PROJECT.glob("output_chunks/*/*_chunks.json"))
        + list(PROJECT.glob("output_chunks_v2/*/*_chunks.json"))
        + list(PROJECT.glob("agents/parse-agent0820/output/*/*_chunks.json"))
        + list(PROJECT.glob("agents/zd-agent0811/chunk/*_chunks.json"))
    )
    print(f"chunk 文件: {len(chunk_files)}")
    for path in chunk_files:
        normalize_json(path)

    result_files = list(PROJECT.glob("agents/zd-agent0811/output/*.json"))
    print(f"提取结果 JSON: {len(result_files)}")
    for path in result_files:
        normalize_json(path)

    for csv_path in [
        PROJECT / "database" / "database_result.csv",
        PROJECT / "agents" / "zd-agent0811" / "database_result" / "database.csv",
    ]:
        normalize_csv(csv_path)
        print("CSV 规范化:", csv_path)

    # 重建 SQLite 指标库
    subprocess.run(
        [
            "/Users/mowan/miniconda3/envs/annual_report/bin/python",
            "-c",
            "from database import sync_from_csv; p=sync_from_csv(); print('SQLite 重建:', p)",
        ],
        cwd=str(PROJECT / "backend"),
        check=True,
    )
    # 重建知识库索引
    subprocess.run(
        [
            "/Users/mowan/miniconda3/envs/annual_report/bin/python",
            "-m",
            "agent.chunk_index",
        ],
        cwd=str(PROJECT / "backend"),
        check=True,
    )
    print("完成")


if __name__ == "__main__":
    main()
