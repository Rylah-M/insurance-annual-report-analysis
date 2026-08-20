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
        fontSize=18,
        leading=24,
        alignment=1,
    )
    heading_style = ParagraphStyle(
        "ChineseHeading",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#1f6feb"),
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "ChineseBody",
        parent=styles["BodyText"],
        fontName="STSong-Light",
        fontSize=10,
        leading=16,
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

    for section in data.get("sections", []):
        story.append(Paragraph(section["category"], heading_style))
        rows = [["指标", "数值", "业务口径", "置信度"]]
        for indicator in section.get("indicators", []):
            rows.append(
                [
                    indicator.get("indicator", ""),
                    _format_number(indicator.get("value"), indicator.get("unit")),
                    indicator.get("business_scope") or "-",
                    (
                        f"{indicator.get('confidence_score'):.2f}"
                        if indicator.get("confidence_score") is not None
                        else "-"
                    ),
                ]
            )
        table = Table(rows, colWidths=[52 * mm, 48 * mm, 100 * mm, 30 * mm])
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

    story.append(Paragraph("分析结论", heading_style))
    for narrative in data.get("narratives", []):
        story.append(Paragraph(f"{narrative['section']}：{narrative['content']}", body_style))
        story.append(Spacer(1, 3))

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
    story.append(
        Paragraph(
            "本报告由上市财险公司年报智能分析 Agent 自动生成，数据来自结构化指标库，仅供研究参考。",
            body_style,
        )
    )
    doc.build(story)
    return str(output)
