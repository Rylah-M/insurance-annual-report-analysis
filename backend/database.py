from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from data_loader import PROJECT_ROOT, _clean_dataframe, _read_csv


SQLITE_PATH = PROJECT_ROOT / "data" / "database.db"
SYNC_ENABLED = os.getenv("DATABASE_SYNC_ENABLED", "1") != "0"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS company_info (
    company_id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    market TEXT,
    business_scope TEXT,
    source_file TEXT
);

CREATE TABLE IF NOT EXISTS indicator_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id TEXT,
    company TEXT NOT NULL,
    year INTEGER,
    report_period TEXT,
    indicator_id TEXT,
    indicator_name TEXT,
    indicator_standard_name TEXT,
    indicator_value REAL,
    unit TEXT,
    business_scope TEXT,
    business_type TEXT,
    source_file TEXT,
    source_page TEXT,
    source_chunk_id TEXT,
    source_text TEXT,
    extraction_time TEXT,
    confidence_score REAL,
    review_status TEXT
);

CREATE INDEX IF NOT EXISTS idx_indicator_company_year
ON indicator_data (company, year);

CREATE INDEX IF NOT EXISTS idx_indicator_name
ON indicator_data (indicator_name);

CREATE TABLE IF NOT EXISTS report_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    year INTEGER NOT NULL,
    report_period TEXT,
    title TEXT,
    json_path TEXT,
    markdown_path TEXT,
    html_path TEXT,
    pdf_path TEXT,
    created_at TEXT
);
"""


def get_db_path() -> Path:
    return SQLITE_PATH


def _connection(db_path: Path | None = None) -> sqlite3.Connection:
    target = db_path or SQLITE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target))
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _now_text() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def init_schema(db_path: Path | None = None) -> None:
    with _connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)


def _company_market(company: str, df: pd.DataFrame) -> str | None:
    rows = df[df["company"] == company]
    if rows.empty:
        return None
    scopes = rows["business_scope"].dropna().astype(str).tolist()
    return "、".join(dict.fromkeys(scopes))[:300] if scopes else None


def sync_from_csv(
    csv_path: Path | None = None,
    db_path: Path | None = None,
) -> Path:
    source = csv_path or PROJECT_ROOT / "database" / "database_result.csv"
    if not source.exists():
        source = PROJECT_ROOT / "data" / "database.csv"
    df = _clean_dataframe(_read_csv(source))
    df = df[df["company"].notna() & df["company"].astype(str).str.strip().ne("")].copy()
    target = db_path or SQLITE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    with _connection(target) as connection:
        connection.execute("DROP TABLE IF EXISTS company_info")
        connection.execute("DROP TABLE IF EXISTS indicator_data")
        connection.execute("DROP TABLE IF EXISTS report_info")
        connection.executescript(SCHEMA_SQL)

        companies = sorted(df["company"].dropna().unique().tolist())
        company_rows = [
            (
                str(index + 1).zfill(3),
                company,
                "中国内地证券市场",
                _company_market(company, df),
                str(source),
            )
            for index, company in enumerate(companies)
        ]
        connection.executemany(
            """
            INSERT INTO company_info
            (company_id, company, market, business_scope, source_file)
            VALUES (?, ?, ?, ?, ?)
            """,
            company_rows,
        )

        company_ids = dict(connection.execute("SELECT company, company_id FROM company_info").fetchall())
        indicator_rows = []
        for record in df.to_dict(orient="records"):
            indicator_rows.append(
                (
                    company_ids.get(str(record.get("company")), ""),
                    record.get("company"),
                    record.get("year"),
                    record.get("report_period"),
                    record.get("indicator_id"),
                    record.get("indicator_name"),
                    record.get("indicator_standard_name"),
                    record.get("indicator_value"),
                    record.get("unit"),
                    record.get("business_scope"),
                    record.get("business_type"),
                    record.get("source_file"),
                    record.get("source_page"),
                    record.get("source_chunk_id"),
                    record.get("source_text"),
                    record.get("extraction_time"),
                    record.get("confidence_score"),
                    record.get("review_status"),
                )
            )
        connection.executemany(
            """
            INSERT INTO indicator_data
            (company_id, company, year, report_period, indicator_id, indicator_name,
             indicator_standard_name, indicator_value, unit, business_scope,
             business_type, source_file, source_page, source_chunk_id, source_text,
             extraction_time, confidence_score, review_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            indicator_rows,
        )

        report_rows = []
        for company in companies:
            for year in df[df["company"] == company]["year"].dropna().unique().tolist():
                report_rows.append(
                    (company, int(year), None, f"{company} {int(year)} 年经营分析报告", None, None, None, None, None)
                )
        connection.executemany(
            """
            INSERT INTO report_info
            (company, year, report_period, title, json_path, markdown_path,
             html_path, pdf_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            report_rows,
        )
    return target


def load_dataframe(db_path: Path | None = None) -> pd.DataFrame:
    target = db_path or SQLITE_PATH
    if not target.exists() and SYNC_ENABLED:
        sync_from_csv(db_path=target)
    if not target.exists():
        raise FileNotFoundError(f"未找到 SQLite 数据文件: {target}")
    query = "SELECT * FROM indicator_data"
    return _clean_dataframe(pd.read_sql_query(query, f"sqlite:///{target}"))


def save_report_artifact(
    company: str,
    year: int,
    report_period: str | None,
    title: str,
    files: dict[str, str],
) -> dict[str, Any]:
    with _connection() as connection:
        connection.execute(
            """
            UPDATE report_info
            SET report_period = ?, title = ?, json_path = ?, markdown_path = ?,
                html_path = ?, pdf_path = ?, created_at = ?
            WHERE company = ? AND year = ?
            """,
            (
                report_period,
                title,
                files.get("json"),
                files.get("markdown"),
                files.get("html"),
                files.get("pdf"),
                _now_text(),
                company,
                int(year),
            ),
        )
        if connection.total_changes == 0:
            connection.execute(
                """
                INSERT INTO report_info
                (company, year, report_period, title, json_path, markdown_path,
                 html_path, pdf_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    company,
                    int(year),
                    report_period,
                    title,
                    files.get("json"),
                    files.get("markdown"),
                    files.get("html"),
                    files.get("pdf"),
                    _now_text(),
                ),
            )
    return {
        "company": company,
        "year": int(year),
        "report_period": report_period,
        "title": title,
        "files": files,
    }


def list_report_info(company: str | None = None) -> list[dict[str, Any]]:
    with _connection() as connection:
        if company:
            rows = connection.execute(
                "SELECT * FROM report_info WHERE company = ? ORDER BY year DESC",
                (company,),
            ).fetchall()
        else:
            rows = connection.execute("SELECT * FROM report_info ORDER BY company, year DESC").fetchall()
    columns = ["id", "company", "year", "report_period", "title", "json_path", "markdown_path", "html_path", "pdf_path", "created_at"]
    return [dict(zip(columns, row)) for row in rows]


def list_reports(company: str | None = None) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "company": item["company"],
            "year": int(item["year"]),
            "report_period": item["report_period"],
            "title": item["title"],
            "generated": bool(item["created_at"]),
            "created_at": item["created_at"],
        }
        for item in list_report_info(company)
    ]
