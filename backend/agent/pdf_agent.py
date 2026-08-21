from __future__ import annotations

from pathlib import Path
from typing import Any


def _format_number(value: Any, unit: str | None = None) -> str:
    if value is None:
        return "暂无数据"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if unit == "%":
        return f"{number:,.2f}%"
    return f"{number:,.2f}"


def build_pdf(data: dict[str, Any], output_path: str | Path) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ChineseTitle",
        parent=styles["Title"],
        fontName="STSong-Light",
        fontSize=22,
        leading=28,
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "ChineseHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=15,
        leading=22,
        textColor=colors.HexColor("#1f6feb"),
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=12,
        leading=20,
    )

    doc = SimpleDocTemplate(
        str(output),
        pagesize=landscape(A4),
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=data.get("title", "经营分析报告"),
    )
    story = [
        Paragraph(data.get("title", "经营分析报告"), title_style),
        Spacer(1, 6),
        Paragraph(
            f"生成时间：{data.get('generated_at', '-')} · 报告期：{data.get('report_period') or data.get('year')}",
            body_style,
        ),
    ]

    kpi_names = [
        "原保险保费收入", "车险保费收入", "非车险保费收入", "综合成本率",
        "综合赔付率", "综合费用率", "承保利润", "净利润", "综合偿付能力充足率",
    ]
    metrics_by_name: dict[str, dict[str, Any]] = {}
    for section in data.get("sections", []):
        for indicator in section.get("indicators", []):
            metrics_by_name[str(indicator.get("indicator", "") or "")] = indicator
    kpi_rows = [["关键指标", "数值", "单位"]]
    for name in kpi_names:
        indicator = metrics_by_name.get(name)
        if indicator is None:
            continue
        kpi_rows.append(
            [
                name,
                _format_number(indicator.get("value"), indicator.get("unit")),
                str(indicator.get("unit") or "-"),
            ]
        )
    if len(kpi_rows) > 1:
        story.append(Paragraph("公司关键指标概览", heading_style))
        kpi_table = Table(kpi_rows, colWidths=[70 * mm, 70 * mm, 60 * mm])
        kpi_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d7dee8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(kpi_table)

    for section in data.get("sections", []):
        story.append(Paragraph(section["category"], heading_style))
        rows = [["指标", "数值", "业务口径"]]
        for indicator in section.get("indicators", []):
            rows.append(
                [
                    indicator.get("indicator", ""),
                    _format_number(indicator.get("value"), indicator.get("unit")),
                    indicator.get("business_scope") or "-",
                ]
            )
        table = Table(rows, colWidths=[52 * mm, 48 * mm, 120 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d7dee8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(table)

    trend_table_data = data.get("trend_table") or {}
    trend_years = trend_table_data.get("years") or []
    trend_rows = trend_table_data.get("rows") or []
    if trend_years and trend_rows:
        story.append(Paragraph("近年主要指标趋势", heading_style))
        header = ["指标"] + [str(year) for year in trend_years]
        table_rows = [header]
        for row in trend_rows:
            values = row.get("values", {})
            table_rows.append(
                [str(row.get("indicator", ""))]
                + [
                    (
                        f"{values[year]:,.2f}"
                        if year in values and values[year] is not None
                        else "-"
                    )
                    for year in trend_years
                ]
            )
        trend_table = Table(
            table_rows,
            colWidths=[70 * mm] + [30 * mm] * len(trend_years),
            repeatRows=1,
        )
        trend_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d7dee8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(trend_table)
    else:
        story.append(Paragraph("近年主要指标趋势", heading_style))
        story.append(
            Paragraph("当前数据库暂无可用的多年趋势数据。", body_style)
        )

    story.append(Paragraph("分析结论", heading_style))
    for narrative in data.get("narratives", []):
        story.append(Paragraph(narrative.get("section", ""), heading_style))
        for paragraph in str(narrative.get("content", "")).split("\n"):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), body_style))
        story.append(Spacer(1, 6))

    story.append(Paragraph("风险与复核提示", heading_style))
    if data.get("risks"):
        for risk in data["risks"]:
            story.append(
                Paragraph(
                    f"- {risk.get('indicator', '')}：{risk.get('message', '')}",
                    body_style,
                )
            )
    else:
        story.append(Paragraph("当前暂无风险提示。", body_style))
    seen_indicators: set[str] = set()
    appendix_rows = [["指标", "数值", "单位", "业务范围"]]
    for section in data.get("sections", []):
        for indicator in section.get("indicators", []):
            name = str(indicator.get("indicator", "") or "")
            if not name or name in seen_indicators:
                continue
            seen_indicators.add(name)
            appendix_rows.append(
                [
                    name,
                    _format_number(indicator.get("value"), indicator.get("unit")),
                    str(indicator.get("unit") or "-"),
                    str(indicator.get("business_scope") or "-"),
                ]
            )
    if len(appendix_rows) > 1:
        story.append(Paragraph("附录：指标明细", heading_style))
        appendix = Table(
            appendix_rows,
            colWidths=[70 * mm, 50 * mm, 30 * mm, 100 * mm],
            repeatRows=1,
        )
        appendix.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d7dee8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(appendix)
    story.append(
        Paragraph(
            "本报告由上市财险公司年报智能分析 Agent 自动生成，数据来自结构化指标库，仅供研究参考。",
            body_style,
        )
    )
    doc.build(story)
    return str(output)
