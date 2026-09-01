"""Entry point for the standardexcel-agent.

Run from the agent directory:

    python main.py
    python main.py --output /path/to/standardexcel.xlsx
    python main.py --companies 人保,平安 --years 2024,2025
"""

import argparse
from pathlib import Path

import config
import data_loader
import indicator_filter
from excel_generator import generate_workbook


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成保险公司横向对标分析底稿 standardexcel.xlsx")
    parser.add_argument("--output", type=Path, default=config.OUTPUT_FILE, help="输出文件路径")
    parser.add_argument("--companies", default=None, help="逗号分隔的公司名称，默认全部")
    parser.add_argument("--years", default=None, help="逗号分隔的年份，默认2022-2026")
    args = parser.parse_args(argv)

    database_rows = data_loader.load_database(config.DATABASE_PATH)
    metadata_rows = data_loader.load_indicator_metadata(config.INDICATOR_METADATA_PATH)
    dictionary_rows = data_loader.load_indicator_dictionary(config.INDICATOR_DICTIONARY_PATH)
    dictionary_ids = {
        row.get("indicator_id") for row in dictionary_rows if row.get("indicator_id")
    }
    missing_defs = [
        meta.get("indicator_id")
        for meta in metadata_rows
        if meta.get("indicator_id") not in dictionary_ids
    ]
    if missing_defs:
        print(f"警告：indicator_dictionary.xlsx 中缺少定义: {missing_defs}")

    eligible_rows = indicator_filter.filter_database_rows(
        database_rows,
        config.ALLOWED_SCOPE_TYPES,
        config.EXCLUDED_SCOPE_TYPES,
    )
    matched = indicator_filter.match_metadata(metadata_rows, eligible_rows)
    if not matched:
        raise SystemExit("未匹配到任何财险口径/特殊财险口径指标数据，请检查输入文件。")

    best_rows = indicator_filter.dedupe_by_period(matched)
    companies = list(config.COMPANY_ORDER)
    if args.companies:
        selected = [c.strip() for c in args.companies.split(",") if c.strip()]
        if selected:
            companies = [c for c in config.COMPANY_ORDER if c in selected]
            companies += [c for c in selected if c not in config.COMPANY_ORDER]

    periods = list(config.PERIODS)
    if args.years:
        selected_years = sorted({int(y.strip()) for y in args.years.split(",") if y.strip()})
        if selected_years:
            periods = []
            for year in selected_years:
                periods.append(f"{year}Q2")
                periods.append(f"{year}Q4")

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generate_workbook(
        output_path=output_path,
        metadata_items=metadata_rows,
        best_rows=best_rows,
        companies=companies,
        periods=periods,
    )

    display_companies = "、".join(config.COMPANY_DISPLAY_NAMES.get(c, c) for c in companies)
    print(f"已生成: {output_path}")
    print(f"公司: {display_companies}")
    print(f"指标: {len(metadata_rows)} 个，期间: {len(periods)} 个，匹配记录: {len(best_rows)} 条")


if __name__ == "__main__":
    main()
