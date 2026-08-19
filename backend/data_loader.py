from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_RESULT_PATH = PROJECT_ROOT / "database" / "database_result.csv"
DATABASE_CSV_PATH = PROJECT_ROOT / "data" / "database.csv"
DEFAULT_DATA_PATH = DATABASE_RESULT_PATH if DATABASE_RESULT_PATH.exists() else DATABASE_CSV_PATH

REQUIRED_COLUMNS = {
    "company",
    "year",
    "report_period",
    "indicator_id",
    "indicator_name",
    "indicator_value",
    "unit",
    "business_scope",
    "confidence_score",
}


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="gb18030")


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(column).strip() for column in df.columns]
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ValueError(f"database.csv 缺少必要字段: {missing_text}")

    cleaned = df.copy()

    text_columns = cleaned.select_dtypes(include=["object"]).columns
    for column in text_columns:
        cleaned[column] = cleaned[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )

    cleaned["year"] = pd.to_numeric(cleaned["year"], errors="coerce").astype("Int64")
    cleaned["indicator_value"] = pd.to_numeric(
        cleaned["indicator_value"], errors="coerce"
    )

    if "confidence_score" in cleaned.columns:
        cleaned["confidence_score"] = pd.to_numeric(
            cleaned["confidence_score"], errors="coerce"
        )

    return cleaned


@lru_cache(maxsize=4)
def load_database(path: str | None = None) -> pd.DataFrame:
    csv_path = Path(path) if path else DEFAULT_DATA_PATH
    if path is None:
        try:
            from database import load_dataframe

            return load_dataframe()
        except Exception:
            # SQLite 不可用时回退到 CSV，保持既有接口兼容。
            pass
    if not csv_path.exists():
        raise FileNotFoundError(f"未找到数据文件: {csv_path}")
    return _clean_dataframe(_read_csv(csv_path))


def dataframe_profile(df: pd.DataFrame) -> dict[str, Any]:
    duplicate_key_columns = [
        column
        for column in [
            "company",
            "year",
            "report_period",
            "indicator_id",
            "indicator_name",
            "business_scope",
        ]
        if column in df.columns
    ]

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "field_names": list(df.columns),
        "field_types": {column: str(dtype) for column, dtype in df.dtypes.items()},
        "company_count": int(df["company"].dropna().nunique()),
        "companies": sorted(df["company"].dropna().unique().tolist()),
        "year_count": int(df["year"].dropna().nunique()),
        "years": sorted(int(year) for year in df["year"].dropna().unique().tolist()),
        "indicator_count": int(df["indicator_name"].dropna().nunique()),
        "indicators": sorted(df["indicator_name"].dropna().unique().tolist()),
        "units": sorted(df["unit"].dropna().unique().tolist()),
        "nulls": {
            column: int(count) for column, count in df.isna().sum().to_dict().items()
        },
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_keys": int(df.duplicated(subset=duplicate_key_columns).sum())
        if duplicate_key_columns
        else 0,
        "available_values": int(df["indicator_value"].notna().sum()),
    }


def records_for_json(df: pd.DataFrame) -> list[dict[str, Any]]:
    return df.where(pd.notna(df), None).to_dict(orient="records")
