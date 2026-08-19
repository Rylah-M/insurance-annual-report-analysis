from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from data_loader import load_database


REPORT_DIR = Path(__file__).resolve().parents[1] / "report" / "analysis_reports"

METRIC_GROUPS = {
    "业务规模": [
        "原保险保费收入",
        "车险保费收入",
        "非车险保费收入",
        "农业保险保费",
        "健康险保费",
    ],
    "盈利能力": [
        "综合成本率",
        "综合赔付率",
        "综合费用率",
        "承保利润",
        "净利润",
        "投资收益",
    ],
    "偿付能力": [
        "核心偿付能力充足率",
        "综合偿付能力充足率",
    ],
    "投资能力": [
        "投资资产",
        "投资资产规模",
        "投资收益",
    ],
}

CATEGORY_ORDER = ["业务规模", "盈利能力", "偿付能力", "投资能力"]

STYLE_CSS = """
body{font-family:"PingFang SC","Microsoft YaHei",Arial,sans-serif;color:#172033;background:#f5f7fb;margin:0;padding:28px}
.sheet{max-width:920px;margin:0 auto;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:36px 40px}
h1{font-size:24px;margin:0 0 6px}
.meta{color:#667085;font-size:13px;margin-bottom:22px}
h2{font-size:18px;border-left:4px solid #1f6feb;padding-left:10px;margin:28px 0 12px}
h3{font-size:15px;margin:18px 0 8px;color:#344054}
p{line-height:1.75;margin:8px 0}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:14px 0}
.kpi{border:1px solid #e2e8f0;border-radius:8px;padding:12px}
.kpi span{display:block;color:#667085;font-size:12px;margin-bottom:6px}
.kpi strong{font-size:16px}
.chart{background:#f8fafc;border:1px solid #edf1f6;border-radius:8px;padding:12px;margin:12px 0}
.chart img{display:block;width:100%;height:auto;aspect-ratio:7/3}
table{width:100%;border-collapse:collapse;margin:10px 0}
th,td{border-bottom:1px solid #edf1f6;padding:9px 10px;text-align:left;font-size:13px}
th{background:#f8fafc;color:#475467}
.risk{border:1px solid #fecaca;background:#fff1f2;border-radius:8px;padding:10px 12px;margin:8px 0;color:#b42318}
.muted{color:#667085;font-size:13px}
@media print{body{padding:0;background:#fff}.sheet{border:0;padding:0}}
""".strip()


def _now_text() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _clean_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _format_number(value: float | None, unit: str | None = None) -> str:
    if value is None:
        return "暂无数据"
    if unit == "%":
        return f"{value:,.2f}%"
    if unit in ("百万元", "万元", "亿元"):
        return f"{value:,.2f}{unit}"
    return f"{value:,.2f}"


def _format_premium(value: float | None, unit: str | None = None) -> str:
    if value is None:
        return "暂无数据"
    if unit == "百万元":
        return f"{value / 100:,.2f}亿元"
    if unit == "万元":
        return f"{value / 10000:,.2f}亿元"
    return _format_number(value, unit)


def _company_context(df: pd.DataFrame, company: str, year: int) -> dict[str, Any]:
    company_df = df[(df["company"] == company) & (df["year"] == int(year))].copy()
    if company_df.empty:
        raise ValueError(f"数据库中未找到 {company} {year} 年数据")
    company_df = company_df.sort_values(["indicator_id", "indicator_name"])

    metrics: dict[str, dict[str, Any]] = {}
    for row in company_df.itertuples():
        value = _clean_value(row.indicator_value)
        metrics[row.indicator_name] = {
            "indicator_id": row.indicator_id,
            "indicator": row.indicator_name,
            "value": value,
            "unit": row.unit if isinstance(row.unit, str) else None,
            "business_scope": row.business_scope
            if isinstance(row.business_scope, str)
            else None,
            "confidence_score": _clean_value(getattr(row, "confidence_score", None)),
            "source_text": row.source_text
            if isinstance(getattr(row, "source_text", None), str)
            else None,
            "review_status": getattr(row, "review_status", None),
        }

    periods = sorted(company_df["report_period"].dropna().astype(str).unique().tolist())
    return {
        "company": company,
        "year": int(year),
        "report_period": periods[-1] if periods else None,
        "metric_count": int(company_df["indicator_name"].nunique()),
        "available_value_count": int(company_df["indicator_value"].notna().sum()),
        "metrics": metrics,
        "companies": sorted(df["company"].dropna().unique().tolist()),
    }


def _share_text(
    numerator: float | None,
    denominator: float | None,
    numerator_name: str,
    denominator_name: str,
) -> str:
    if numerator is None or denominator is None or denominator == 0:
        return ""
    return f"{numerator_name}占{denominator_name}的{numerator / denominator * 100:.1f}%"


def _narrative(context: dict[str, Any]) -> list[dict[str, str]]:
    metrics = context["metrics"]
    company = context["company"]
    period_label = context["report_period"] or f"{context['year']}年"
    narratives: list[dict[str, str]] = []

    # 公司基本情况
    basic_lines = [
        f"{company}为本系统覆盖的上市财险公司，本报告基于 {period_label} 已提取的结构化指标数据生成。",
        f"当前数据来源为年报结构化 chunks，共提取 {context['metric_count']} 项指标，其中 {context['available_value_count']} 项具有有效数值。",
    ]
    narratives.append(
        {
            "section": "公司基本情况",
            "content": " ".join(basic_lines),
        }
    )

    # 业务规模
    premium = metrics.get("原保险保费收入", {}).get("value")
    car = metrics.get("车险保费收入", {}).get("value")
    non_car = metrics.get("非车险保费收入", {}).get("value")
    premium_unit = metrics.get("原保险保费收入", {}).get("unit")
    business_lines = []
    if premium is not None:
        business_lines.append(
            f"{company}{period_label}原保险保费收入为{_format_premium(premium, premium_unit)}。"
        )
    if car is not None:
        business_lines.append(f"车险保费收入为{_format_premium(car, metrics.get('车险保费收入', {}).get('unit'))}。")
    if non_car is not None:
        share = _share_text(non_car, premium, "非车险", "原保险保费收入")
        business_lines.append(
            f"非车险保费收入为{_format_premium(non_car, metrics.get('非车险保费收入', {}).get('unit'))}"
            + (f"，{share}" if share else "。")
        )
    if car is not None and non_car is not None and car + non_car > 0:
        business_lines.append(
            f"车险与非车险业务占比约为 {car / (car + non_car) * 100:.1f}% 与 {non_car / (car + non_car) * 100:.1f}%。"
        )
    for name in ("农业保险保费", "健康险保费"):
        value = metrics.get(name, {}).get("value")
        if value is not None:
            business_lines.append(
                f"{name}为{_format_premium(value, metrics.get(name, {}).get('unit'))}。"
            )
    if not business_lines:
        business_lines.append("当前数据库尚未收录该公司的业务规模指标。")
    narratives.append({"section": "业务规模分析", "content": " ".join(business_lines)})

    # 盈利能力
    cost = metrics.get("综合成本率", {}).get("value")
    profit_lines: list[str] = []
    if cost is not None:
        if cost < 100:
            profit_lines.append(
                f"公司综合成本率为{_format_number(cost, '%')}，低于100%承保盈亏平衡线，整体实现承保盈利。"
            )
        elif cost == 100:
            profit_lines.append(
                f"公司综合成本率为{_format_number(cost, '%')}，处于承保盈亏平衡点附近。"
            )
        else:
            profit_lines.append(
                f"公司综合成本率为{_format_number(cost, '%')}，高于100%，承保端存在一定承保亏损压力。"
            )
    for name in ("综合赔付率", "综合费用率"):
        value = metrics.get(name, {}).get("value")
        if value is not None:
            profit_lines.append(
                f"{name}为{_format_number(value, metrics.get(name, {}).get('unit'))}。"
            )
    for name in ("承保利润", "净利润"):
        value = metrics.get(name, {}).get("value")
        if value is not None:
            profit_lines.append(
                f"{name}为{_format_number(value, metrics.get(name, {}).get('unit'))}。"
            )
    if not any(name in metrics for name in ("综合成本率", "综合赔付率", "综合费用率", "承保利润", "净利润")):
        profit_lines.append("当前数据库尚未收录该公司的盈利能力指标。")
    narratives.append({"section": "盈利能力分析", "content": " ".join(profit_lines)})

    # 偿付能力
    solvency = metrics.get("综合偿付能力充足率", {}).get("value")
    core = metrics.get("核心偿付能力充足率", {}).get("value")
    solvency_lines: list[str] = []
    if solvency is not None:
        if solvency >= 200:
            level = "充足"
        elif solvency >= 150:
            level = "较为充足"
        else:
            level = "需要关注"
        solvency_lines.append(
            f"公司综合偿付能力充足率为{_format_number(solvency, '%')}，偿付能力{level}。"
        )
    if core is not None:
        solvency_lines.append(
            f"核心偿付能力充足率为{_format_number(core, '%')}。"
        )
    if not solvency_lines:
        solvency_lines.append("当前数据库尚未收录该公司的偿付能力指标。")
    narratives.append({"section": "偿付能力分析", "content": " ".join(solvency_lines)})

    # 投资能力
    investment_lines: list[str] = []
    for name in ("投资资产", "投资资产规模", "投资收益"):
        value = metrics.get(name, {}).get("value")
        if value is not None:
            investment_lines.append(
                f"{name}为{_format_number(value, metrics.get(name, {}).get('unit'))}。"
            )
    if not investment_lines:
        investment_lines.append("当前数据库尚未收录该公司的投资能力指标。")
    narratives.append({"section": "投资能力分析", "content": " ".join(investment_lines)})

    # 风险提示
    risks = [
        {
            "type": "missing_value",
            "indicator": name,
            "message": "该指标当前数据库未披露或未抽取到有效数值。",
        }
        for name, metric in metrics.items()
        if metric["value"] is None
    ]
    risks.extend(
        {
            "type": "low_confidence",
            "indicator": name,
            "message": "该指标抽取置信度偏低，建议人工复核。",
            "confidence_score": metric["confidence_score"],
        }
        for name, metric in metrics.items()
        if metric["confidence_score"] is not None and metric["confidence_score"] < 0.5
    )
    if risks:
        risk_text = "；".join(f"{item['indicator']}：{item['message']}" for item in risks[:6])
        narratives.append({"section": "风险与复核提示", "content": f"本报告识别到 {len(risks)} 项需关注事项：{risk_text}。"})
    return narratives


def build_report_data(df: pd.DataFrame, company: str, year: int) -> dict[str, Any]:
    context = _company_context(df, company, int(year))
    metrics = context["metrics"]
    period_label = context["report_period"] or f"{context['year']}年"

    premium = metrics.get("原保险保费收入", {}).get("value")
    car = metrics.get("车险保费收入", {}).get("value")
    non_car = metrics.get("非车险保费收入", {}).get("value")
    cost = metrics.get("综合成本率", {}).get("value")

    charts = {
        "业务结构占比": _svg_data_uri(
            _svg_donut(
                [
                    ("车险", car),
                    ("非车险", non_car),
                ]
            )
        ),
        "业务规模对比": _svg_data_uri(
            _svg_bar(
                "原保险保费收入与车险/非车险",
                ["原保险保费收入", "车险保费收入", "非车险保费收入"],
                [premium, car, non_car],
                unit="百万元",
            )
        ),
        "综合成本率构成": _svg_data_uri(
            _svg_bar(
                "综合成本率构成",
                ["综合成本率", "综合赔付率", "综合费用率"],
                [
                    cost,
                    metrics.get("综合赔付率", {}).get("value"),
                    metrics.get("综合费用率", {}).get("value"),
                ],
                unit="%",
            )
        ),
    }

    sections = []
    for category in CATEGORY_ORDER:
        indicators = [
            metrics[name]
            for name in METRIC_GROUPS[category]
            if name in metrics
        ]
        category_charts = []
        if category == "业务规模":
            category_charts = [
                {"name": "业务规模对比", "data": charts["业务规模对比"]},
                {"name": "业务结构占比", "data": charts["业务结构占比"]},
            ]
        elif category == "盈利能力":
            category_charts = [
                {"name": "综合成本率构成", "data": charts["综合成本率构成"]},
            ]
        sections.append(
            {
                "category": category,
                "indicators": indicators,
                "charts": category_charts,
            }
        )

    risks = [
        {
            "type": "missing_value",
            "indicator": name,
            "message": "该指标当前数据库未披露或未抽取到有效数值。",
        }
        for name, metric in metrics.items()
        if metric["value"] is None
    ]
    risks.extend(
        {
            "type": "low_confidence",
            "indicator": name,
            "message": "该指标抽取置信度偏低，建议人工复核。",
            "confidence_score": metric["confidence_score"],
        }
        for name, metric in metrics.items()
        if metric["confidence_score"] is not None and metric["confidence_score"] < 0.5
    )

    narratives = _narrative(context)
    key_findings = []
    if premium is not None:
        key_findings.append(f"原保险保费收入 {_format_premium(premium, metrics.get('原保险保费收入', {}).get('unit'))}")
    if cost is not None:
        key_findings.append(
            f"综合成本率 {_format_number(cost, '%')}（{'低于' if cost < 100 else '高于'}100%）"
        )
    solvency = metrics.get("综合偿付能力充足率", {}).get("value")
    if solvency is not None:
        key_findings.append(f"综合偿付能力充足率 {_format_number(solvency, '%')}")

    return {
        "generated_at": _now_text(),
        "company": company,
        "year": int(year),
        "report_period": context["report_period"],
        "title": f"{company} {period_label}经营分析报告",
        "summary": {
            "metric_count": context["metric_count"],
            "available_value_count": context["available_value_count"],
            "key_findings": key_findings,
        },
        "company_basic": {
            "company": company,
            "year": int(year),
            "report_period": context["report_period"],
            "market": "中国内地证券市场",
            "business_scope": next(
                (
                    metric.get("business_scope")
                    for metric in metrics.values()
                    if metric.get("business_scope")
                ),
                None,
            ),
        },
        "sections": sections,
        "narratives": narratives,
        "charts": charts,
        "risks": risks,
        "data_coverage": {
            "companies": context["companies"],
            "company_count": len(context["companies"]),
            "indicator_count": len(metrics),
        },
    }


def _render_markdown(data: dict[str, Any]) -> str:
    lines = [
        f"# {data['title']}",
        "",
        f"- 生成时间：{data['generated_at']}",
        f"- 公司：{data['company']}",
        f"- 年份：{data['year']}",
        f"- 报告期：{data['report_period'] or '全年'}",
        "",
        "## 摘要",
        "",
        f"共提取 {data['summary']['metric_count']} 项指标，其中 {data['summary']['available_value_count']} 项具有有效数值。",
        "",
        "关键发现：",
        "",
    ]
    for finding in data["summary"]["key_findings"]:
        lines.append(f"- {finding}")
    lines.append("")

    for section in data["sections"]:
        lines.extend(["## " + section["category"], ""])
        for indicator in section["indicators"]:
            lines.append(
                f"- {indicator['indicator']}：{_format_number(indicator['value'], indicator['unit'])}"
            )
        lines.append("")

    lines.extend(["## 分析结论", ""])
    for narrative in data["narratives"]:
        lines.append(f"### {narrative['section']}")
        lines.append("")
        lines.append(narrative["content"])
        lines.append("")

    lines.extend(["## 风险与复核提示", ""])
    if data["risks"]:
        for risk in data["risks"]:
            lines.append(f"- {risk['indicator']}：{risk['message']}")
    else:
        lines.append("当前暂无风险提示。")
    lines.extend(
        [
            "",
            "> 本报告由上市财险公司年报智能分析 Agent 自动生成，数据来自结构化指标库，仅供研究参考。",
        ]
    )
    return "\n".join(lines)


def _render_html(data: dict[str, Any]) -> str:
    metric_kpis = []
    for name in ("原保险保费收入", "综合成本率", "综合偿付能力充足率"):
        for section in data["sections"]:
            for indicator in section["indicators"]:
                if indicator["indicator"] == name:
                    metric_kpis.append(
                        f'<div class="kpi"><span>{name}</span><strong>{_format_number(indicator["value"], indicator["unit"])}</strong></div>'
                    )
                    break
            else:
                continue
            break
    kpi_html = "".join(metric_kpis) or kpi_html

    sections_html = ""
    for section in data["sections"]:
        rows = "".join(
            (
                "<tr>"
                f"<td>{indicator['indicator']}</td>"
                f"<td>{_format_number(indicator['value'], indicator['unit'])}</td>"
                f"<td>{indicator.get('business_scope') or '-'}</td>"
                f"<td>{indicator.get('confidence_score') if indicator.get('confidence_score') is not None else '-'}</td>"
                "</tr>"
            )
            for indicator in section["indicators"]
        )
        chart_html = ""
        for chart in section["charts"]:
            svg_uri = data["charts"].get(chart["name"], "")
            if svg_uri:
                chart_html += (
                    f'<div class="chart"><h3>{chart["name"]}</h3>'
                    f'<img src="{svg_uri}" alt="{chart["name"]}" /></div>'
                )
        sections_html += f"""
        <h2>{section['category']}</h2>
        <table><thead><tr><th>指标</th><th>数值</th><th>业务口径</th><th>置信度</th></tr></thead>
        <tbody>{rows}</tbody></table>
        {chart_html}
        """

    narratives_html = "".join(
        f"<h3>{item['section']}</h3><p>{item['content']}</p>" for item in data["narratives"]
    )
    risks_html = "".join(
        f'<div class="risk">{risk["indicator"]}：{risk["message"]}</div>' for risk in data["risks"]
    ) or '<p class="muted">当前暂无风险提示。</p>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{data['title']}</title>
<style>{STYLE_CSS}</style>
</head>
<body>
<div class="sheet">
<h1>{data['title']}</h1>
<div class="meta">生成时间：{data['generated_at']} · 报告期：{data['report_period'] or data['year']} · 由年报智能分析 Agent 自动生成</div>
<div class="kpis">{kpi_html}</div>
<h2>摘要</h2>
<p>共提取 {data['summary']['metric_count']} 项指标，其中 {data['summary']['available_value_count']} 项具有有效数值。关键发现：{'；'.join(data['summary']['key_findings']) or '暂无'}</p>
{sections_html}
<h2>分析结论</h2>
{narratives_html}
<h2>风险与复核提示</h2>
{risks_html}
<p class="muted">本报告由上市财险公司年报智能分析 Agent 自动生成，数据来自结构化指标库，仅供研究参考。</p>
</div>
</body>
</html>
"""


def _b64(text: str) -> str:
    import base64

    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _svg_data_uri(svg: str) -> str:
    return f"data:image/svg+xml;base64,{_b64(svg)}"


def _svg_common(width: int = 560, height: int = 240) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Arial, sans-serif">'


def _svg_bar(title: str, labels: list[str], values: list[float | None], unit: str | None = None) -> str:
    numbers = [value if value is not None else 0 for value in values]
    max_value = max(numbers) if numbers else 1
    max_value = max_value or 1
    width, height = 560, 240
    left, right, top, bottom = 64, 16, 46, 46
    chart_w = width - left - right
    chart_h = height - top - bottom
    bar_w = chart_w / max(len(values), 1) * 0.56
    bars = []
    for index, (label, value) in enumerate(zip(labels, values)):
        display = "" if value is None else f"{value:,.1f}{unit or ''}"
        bar_h = max(2, chart_h * (value or 0) / max_value)
        x = left + index * (chart_w / max(len(values), 1)) + (chart_w / max(len(values), 1) - bar_w) / 2
        y = top + chart_h - bar_h
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="3" fill="#1f6feb"/>'
            f'<text x="{x + bar_w / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle" font-size="11" fill="#475467">{display}</text>'
            f'<text x="{x + bar_w / 2:.1f}" y="{height - 20:.1f}" text-anchor="middle" font-size="12" fill="#172033">{label}</text>'
        )
    return (
        _svg_common(width, height)
        + f'<text x="{left}" y="24" font-size="14" font-weight="bold" fill="#172033">{title}</text>'
        + "".join(bars)
        + "</svg>"
    )


def _svg_line(title: str, points: list[float | None], labels: list[str], unit: str | None = None) -> str:
    numbers = [point if point is not None else 0 for point in points]
    max_value = max(numbers) if numbers else 1
    min_value = min(numbers) if numbers else 0
    max_value = max_value or 1
    width, height = 560, 240
    left, right, top, bottom = 64, 16, 46, 46
    chart_w = width - left - right
    chart_h = height - top - bottom
    span = (max_value - min_value) or 1
    coordinates = []
    for index, point in enumerate(points):
        if point is None:
            continue
        x = left + (chart_w * index / max(len(points) - 1, 1))
        y = top + chart_h - chart_h * (point - min_value) / span
        coordinates.append((x, y))
    if not coordinates:
        return _svg_bar(title, labels, points, unit)
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordinates)
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#0f766e"/><text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-size="11" fill="#475467">{value:,.1f}{unit or ""}</text>'
        for (x, y), value in zip(coordinates, points)
        if value is not None
    )
    labels_html = "".join(
        f'<text x="{left + chart_w * index / max(len(labels) - 1, 1):.1f}" y="{height - 20:.1f}" text-anchor="middle" font-size="12" fill="#172033">{label}</text>'
        for index, label in enumerate(labels)
    )
    return (
        _svg_common(width, height)
        + f'<text x="{left}" y="24" font-size="14" font-weight="bold" fill="#172033">{title}</text>'
        + f'<polyline points="{polyline}" fill="none" stroke="#0f766e" stroke-width="3"/>'
        + dots
        + labels_html
        + "</svg>"
    )


def _svg_donut(items: list[tuple[str, float | None]]) -> str:
    values = [value for _, value in items if value is not None and value > 0]
    labels = [label for label, value in items if value is not None and value > 0]
    total = sum(values) or 1
    cx, cy = 160, 120
    ring_radius = 70
    ring_width = 36
    import math

    circumference = 2 * math.pi * ring_radius
    segments = []
    legend = []
    colors = ["#1f6feb", "#0f766e", "#f59e0b", "#64748b"]
    cumulative = 0.0
    for index, (label, value) in enumerate(zip(labels, values)):
        color = colors[index % len(colors)]
        dash = value / total * circumference
        gap = max(circumference - dash, 0.01)
        start_angle = 360 * cumulative / total
        segments.append(
            f'<circle cx="{cx}" cy="{cy}" r="{ring_radius}" fill="none" stroke="{color}" '
            f'stroke-width="{ring_width}" stroke-dasharray="{dash:.2f} {gap:.2f}" '
            f'transform="rotate({start_angle - 90:.2f} {cx} {cy})"/>'
        )
        legend.append(
            f'<text x="300" y="{80 + index * 26}" font-size="13" fill="#172033">'
            f'<tspan fill="{color}">●</tspan> '
            f"{label} {value / total * 100:.1f}%</text>"
        )
        cumulative += value
    center = (
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="16" font-weight="bold" fill="#172033">合计</text>'
        f'<text x="{cx}" y="{cy + 20}" text-anchor="middle" font-size="13" fill="#667085">{total:,.1f}</text>'
    )
    return (
        _svg_common()
        + f'<text x="24" y="26" font-size="14" font-weight="bold" fill="#172033">业务结构占比</text>'
        + "".join(segments)
        + center
        + "".join(legend)
        + "</svg>"
    )


def _cos(angle: float) -> float:
    import math

    return math.cos(math.radians(angle))


def _sin(angle: float) -> float:
    import math

    return math.sin(math.radians(angle))


def generate_report_files(
    df: pd.DataFrame,
    company: str,
    year: int,
    output_dir: Path | None = None,
) -> dict[str, str]:
    data = build_report_data(df, company, year)
    target_dir = output_dir or REPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{company}_{year}"
    json_path = target_dir / f"{stem}.json"
    markdown_path = target_dir / f"{stem}.md"
    html_path = target_dir / f"{stem}.html"
    pdf_path = target_dir / f"{stem}.pdf"

    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(data), encoding="utf-8")
    html_path.write_text(_render_html(data), encoding="utf-8")

    files = {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
    }
    try:
        try:
            from .pdf_agent import build_pdf
        except ImportError:
            from pdf_agent import build_pdf

        build_pdf(data, str(pdf_path))
        files["pdf"] = str(pdf_path)
    except Exception:
        # PDF 依赖可选，缺失时不影响网页与 Markdown/HTML 报告。
        files["pdf"] = ""
    return files


def generate_report(company: str, year: int, output_dir: Path | None = None) -> dict[str, Any]:
    df = load_database()
    if company not in set(df["company"].dropna()):
        raise ValueError(f"公司不存在: {company}")
    if int(year) not in set(df["year"].dropna().astype(int)):
        raise ValueError(f"年份不存在: {year}")
    files = generate_report_files(df, company, int(year), output_dir)
    data = json.loads(Path(files["json"]).read_text(encoding="utf-8"))
    data["files"] = files
    return data
