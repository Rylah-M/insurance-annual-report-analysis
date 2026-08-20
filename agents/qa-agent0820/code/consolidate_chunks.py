"""统一重切:把过碎的 chunks 按章节语义合并为统一粒度的知识库。

背景:
- parse_v1/output 里的 chunks 是流水线原产物,部分报告(如平安 2025 Q4)
  被切成 899 个平均 200 字的碎片;
- output_chunks 里的旧语义版又缺少"管理层讨论/经营计划/展望"等章节。

本脚本对每份报告的 chunks 按"相邻 + 同章节 + 目标长度"合并,
产出 output_chunks_v2(每份报告一个目录),不做简繁转换、不改原文。

用法:
    python consolidate_chunks.py
"""

from __future__ import annotations

import json
import glob
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
INPUT_GLOBS = (
    "agents/parse-agent0820/output/*/*_chunks.json",
)
OUTPUT_ROOT = PROJECT_ROOT / "output_chunks_v2"

MIN_CHARS = 600      # 组长度低于此值时不主动断开
MAX_CHARS = 2200     # 组内容字符数上限


def _group_key(chunk: dict) -> str:
    return chunk.get("section") or ""


def consolidate(file_chunks: list[dict]) -> list[dict]:
    groups: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        chunks = current["chunks"]
        first = chunks[0]
        content = "\n\n".join(str(c.get("content") or "") for c in chunks).strip()
        tables: list = []
        for c in chunks:
            if c.get("tables"):
                tables.extend(c["tables"])
        groups.append(
            {
                "chunk_id": f"{current['stem']}_{len(groups) + 1:03d}",
                "company": first.get("company"),
                "year": first.get("year"),
                "quarter": first.get("quarter"),
                "market": first.get("market"),
                "section": first.get("section"),
                "title": first.get("title"),
                "content": content,
                "tables": tables,
                "position": first.get("position"),
            }
        )
        current = None

    for chunk in file_chunks:
        size = len(str(chunk.get("content") or ""))
        if current is None:
            current = {"stem": _stem_of(chunk), "chunks": [chunk], "len": size}
            continue
        current_len = current["len"]
        # 单段超大时直接自成一组
        if size > MAX_CHARS:
            flush()
            current = {"stem": _stem_of(chunk), "chunks": [chunk], "len": size}
            continue
        # 章节切换 → 断开（不跨章节合并）
        if _group_key(chunk) != _group_key(current["chunks"][-1]):
            flush()
            current = {"stem": _stem_of(chunk), "chunks": [chunk], "len": size}
            continue
        # 超上限 → 断开
        if current_len + size > MAX_CHARS:
            flush()
            current = {"stem": _stem_of(chunk), "chunks": [chunk], "len": size}
            continue
        current["chunks"].append(chunk)
        current["len"] += size
    flush()
    return groups


def _stem_of(chunk: dict) -> str:
    return str(chunk.get("chunk_id") or "").rsplit("_", 1)[0]


def main() -> None:
    files = []
    for pattern in INPUT_GLOBS:
        files.extend(glob.glob(str(PROJECT_ROOT / pattern)))
    files = sorted(set(files))
    if not files:
        print("未找到输入 chunks 文件")
        sys.exit(1)

    total_in = total_out = 0
    print(f"处理 {len(files)} 份报告 -> {OUTPUT_ROOT}")
    for path in files:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, list) or not data:
            print(f"  跳过(空/格式异常): {Path(path).name}")
            continue
        stem = Path(path).parent.name  # 如 平安_2025_Q4_A股
        out_dir = OUTPUT_ROOT / stem
        out_dir.mkdir(parents=True, exist_ok=True)
        groups = consolidate(data)
        (out_dir / f"{stem}_chunks.json").write_text(
            json.dumps(groups, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        total_in += len(data)
        total_out += len(groups)
        print(f"  {stem}: {len(data)} -> {len(groups)}")
    print(f"合计: {total_in} -> {total_out}")


if __name__ == "__main__":
    main()
