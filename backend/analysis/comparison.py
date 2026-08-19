from __future__ import annotations

from typing import Any

import pandas as pd

from .statistics import descriptive_statistics, rank_metric, year_over_year


INDICATOR_CATEGORIES = {
    "经营规模": {"保险服务收入", "原保险保费收入", "车险保费收入", "非车险保费收入", "农业保险保费", "健康险保费"},
    "盈利能力": {"净利润", "承保利润", "投资收益", "综合成本率", "综合赔付率", "综合费用率", "保费增长率"},
    "业务结构": {"车险保费收入", "非车险保费收入", "农业保险保费", "健康险保费"},
    "偿付能力": {"核心偿付能力充足率", "综合偿付能力充足率"},
    "资产负债": {"总资产", "投资资产", "保险合同负债", "未决赔款准备金"},
}


def compare_indicator(
    df: pd.DataFrame, indicator_name: str, year: int | None = None
) -> dict[str, Any]:
    metric_df = df[df["indicator_name"] == indicator_name].copy()
    if year is not None:
        metric_df = metric_df[metric_df["year"] == year]

    values = []
    for row in metric_df.sort_values(["year", "company"]).itertuples():
        values.append(
            {
                "company": row.company,
                "year": int(row.year),
                "indicator": row.indicator_name,
                "value": None
                if pd.isna(row.indicator_value)
                else float(row.indicator_value),
                "unit": row.unit,
                "business_scope": row.business_scope
                if isinstance(row.business_scope, str)
                else None,
                "review_status": row.review_status
                if hasattr(row, "review_status")
                else None,
            }
        )

    return {
        "indicator": indicator_name,
        "year": year,
        "values": values,
        "statistics": descriptive_statistics(metric_df),
        "ranking": rank_metric(metric_df, indicator_name),
        "chart": {
            "type": "bar",
            "xAxis": [item["company"] for item in values],
            "series": [
                {
                    "name": indicator_name,
                    "data": [item["value"] for item in values],
                    "unit": values[0]["unit"] if values else None,
                }
            ],
        },
    }


def company_overview(
    df: pd.DataFrame, company: str, year: int | None = None
) -> dict[str, Any]:
    company_df = df[df["company"] == company].copy()
    if year is not None:
        company_df = company_df[company_df["year"] == year]

    metrics: dict[str, Any] = {}
    categories: dict[str, list[dict[str, Any]]] = {
        category: [] for category in INDICATOR_CATEGORIES
    }

    for row in company_df.sort_values(["indicator_id", "indicator_name"]).itertuples():
        metric = {
            "indicator_id": row.indicator_id,
            "indicator": row.indicator_name,
            "value": None if pd.isna(row.indicator_value) else float(row.indicator_value),
            "unit": row.unit,
            "business_scope": row.business_scope
            if isinstance(row.business_scope, str)
            else None,
            "confidence_score": None
            if not hasattr(row, "confidence_score") or pd.isna(row.confidence_score)
            else float(row.confidence_score),
            "review_status": row.review_status if hasattr(row, "review_status") else None,
        }
        metrics[row.indicator_name] = {
            "value": metric["value"],
            "unit": metric["unit"],
            "business_scope": metric["business_scope"],
        }
        for category, names in INDICATOR_CATEGORIES.items():
            if row.indicator_name in names:
                categories[category].append(metric)

    return {
        "company": company,
        "year": year,
        "metric_count": int(company_df["indicator_name"].nunique()),
        "available_value_count": int(company_df["indicator_value"].notna().sum()),
        "metrics": metrics,
        "categories": categories,
    }


def report_snapshot(df: pd.DataFrame, company: str, year: int) -> dict[str, Any]:
    overview = company_overview(df, company, year)
    comparison: dict[str, Any] = {}
    for indicator_name in overview["metrics"]:
        metric_comparison = compare_indicator(df, indicator_name, year)
        ranking = metric_comparison["ranking"]
        own_rank = next((item for item in ranking if item["company"] == company), None)
        comparison[indicator_name] = own_rank

    return {
        "company": company,
        "year": year,
        "metrics": overview["metrics"],
        "comparison": comparison,
    }


def trend_data(df: pd.DataFrame, company: str, indicator_name: str) -> dict[str, Any]:
    rows = year_over_year(df, company, indicator_name)
    return {
        "company": company,
        "indicator": indicator_name,
        "values": rows,
        "chart": {
            "type": "line",
            "xAxis": [item["year"] for item in rows],
            "series": [
                {
                    "name": indicator_name,
                    "data": [item["value"] for item in rows],
                    "unit": rows[0]["unit"] if rows else None,
                }
            ],
        },
    }
