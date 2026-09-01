"""Filter, match and dedupe database rows for the workbook."""

from __future__ import annotations

import math
from typing import Any, Optional


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_year(value: Any) -> Optional[int]:
    text = _clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def filter_database_rows(rows, allowed_scope_types, excluded_scope_types):
    """Keep rows that have a company/year and an allowed business scope type."""
    filtered = []
    for row in rows:
        company = _clean(row.get("company"))
        year = normalize_year(row.get("year"))
        scope_type = _clean(row.get("business_scope_type"))
        if not company or year is None or not scope_type:
            continue
        if scope_type in excluded_scope_types:
            continue
        if scope_type not in allowed_scope_types:
            continue
        filtered.append(row)
    return filtered


def match_metadata(metadata_rows, database_rows):
    """Match database rows to metadata by indicator_id first, then indicator_name."""
    matched = []
    for meta in metadata_rows:
        indicator_id = _clean(meta.get("indicator_id"))
        indicator_name = _clean(meta.get("indicator_name"))
        hits = []
        if indicator_id:
            hits = [row for row in database_rows if _clean(row.get("indicator_id")) == indicator_id]
        if not hits and indicator_name:
            hits = [row for row in database_rows if _clean(row.get("indicator_name")) == indicator_name]
        for row in hits:
            matched.append((meta, row))
    return matched


def _row_rank(row):
    scope_order = {"财险口径": 0, "特殊财险口径": 1}
    scope_type = _clean(row.get("business_scope_type")) or ""
    scope_rank = scope_order.get(scope_type, 2)
    try:
        confidence = float(_clean(row.get("confidence_score")) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    return scope_rank, -confidence


def dedupe_by_period(matched):
    """Pick one row per indicator/company/report_period.

    财险口径 is preferred over 特殊财险口径; ties are broken by extraction
    confidence.
    """
    best = {}
    for item in matched:
        meta, row = item
        period = _clean(row.get("report_period"))
        if period is None:
            continue
        key = (meta.get("indicator_id"), row.get("company"), period)
        if key not in best or _row_rank(row) < _row_rank(best[key][1]):
            best[key] = item
    return best


def parse_indicator_value(value):
    """Parse a database value into a number, or keep non-numeric text as-is."""
    text = _clean(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return text
