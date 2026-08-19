from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect, String


pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


BLUE = colors.HexColor("#1F6FEB")
ORANGE = colors.HexColor("#E8730C")
GRAY = colors.HexColor("#94A3B8")
DARK = colors.HexColor("#172033")
MUTED = colors.HexColor("#667085")
LIGHT = colors.HexColor("#F8FAFC")


def _pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "未披露"
    return f"{value * 100:.{digits}f}%"


def _num(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "未披露"
    return f"{value:,.{digits}f}"


def _pt(value: float | None) -> str:
    if value is None:
        return "未披露"
    return f"{value * 100:+.1f}pt"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "cn_title", parent=base["Title"], fontName="STSong-Light", fontSize=18, alignment=TA_CENTER
        ),
        "h1": ParagraphStyle(
            "cn_h1", parent=base["Heading1"], fontName="STSong-Light", fontSize=15,
            spaceBefore=12, spaceAfter=8, textColor=DARK,
        ),
        "h2": ParagraphStyle(
            "cn_h2", parent=base["Heading2"], fontName="STSong-Light", fontSize=12,
            spaceBefore=8, spaceAfter=6, textColor=DARK,
        ),
        "body": ParagraphStyle(
            "cn_body", parent=base["BodyText"], fontName="STSong-Light", fontSize=10, leading=16
        ),
        "small": ParagraphStyle(
            "cn_small", parent=base["BodyText"], fontName="STSong-Light", fontSize=8.5, leading=13,
            textColor=MUTED,
        ),
        "conclusion": ParagraphStyle(
            "cn_conclusion", parent=base["BodyText"], fontName="STSong-Light", fontSize=9.5,
            leading=14, textColor=ORANGE,
        ),
    }


def _table(data: list[list[str]], widths: list[float] | None = None) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _bar_chart(
    title: str,
    categories: list[str],
    values: list[float | None],
    labels: list[str],
    *,
    highlight: str = "阳光",
    width: int = 460,
    height: int = 190,
) -> Drawing:
    drawing = Drawing(width, height + 30)
    chart_width = width - 60
    chart_height = height - 50
    max_value = max((value for value in values if value is not None), default=0) or 1
    min_value = min((value for value in values if value is not None), default=0)
    span = max(max_value - min_value, 0.001)
    drawing.add(String(0, height + 12, title, fontName="STSong-Light", fontSize=10, fillColor=DARK))
    slot = chart_width / max(len(categories), 1)
    bar_width = slot * 0.5
    for index, (category, value) in enumerate(zip(categories, values)):
        if value is None:
            continue
        color = ORANGE if category == highlight else GRAY if "合计" in category else BLUE
        bar_height = max(2, chart_height * (value - min_value) / span)
        x = 40 + index * slot + (slot - bar_width) / 2
        y = 20 + (chart_height - bar_height)
        drawing.add(Rect(x, y, bar_width, bar_height, fillColor=color, strokeColor=None))
        drawing.add(
            String(
                x + bar_width / 2,
                y - 11,
                labels[index] if index < len(labels) else "",
                fontName="STSong-Light",
                fontSize=8,
                fillColor=MUTED,
                textAnchor="middle",
            )
        )
        drawing.add(
            String(
                x + bar_width / 2,
                y + 2,
                str(value),
                fontName="STSong-Light",
                fontSize=8,
                fillColor=DARK,
                textAnchor="middle",
            )
        )
        drawing.add(
            String(
                x + bar_width / 2,
                4,
                category,
                fontName="STSong-Light",
                fontSize=8,
                fillColor=DARK,
                textAnchor="middle",
            )
        )
    return drawing


def _add_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("STSong-Light", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "2025年上市公司产险经营分析")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"第 {doc.page} 页")
    canvas.setStrokeColor(colors.HexColor("#E2E8F0"))
    canvas.line(2 * cm, 1.45 * cm, A4[0] - 2 * cm, 1.45 * cm)
    canvas.restoreState()


def build_pdf(analysis: dict[str, Any], output: Path, critic_summary: str = "") -> Path:
    styles = _styles()
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.2 * cm,
        title="2025年上市公司产险经营分析",
    )
    story: list[Any] = []
    story.append(Paragraph("2025年上市公司产险经营分析", styles["title"]))
    story.append(Paragraph("——保险上市公司经营分析 Agent V2", styles["body"]))
    story.append(Spacer(1, 10))

    premium = analysis["premium"]
    structure = analysis["structure"]
    contribution = analysis["contribution"]
    profitability = analysis["profitability"]
    position = analysis["sunshine_position"]
    insights = analysis["insights"]

    # 执行摘要
    story.append(Paragraph("一、执行摘要", styles["h1"]))
    story.append(Paragraph("行业判断", styles["h2"]))
    industry_lines = [
        f"2025 年上市公司产险原保险保费收入合计 {_num(premium['companies'][-1]['value'], 0)} 亿元，同比增长 {_pct(premium['industry_growth'])}。",
    ]
    for item in premium["lines"]:
        industry_lines.append(
            f"{item['line']}：行业增速 {_pct(item['industry_growth'])}，阳光 {_pct(item['sunshine_growth'])}。"
        )
    industry_lines.append(f"上市公司平均综合成本率 {_pct(profitability['sunshine_cost_avg'])}。")
    for index, line in enumerate(industry_lines, 1):
        story.append(Paragraph(f"{index}. {line}", styles["body"]))
    story.append(Paragraph("阳光判断", styles["h2"]))
    sunshine_lines = (position["strengths"] or ["暂无突出优势"]) + (position["weaknesses"] or ["暂无突出短板"])
    for index, line in enumerate(sunshine_lines[:5], 1):
        story.append(Paragraph(f"{index}. {line}", styles["body"]))

    # 保费与业务结构
    story.append(Paragraph("二、整体保费与业务结构", styles["h1"]))
    trend_industry = premium["trend_industry"]
    story.append(
        Paragraph(
            f"上市公司保费：2023 {_num(trend_industry['values']['2023'], 0)} → "
            f"2024 {_num(trend_industry['values']['2024'], 0)} → "
            f"2025 {_num(trend_industry['values']['2025'], 0)} 亿元，趋势：{trend_industry['direction']}。",
            styles["body"],
        )
    )
    premium_rows = [["公司", "2025 保费（亿元）", "同比增速"]]
    for item in premium["companies"]:
        premium_rows.append([item["company"], _num(item["value"], 0), _pct(item["growth"])])
    story.append(_table(premium_rows, widths=[4 * cm, 5 * cm, 5 * cm]))
    story.append(Spacer(1, 6))
    peer = premium["peer"]
    story.append(
        Paragraph(
            f"阳光保费增速 {_pct(peer['sunshine'])}，上市公司平均 {_pct(peer['average'])}，"
            f"差异 {_pt(peer['diff'])}，排名第 {peer['rank']} 位。",
            styles["body"],
        )
    )
    story.append(Spacer(1, 6))
    growth_chart = _bar_chart(
        "图1：各公司保费增速（回答：谁跑赢行业）",
        [item["company"] for item in premium["companies"]],
        [item["growth"] for item in premium["companies"]],
        [f"{_pct(item['growth'])}" for item in premium["companies"]],
    )
    story.append(growth_chart)
    story.append(
        Paragraph(
            f"图表结论：阳光增速 {_pct(peer['sunshine'])}，上市公司平均 {_pct(peer['average'])}，"
            f"阳光{'高于' if (peer['diff'] or 0) > 0 else '低于'}行业平均。",
            styles["conclusion"],
        )
    )
    story.append(Spacer(1, 8))
    structure_rows = [["险种", "2024占比", "2025占比", "变化"]]
    for item in structure["sunshine"]:
        structure_rows.append(
            [
                item["line"],
                _pct(item["previous"]),
                _pct(item["current"]),
                _pt(item["change"]),
            ]
        )
    story.append(Paragraph("图2：阳光业务结构变化（回答：阳光增长来自哪里）", styles["h2"]))
    story.append(_table(structure_rows, widths=[3.6 * cm, 3.8 * cm, 3.8 * cm, 3.8 * cm]))
    structure_change = next(
        (item for item in structure["sunshine"] if item["line"] == "车险"), None
    )
    structure_text = "阳光业务结构变化见上表"
    if structure_change and structure_change["change"] is not None:
        structure_text = f"图表结论：阳光车险占比变化 {_pt(structure_change['change'])}，业务结构出现调整。"
    story.append(Paragraph(structure_text, styles["conclusion"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("增长贡献", styles["h2"]))
    for scope, label in [("sunshine", "阳光"), ("listed", "上市公司合计")]:
        data = contribution[scope]
        if data["total_increment"] is None:
            story.append(Paragraph(f"{label}：{data.get('note', '新增保费数据不足。')}", styles["body"]))
            continue
        text = f"{label}新增保费约 {_num(data['total_increment'], 1)} 亿元："
        details = "；".join(
            f"{item['line']}贡献 "
            + ("未披露" if item["contribution"] is None else f"{item['contribution'] * 100:.0f}%")
            for item in data["lines"]
        )
        story.append(Paragraph(f"{text}{details}。", styles["body"]))

    # 承保盈利
    story.append(Paragraph("三、承保盈利与增长质量", styles["h1"]))
    profit_rows = [["公司", "承保利润（亿元）", "综合成本率", "同比变化", "净利润（亿元）"]]
    for item in profitability["companies"]:
        profit_rows.append(
            [
                item["company"],
                _num(item["underwriting"]),
                _pct(item["combined_ratio"]),
                _pt(item["cost_pt"]),
                _num(item["net_profit"]),
            ]
        )
    story.append(_table(profit_rows, widths=[3 * cm, 3.4 * cm, 3.4 * cm, 2.8 * cm, 3.4 * cm]))
    story.append(Spacer(1, 6))
    quality_rows = [["公司", "保费增速", "成本率变化", "判定"]]
    for item in analysis["quality_matrix"]:
        quality_rows.append(
            [item["company"], _pct(item["premium_growth"]), _pt(item["cost_pt"]), item["quadrant"]]
        )
    story.append(_table(quality_rows, widths=[3 * cm, 4 * cm, 4 * cm, 4.5 * cm]))
    story.append(Spacer(1, 8))
    cost_pt_chart = _bar_chart(
        "图3：各公司综合成本率同比变化（pt，回答：谁实现高质量增长）",
        [item["company"] for item in profitability["companies"]],
        [item["cost_pt"] for item in profitability["companies"]],
        [f"{_pt(item['cost_pt'])}" for item in profitability["companies"]],
    )
    story.append(cost_pt_chart)
    sunshine_cost_pt = next(
        (item["cost_pt"] for item in profitability["companies"] if item["company"] == "阳光"),
        None,
    )
    story.append(
        Paragraph(
            f"图表结论：阳光综合成本率同比 {_pt(sunshine_cost_pt)}，"
            "增长质量承压，需结合赔付率与费用率进一步定位来源。",
            styles["conclusion"],
        )
    )
    story.append(Spacer(1, 8))
    story.append(Paragraph("赔付率 / 费用率", styles["h2"]))
    story.append(
        Paragraph(
            f"阳光综合赔付率 {_pct(profitability['loss_ratio_sunshine'], 2)}，"
            f"综合费用率 {_pct(profitability['expense_ratio_sunshine'], 2)}。",
            styles["body"],
        )
    )

    # 重点险种
    story.append(Paragraph("四、重点险种经营分析", styles["h1"]))
    key_signals = [
        signal for signal in analysis["signals"]
        if signal["type"] in ("增长引擎", "结构转型", "行业分化", "风险暴露")
    ]
    for signal in key_signals[:6]:
        story.append(Paragraph(f"- {signal['type']}：{signal['message']}", styles["body"]))
    if not key_signals:
        story.append(Paragraph("当前数据暂未识别出值得单独展开的重点险种。", styles["body"]))

    # 阳光画像
    story.append(Paragraph("五、阳光经营画像", styles["h1"]))
    for title, items in [
        ("阳光做得好的地方", position["strengths"]),
        ("阳光需要关注的地方", position["weaknesses"]),
        ("阳光未来值得关注的业务", position["opportunities"]),
        ("阳光潜在风险", position["risks"]),
    ]:
        story.append(Paragraph(title, styles["h2"]))
        for item in items or ["暂无"]:
            story.append(Paragraph(f"- {item}", styles["body"]))

    # 重点 Insight
    story.append(Paragraph("六、重点 Insight 与待验证问题", styles["h1"]))
    for insight in insights[:5]:
        story.append(Paragraph(insight["statement"], styles["body"]))
        for evidence in insight.get("evidence", []):
            story.append(Paragraph(f"  证据：{evidence['metric']} = {evidence['value']}", styles["small"]))
        story.append(
            Paragraph(f"  So What：{insight.get('so_what', '')}（置信度 {insight.get('confidence')}）", styles["small"])
        )
    story.append(Paragraph("待验证问题", styles["h2"]))
    for question in analysis["pending_questions"]:
        story.append(Paragraph(f"- {question}", styles["body"]))

    # 数据口径
    story.append(Paragraph("数据口径及说明", styles["h1"]))
    notes = list(dict.fromkeys(analysis["data_notes"])) or ["数据来源为产险对标 Excel。"]
    for note in notes:
        story.append(Paragraph(f"- {note}", styles["small"]))
    if critic_summary:
        story.append(Paragraph("质检说明", styles["h1"]))
        story.append(Paragraph(critic_summary, styles["small"]))

    doc.build(story, onFirstPage=_add_footer, onLaterPages=_add_footer)
    return output
