from __future__ import annotations

from typing import Any

import pandas as pd

from .comparison import company_overview, compare_indicator


SECTION_INDICATORS = {
    "基础经营情况": ["原保险保费收入", "保险服务收入", "车险保费收入", "非车险保费收入"],
    "盈利能力": ["净利润", "承保利润", "综合成本率", "综合赔付率", "综合费用率", "投资收益"],
    "偿付能力": ["核心偿付能力充足率", "综合偿付能力充足率"],
    "风险分析": ["保费增长率", "保险合同负债", "未决赔款准备金"],
}


def _metric_payload(row: pd.Series) -> dict[str, Any]:
    value = row.get("indicator_value")
    return {
        "indicator_id": row.get("indicator_id"),
        "indicator": row.get("indicator_name"),
        "value": None if pd.isna(value) else float(value),
        "unit": row.get("unit"),
        "business_scope": None
        if pd.isna(row.get("business_scope"))
        else row.get("business_scope"),
        "confidence_score": None
        if pd.isna(row.get("confidence_score"))
        else float(row.get("confidence_score")),
        "review_status": row.get("review_status")
        if "review_status" in row.index
        else None,
    }


def company_report_data(df: pd.DataFrame, company: str, year: int) -> dict[str, Any]:
    company_df = df[(df["company"] == company) & (df["year"] == year)].copy()
    overview = company_overview(df, company, year)
    sections: dict[str, list[dict[str, Any]]] = {}

    for section, indicator_names in SECTION_INDICATORS.items():
        section_rows = company_df[company_df["indicator_name"].isin(indicator_names)]
        sections[section] = [_metric_payload(row) for _, row in section_rows.iterrows()]

    comparison = {}
    for indicator_name, metric in overview["metrics"].items():
        if metric["value"] is None:
            comparison[indicator_name] = None
            continue
        ranking = compare_indicator(df, indicator_name, year)["ranking"]
        comparison[indicator_name] = next(
            (item for item in ranking if item["company"] == company), None
        )

    risks = []
    for row in company_df.iterrows():
        metric = _metric_payload(row[1])
        if metric["value"] is None:
            risks.append(
                {
                    "type": "missing_value",
                    "indicator": metric["indicator"],
                    "message": "该指标当前数据库未披露或未抽取到有效数值。",
                }
            )
        elif metric["confidence_score"] is not None and metric["confidence_score"] < 0.5:
            risks.append(
                {
                    "type": "low_confidence",
                    "indicator": metric["indicator"],
                    "confidence_score": metric["confidence_score"],
                    "message": "该指标抽取置信度偏低，建议人工复核。",
                }
            )

    return {
        "company": company,
        "year": year,
        "summary": {
            "metric_count": overview["metric_count"],
            "available_value_count": overview["available_value_count"],
        },
        "sections": sections,
        "comparison": comparison,
        "risks": risks,
    }
