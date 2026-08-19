from __future__ import annotations

from typing import Any

import pandas as pd


LOWER_IS_BETTER_KEYWORDS = ("成本率", "赔付率", "费用率", "负债率")


def is_lower_better(indicator_name: str) -> bool:
    return any(keyword in indicator_name for keyword in LOWER_IS_BETTER_KEYWORDS)


def filter_metric(
    df: pd.DataFrame,
    indicator_name: str,
    year: int | None = None,
    unit: str | None = None,
) -> pd.DataFrame:
    metric_df = df[df["indicator_name"] == indicator_name].copy()
    if year is not None:
        metric_df = metric_df[metric_df["year"] == year]
    if unit is not None:
        metric_df = metric_df[metric_df["unit"] == unit]
    return metric_df


def descriptive_statistics(metric_df: pd.DataFrame) -> dict[str, Any]:
    available = metric_df[metric_df["indicator_value"].notna()].copy()
    units = available["unit"].dropna().unique().tolist()
    if available.empty:
        return {
            "count": 0,
            "unit": units[0] if len(units) == 1 else None,
            "max": None,
            "min": None,
            "mean": None,
            "median": None,
        }

    if len(units) > 1:
        return {
            "count": int(len(available)),
            "unit": None,
            "warning": "同一指标存在多个单位，未混合统计。",
        }

    values = available["indicator_value"]
    return {
        "count": int(len(available)),
        "unit": units[0] if units else None,
        "max": float(values.max()),
        "min": float(values.min()),
        "mean": float(values.mean()),
        "median": float(values.median()),
    }


def rank_metric(metric_df: pd.DataFrame, indicator_name: str) -> list[dict[str, Any]]:
    available = metric_df[metric_df["indicator_value"].notna()].copy()
    if available.empty:
        return []

    ascending = is_lower_better(indicator_name)
    available = available.sort_values(
        ["indicator_value", "company"], ascending=[ascending, True]
    )
    available["rank"] = (
        available["indicator_value"].rank(method="min", ascending=ascending).astype(int)
    )
    average = available["indicator_value"].mean()

    return [
        {
            "company": row.company,
            "year": int(row.year),
            "indicator": row.indicator_name,
            "value": float(row.indicator_value),
            "unit": row.unit,
            "rank": int(row.rank),
            "company_average_difference": float(row.indicator_value - average),
            "business_scope": row.business_scope
            if isinstance(row.business_scope, str)
            else None,
        }
        for row in available.itertuples()
    ]


def year_over_year(df: pd.DataFrame, company: str, indicator_name: str) -> list[dict[str, Any]]:
    metric_df = df[
        (df["company"] == company)
        & (df["indicator_name"] == indicator_name)
        & (df["indicator_value"].notna())
    ].copy()
    if metric_df.empty:
        return []

    metric_df = metric_df.sort_values("year")
    metric_df["previous_value"] = metric_df["indicator_value"].shift(1)
    metric_df["change"] = metric_df["indicator_value"] - metric_df["previous_value"]
    metric_df["change_rate"] = metric_df["change"] / metric_df["previous_value"] * 100

    rows: list[dict[str, Any]] = []
    for row in metric_df.itertuples():
        rows.append(
            {
                "year": int(row.year),
                "value": float(row.indicator_value),
                "unit": row.unit,
                "previous_value": None
                if pd.isna(row.previous_value)
                else float(row.previous_value),
                "change": None if pd.isna(row.change) else float(row.change),
                "change_rate": None
                if pd.isna(row.change_rate)
                else float(row.change_rate),
            }
        )
    return rows
