from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import build_analysis_v2
from .critic import review as critic_review
from .excel_reader import load_excel
from .narrative import build_markdown
from .pdf_builder import build_pdf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "output" / "产险报告"
FINAL_MD = "2025年上市公司产险经营分析.md"
FINAL_PDF = "2025年上市公司产险经营分析.pdf"


def run(excel_path: str | None, output_dir: str | None) -> dict[str, Path]:
    records, source = load_excel(excel_path)
    analysis = build_analysis_v2(records)
    target = Path(output_dir) if output_dir else DEFAULT_OUTPUT
    target.mkdir(parents=True, exist_ok=True)
    markdown_path = target / FINAL_MD
    pdf_path = target / FINAL_PDF
    markdown = build_markdown(analysis)
    critic = critic_review(analysis, markdown)
    markdown_path.write_text(markdown, encoding="utf-8")
    build_pdf(analysis, pdf_path, critic_summary=critic["summary"])
    print(f"Quality Critic: {critic['summary']}")
    for finding in critic["findings"]:
        print(f"  [{finding['level']}] {finding['area']}: {finding['message']}")
    return {
        "markdown": markdown_path,
        "pdf": pdf_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Excel → 产险经营分析报告生成 Agent")
    parser.add_argument("--input", help="产险对标 Excel 路径")
    parser.add_argument("--output", help="输出目录")
    args = parser.parse_args()
    files = run(args.input, args.output)
    for name, path in files.items():
        print(f"{name}: {path}")


if __name__ == "__main__":
    main()
