"""test_splitter.py：验证重构后的 cleaner + splitter 输出。

用法：
    python test_splitter.py                 # 使用项目内已有太保 md 样本
    python test_splitter.py --input a.md    # 指定输入 Markdown

输出：
    test_output/
        raw.md
        chunks.json
        metadata.json

检查：
1. 章节正确切分：每个 chunk 有 section/title/完整正文，position 连续、chunk_id 唯一
2. chunk 数量明显减少（本样本 146 页目标 ≤ 160，300 页年报目标 50-150）
3. 表格全部保留并绑定到章节 chunk，且不存在“纯表格 chunk”
4. 图片引用已删除
5. 编号标题（一、/（一）/1、）嵌套在章节内，不单独成 chunk
6. 超长 chunk（> 12000 tokens）按三级标题/段落拆分并保留 section/title
7. JSON 可正常读取，metadata 一致
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from cleaner import HTML_IMG_RE, IMAGE_REF_LINE_RE, clean_markdown
from output_manager import build_output_name, write_metadata
from splitter import HTML_TABLE_RE, PIPE_TABLE_RE, split_markdown

PROJECT_ROOT = Path(__file__).resolve().parent
TEST_OUTPUT_DIR = PROJECT_ROOT / "test_output"

SAMPLE_CANDIDATES = [
    Path("/Users/mowan/Desktop/Annual_Report_Analysis/output/028127ed-1437-4744-8a51-d921366e9d19/太保24Q2-A股/auto/太保24Q2-A股.md"),
    PROJECT_ROOT / "output" / "中国太保_2024_A股" / "raw.md",
    PROJECT_ROOT / "output" / "中国太保_2024_A股" / "中国太保_2024_A股.md",
]

MAX_TOKENS = 12000
QUARTER = "Q3"


def find_sample_md() -> Path:
    for candidate in SAMPLE_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit("未找到测试样本 Markdown，请使用 --input 指定输入文件")


def count_source_tables(text: str) -> int:
    html_count = len(HTML_TABLE_RE.findall(text))
    pipe_count = 0
    for match in PIPE_TABLE_RE.finditer(text):
        lines = [ln for ln in match.group(0).splitlines() if ln.strip()]
        if len(lines) >= 2:
            pipe_count += 1
    return html_count + pipe_count


def run_checks(
    raw: str,
    chunks: list[dict],
    input_name: str,
    errors: list[str],
) -> None:
    """对真实样本执行核心检查。"""
    # 1. 章节切分
    if not chunks:
        errors.append("chunks 为空，未切分出任何章节")
        return
    positions = [c["position"] for c in chunks]
    if positions != list(range(1, len(chunks) + 1)):
        errors.append("position 不是从 1 开始的连续递增序列")
    ids = [c["chunk_id"] for c in chunks]
    if len(set(ids)) != len(ids):
        errors.append("chunk_id 存在重复")
    for c in chunks:
        if f"_{QUARTER.lower()}_" not in c["chunk_id"]:
            errors.append(f"chunk_id 缺少报告时间：{c['chunk_id']}")
        if c.get("quarter") != QUARTER:
            errors.append(f"chunk 缺少 quarter 字段：{c['chunk_id']}")
    for c in chunks:
        if not c.get("section") or not c.get("title"):
            errors.append(f"chunk {c.get('chunk_id')} 缺少 section 或 title")
        if not c.get("content", "").strip():
            errors.append(f"chunk {c.get('chunk_id')} 内容为空（表格未绑定到章节）")
        if "tables" not in c or not isinstance(c["tables"], list):
            errors.append(f"chunk {c.get('chunk_id')} 缺少 tables 字段")

    # 2. chunk 数量明显减少（针对太保样本：146 页目标 ≤ 160）
    if "太保24Q2" in input_name:
        if len(chunks) > 160:
            errors.append(
                f"chunk 数量过多：{len(chunks)} > 160（目标：300 页年报 50-150 chunks）"
            )
    if len(chunks) < 10:
        errors.append(f"chunk 数量过少：{len(chunks)}")

    # 3. 表格全部保留且绑定到章节
    source_tables = count_source_tables(raw)
    preserved_tables = sum(len(c.get("tables", [])) for c in chunks)
    if source_tables != preserved_tables:
        errors.append(
            f"表格数量不一致：源 {source_tables} 个，chunks 中保留 {preserved_tables} 个"
        )

    # 4. 图片引用删除
    chunk_text = "\n".join(c.get("content", "") for c in chunks)
    if "![](" in chunk_text or "<img" in chunk_text.lower():
        errors.append("chunk 内容中仍存在图片引用")


def synthetic_checks(errors: list[str]) -> None:
    """构造样例验证编号嵌套与超长拆分规则。"""
    # 编号标题应嵌套在真实二级标题之下，不单独成 chunk
    nested_doc = """# 经营业绩

## 公司业务概要

一、主要业务

公司业务覆盖人身保险、财产保险等。

（一）人身保险

寿险业务保持稳健增长。

1、按渠道分析

代理人渠道与银保渠道均衡发展。

<table><tr><td>渠道</td><td>保费</td></tr></table>
"""
    chunks = split_markdown(nested_doc, "中国太保", 2024, "A股", max_tokens=MAX_TOKENS)
    titles = [c["title"] for c in chunks]
    if any(t.startswith("一、") or t.startswith("（一）") or t.startswith("1、") for t in titles):
        errors.append("编号标题（一、/（一）/1、）被拆成了独立 chunk")
    if not any(t == "公司业务概要" for t in titles):
        errors.append("真实二级标题未生成 chunk")
    company_chunk = next((c for c in chunks if c["title"] == "公司业务概要"), None)
    if company_chunk and "一、主要业务" not in company_chunk["content"]:
        errors.append("编号标题内容未保留在所属章节 chunk 内")
    if company_chunk and len(company_chunk["tables"]) != 1:
        errors.append("章节内表格未绑定到所属 chunk")

    # 超长章节（> max_tokens）按三级标题拆分，且保留 section/title
    long_doc = "# 财务报告\n\n## 经营情况讨论与分析\n\n导语。\n\n### 财产保险业务\n\n" + (
        "财产险保费收入与综合成本率指标说明。" * 800
    ) + "\n\n### 人寿保险业务\n\n" + ("寿险新业务价值指标说明。" * 800)
    chunks_long = split_markdown(
        long_doc, "中国太保", 2024, "A股", max_tokens=200
    )
    if not any(c["title"] == "财产保险业务" for c in chunks_long):
        errors.append("超长章节未按三级标题拆分")
    for c in chunks_long:
        if not c.get("section") or not c.get("title"):
            errors.append("超长拆分后丢失 section/title")
    if not all(c["section"] == "财务报告" for c in chunks_long if c["section"]):
        errors.append("超长拆分后 parent section 未保留")

    # 纯表格片段不得单独成 chunk（构造超长段落 + 孤立表格场景）
    table_doc = "# 测试\n\n## 风险数据\n\n" + ("这是一段很长很长的风险描述文字。" * 300) + "\n\n<table><tr><td>风险指标</td><td>数值</td></tr></table>\n\n"
    chunks_table = split_markdown(table_doc, "中国太保", 2024, "A股", max_tokens=300)
    if any(not c["content"].strip() for c in chunks_table):
        errors.append("存在纯表格 chunk（表格未绑定到章节）")
    total_tables = sum(len(c["tables"]) for c in chunks_table)
    if total_tables != 1:
        errors.append(f"纯表格场景下表格丢失或重复：{total_tables}")


def main() -> None:
    arg_parser = argparse.ArgumentParser(description="验证重构后的 cleaner + splitter")
    arg_parser.add_argument("--input", type=Path, default=None, help="输入 Markdown 文件")
    arg_parser.add_argument("--company", default="中国太保")
    arg_parser.add_argument("--year", type=int, default=2024)
    arg_parser.add_argument("--market", default="A股")
    args = arg_parser.parse_args()

    input_path = args.input or find_sample_md()
    raw = input_path.read_text(encoding="utf-8")
    cleaned = clean_markdown(raw)
    chunks = split_markdown(
        cleaned,
        args.company,
        args.year,
        args.market,
        quarter=QUARTER,
        max_tokens=MAX_TOKENS,
    )
    output_name = build_output_name(args.company, args.year, args.market, QUARTER)

    # 写 test_output
    TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw_file = TEST_OUTPUT_DIR / f"{output_name}.md"
    chunks_file = TEST_OUTPUT_DIR / f"{output_name}_chunks.json"
    raw_file.write_text(raw, encoding="utf-8")
    chunks_file.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_metadata(
        args.company,
        args.year,
        args.market,
        input_path.name,
        len(chunks),
        quarter=QUARTER,
        output_dir=TEST_OUTPUT_DIR,
    )

    errors: list[str] = []
    run_checks(raw, chunks, input_path.name, errors)
    synthetic_checks(errors)

    # JSON 可读取 + metadata 一致
    try:
        chunks_loaded = json.loads(chunks_file.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{chunks_file.name} 无法解析：{exc}")
        chunks_loaded = []
    try:
        metadata_loaded = json.loads(
            (TEST_OUTPUT_DIR / f"{output_name}_metadata.json").read_text(encoding="utf-8")
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{output_name}_metadata.json 无法解析：{exc}")
        metadata_loaded = {}
    if metadata_loaded.get("total_chunks") != len(chunks_loaded):
        errors.append("metadata.total_chunks 与 chunks.json 实际数量不一致")
    if metadata_loaded.get("quarter") != QUARTER:
        errors.append("metadata.json 缺少 quarter 字段")
    for key in ("company", "year", "market", "source_file", "total_chunks", "created_time"):
        if key not in metadata_loaded:
            errors.append(f"metadata.json 缺少字段：{key}")

    # 汇总
    source_images = len(IMAGE_REF_LINE_RE.findall(raw)) + len(HTML_IMG_RE.findall(raw))
    chunk_text = "\n".join(c.get("content", "") for c in chunks)
    residual_images = len(re.findall(r"!\[\]\(", chunk_text))
    preserved_tables = sum(len(c.get("tables", [])) for c in chunks)
    print(f"输入文件：{input_path}")
    print(f"原始字符数：{len(raw)}，清洗后字符数：{len(cleaned)}")
    print(f"chunk 数量：{len(chunks)}（目标：300 页年报 50-150 chunks）")
    print(f"源表格：{count_source_tables(raw)}，chunks 中保留表格：{preserved_tables}")
    print(f"源图片引用：{source_images}，chunks 中残留：{residual_images}")
    print(f"输出文件：{raw_file.name} / {chunks_file.name} / {output_name}_metadata.json")
    print(f"输出目录：{TEST_OUTPUT_DIR}")

    if errors:
        print("\n❌ 检查未通过：")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    print("\n✅ 全部检查通过：章节切分、表格绑定、图片删除、编号嵌套、超长拆分、JSON 可读。")


if __name__ == "__main__":
    main()
