from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl


DEFAULT_EXCEL = Path(
    "/Users/mayuhang/Documents/为了agent暂时放其他文件/慢慢找工作/阳光学习资料"
    "/0806‘agent/2025年上市公司年报数据对标-产险V3.xlsx"
)

ANNUAL_SHEET = "3-产险对标"
H1_SHEET = "3.1-2023H1产险对标(新准则)"

VALUE_PERIODS = [
    "2022-重述",
    "2023H1",
    "2023",
    "2024H1",
    "2024",
    "2025H1",
    "2025",
]
GROWTH_PERIODS = ["2023", "2024H1", "2024", "2025H1", "2025"]

COMPANY_MAP = {
    "人保": "人保",
    "太保": "太保",
    "平安": "平安",
    "大地": "大地",
    "太平": "太平",
    "众安（产险业务）": "众安",
    "众安（合并口径）": "众安（合并口径）",
    "上市公司合计": "上市公司合计",
    "阳光": "阳光",
    "阳光-上市": "阳光-上市",
}

LISTED_COMPANIES = ["人保", "太保", "平安", "大地", "太平", "众安"]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("--", "")
    if not text or text in {"-", "N/A", "NA", "未披露"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_growth(value: Any) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    # Excel 使用 -1 作为缺失/无法计算的同比占位
    if abs(number + 1) < 1e-9:
        return None
    return number


def _norm_indicator(indicator: str) -> dict[str, str]:
    text = str(indicator or "").strip()
    metric = text
    line = "整体"
    if text.startswith("原保险保费收入"):
        metric = "原保险保费收入"
        if "非车非保证" in text:
            line = "非车非保证险"
        elif "非车险" in text:
            line = "非车险"
        elif "车险" in text:
            line = "车险"
    elif text.startswith("[承保]综合成本率（年报）"):
        metric = "综合成本率"
        if "非车险" in text:
            line = "非车险"
        elif "车险" in text:
            line = "车险"
    elif text.startswith("承保综合赔付率"):
        metric = "综合赔付率"
    elif text.startswith("承保综合费用率"):
        metric = "综合费用率"
    elif text.startswith("承保利润"):
        metric = "承保利润"
    elif text.startswith("净利润"):
        metric = "净利润"
    elif text.startswith("保险服务收入"):
        metric = "保险服务收入"
        if "非车险" in text:
            line = "非车险"
        elif "车险" in text:
            line = "车险"
    elif "汇率" in text:
        metric = "汇率"
    return {"metric": metric, "line": line, "raw": text}


def read_annual_sheet(workbook: Any) -> list[dict[str, Any]]:
    ws = workbook[ANNUAL_SHEET]
    records: list[dict[str, Any]] = []
    current_indicator = ""
    for row in ws.iter_rows(min_row=5, values_only=True):
        indicator_type = row[0]
        indicator = row[1]
        company_raw = row[2]
        if indicator and str(indicator).strip():
            current_indicator = str(indicator).strip()
        if company_raw is None:
            continue
        company = COMPANY_MAP.get(str(company_raw).strip())
        if company is None:
            continue
        if not current_indicator:
            continue
        norm = _norm_indicator(current_indicator)
        if norm["metric"] == "汇率":
            continue
        values = {
            period: _to_float(row[3 + index])
            for index, period in enumerate(VALUE_PERIODS)
        }
        growth = {
            period: _to_growth(row[10 + index])
            for index, period in enumerate(GROWTH_PERIODS)
        }
        note = str(row[15]).strip() if len(row) > 15 and row[15] else ""
        records.append(
            {
                "indicator_type": str(indicator_type).strip() if indicator_type else "",
                "indicator": norm["metric"],
                "line": norm["line"],
                "raw_indicator": norm["raw"],
                "company": company,
                "values": values,
                "growth": growth,
                "note": note,
            }
        )
    return records


def load_excel(path: str | Path | None = None) -> tuple[list[dict[str, Any]], Path]:
    excel_path = Path(path) if path else DEFAULT_EXCEL
    workbook = openpyxl.load_workbook(excel_path, data_only=True, read_only=True)
    records = read_annual_sheet(workbook)
    workbook.close()
    return records, excel_path
