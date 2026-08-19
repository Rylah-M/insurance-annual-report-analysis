from __future__ import annotations

from typing import Any


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


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def _insight_block(insight: dict[str, Any]) -> str:
    lines = [
        f"**{insight['statement']}**",
        "",
        "证据链：",
    ]
    for item in insight.get("evidence", []):
        lines.append(f"- {item['metric']}：{item['value']}")
    if insight.get("comparison"):
        comparison = "；".join(f"{key} {value}" for key, value in insight["comparison"].items())
        lines.append(f"- 对标：{comparison}")
    for interpretation in insight.get("interpretation", []):
        lines.append(f"- 解读：{interpretation}")
    lines.append(f"- 置信度：{insight.get('confidence', 'medium')}")
    lines.append(f"- So What：{insight.get('so_what', '')}")
    return "\n".join(lines)


def build_markdown(analysis: dict[str, Any]) -> str:
    premium = analysis["premium"]
    structure = analysis["structure"]
    contribution = analysis["contribution"]
    profitability = analysis["profitability"]
    position = analysis["sunshine_position"]
    insights = analysis["insights"]
    signals = analysis["signals"]

    lines: list[str] = []
    lines.append("# 2025年上市公司产险经营分析")
    lines.append("")
    lines.append("> 由保险上市公司经营分析 Agent V2 自动生成（Excel → 深度经营分析 → Markdown/PDF）。")
    lines.append("")
    lines.append("## 一、执行摘要")
    lines.append("")
    lines.append("### 行业判断")
    lines.append("")
    industry = [
        f"2025 年上市公司产险原保险保费收入合计 {_num(premium['companies'][-1]['value'], 0)} 亿元，同比增长 {_pct(premium['industry_growth'])}。",
    ]
    for item in premium["lines"]:
        industry.append(
            f"{item['line']}：行业增速 {_pct(item['industry_growth'])}，阳光 {_pct(item['sunshine_growth'])}。"
        )
    cost_avg = profitability["sunshine_cost_avg"]
    industry.append(f"上市公司平均综合成本率 {_pct(cost_avg)}。")
    for index, item in enumerate(industry, 1):
        lines.append(f"{index}. {item}")
    lines.append("")
    lines.append("### 阳光判断")
    lines.append("")
    sunshine = []
    for item in position["strengths"] or ["暂无突出优势"]:
        sunshine.append(item)
    for item in position["weaknesses"] or ["暂无突出短板"]:
        sunshine.append(item)
    for index, item in enumerate(sunshine[:5], 1):
        lines.append(f"{index}. {item}")
    lines.append("")

    lines.append("## 二、整体保费与业务结构")
    lines.append("")
    lines.append("### 2.1 行业趋势")
    lines.append("")
    trend_industry = premium["trend_industry"]
    lines.append(
        f"上市公司原保险保费收入：2023 {_num(trend_industry['values']['2023'], 0)} 亿元 → "
        f"2024 {_num(trend_industry['values']['2024'], 0)} 亿元 → "
        f"2025 {_num(trend_industry['values']['2025'], 0)} 亿元；"
        f"2025 同比 {_pct(trend_industry['growth_25'])}，趋势判断：{trend_industry['direction']}。"
    )
    trend_sunshine = premium["trend_sunshine"]
    lines.append(
        f"阳光：2023 {_num(trend_sunshine['values']['2023'], 0)} 亿元 → "
        f"2024 {_num(trend_sunshine['values']['2024'], 0)} 亿元 → "
        f"2025 {_num(trend_sunshine['values']['2025'], 0)} 亿元；"
        f"2025 同比 {_pct(trend_sunshine['growth_25'])}，趋势判断：{trend_sunshine['direction']}。"
    )
    lines.append("")
    lines.append("### 2.2 上市公司对标")
    lines.append("")
    rows = []
    for item in premium["companies"]:
        rows.append([item["company"], _num(item["value"], 0), _pct(item["growth"])])
    lines.append(_md_table(["公司", "2025 保费（亿元）", "同比增速"], rows))
    peer = premium["peer"]
    lines.append("")
    lines.append(
        f"阳光保费增速 {_pct(peer['sunshine'])}，上市公司平均 {_pct(peer['average'])}，"
        f"阳光与平均差异 {_pt(peer['diff'])}，排名第 {peer['rank']} 位（共有 {6} 家可比公司）。"
    )
    lines.append("")
    lines.append("### 2.3 阳光表现")
    lines.append("")
    for item in premium["lines"]:
        lines.append(
            f"- {item['line']}：阳光增速 {_pct(item['sunshine_growth'])}，行业 {_pct(item['industry_growth'])}。"
        )
    lines.append("")
    lines.append("### 2.4 增长贡献")
    lines.append("")
    for scope, label in [("sunshine", "阳光"), ("listed", "上市公司合计")]:
        data = contribution[scope]
        if data["total_increment"] is None:
            lines.append(f"{label}：{data.get('note', '新增保费数据不足，无法计算贡献度。')}")
            continue
        lines.append(f"{label}新增保费约 {_num(data['total_increment'], 1)} 亿元：")
        for item in data["lines"]:
            lines.append(
                f"- {item['line']}增量 {_num(item['increment'], 1)} 亿元，贡献度 "
                + ("未披露" if item["contribution"] is None else f"{item['contribution'] * 100:.0f}%")
            )
    lines.append("")
    lines.append("### 2.5 核心结论")
    lines.append("")
    core_premium = [insight for insight in insights if insight["id"].startswith(("I01", "I02", "I06"))]
    if core_premium:
        for insight in core_premium[:3]:
            lines.append(_insight_block(insight))
            lines.append("")
    else:
        lines.append("当前数据暂未形成足够强的保费结构结论。")
        lines.append("")

    lines.append("## 三、承保盈利与增长质量")
    lines.append("")
    lines.append("### 3.1 承保利润")
    lines.append("")
    profit_rows = [
        [item["company"], _num(item["underwriting"]), _num(item["net_profit"])]
        for item in profitability["companies"]
    ]
    lines.append(_md_table(["公司", "承保利润（亿元）", "净利润（亿元）"], profit_rows))
    lines.append("")
    lines.append("### 3.2 综合成本率")
    lines.append("")
    cost_rows = [
        [item["company"], _pct(item["combined_ratio"]), _pt(item["cost_pt"])]
        for item in profitability["companies"]
    ]
    lines.append(_md_table(["公司", "综合成本率", "同比变化"], cost_rows))
    lines.append("")
    lines.append("### 3.3 赔付率 / 费用率")
    lines.append("")
    lines.append(
        f"阳光综合赔付率 {_pct(profitability['loss_ratio_sunshine'], 2)}，"
        f"综合费用率 {_pct(profitability['expense_ratio_sunshine'], 2)}。"
    )
    lines.append("")
    lines.append("### 3.4 规模 × 盈利矩阵")
    lines.append("")
    quality_rows = [
        [item["company"], _pct(item["premium_growth"]), _pt(item["cost_pt"]), item["quadrant"]]
        for item in analysis["quality_matrix"]
    ]
    lines.append(_md_table(["公司", "保费增速", "成本率变化", "判定"], quality_rows))
    lines.append("")
    lines.append("### 3.5 核心结论")
    lines.append("")
    core_profit = [insight for insight in insights if insight["id"] in ("I03", "I04", "I05")]
    if core_profit:
        for insight in core_profit:
            lines.append(_insight_block(insight))
            lines.append("")
    else:
        lines.append("当前数据暂未形成足够强的盈利结论。")
        lines.append("")

    lines.append("## 四、重点险种经营分析")
    lines.append("")
    key_signals = [signal for signal in signals if signal["type"] in ("增长引擎", "结构转型", "行业分化", "风险暴露")]
    if key_signals:
        for signal in key_signals[:6]:
            lines.append(f"- **{signal['type']}**：{signal['message']}")
    else:
        lines.append("当前数据暂未识别出值得单独展开的重点险种。")
    lines.append("")

    lines.append("## 五、阳光经营画像")
    lines.append("")
    lines.append("### 阳光做得好的地方")
    lines.append("")
    for item in position["strengths"] or ["暂无突出优势"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 阳光需要关注的地方")
    lines.append("")
    for item in position["weaknesses"] or ["暂无明显短板"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 阳光未来值得关注的业务")
    lines.append("")
    for item in position["opportunities"] or ["暂无明确机会"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### 阳光潜在风险")
    lines.append("")
    for item in position["risks"] or ["暂无重点风险"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 六、重点关注事项与待验证问题")
    lines.append("")
    lines.append("### 重点 Insight")
    lines.append("")
    for insight in insights[:5]:
        lines.append(_insight_block(insight))
        lines.append("")
    lines.append("### 待验证问题")
    lines.append("")
    for item in analysis["pending_questions"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 数据口径及说明")
    lines.append("")
    notes = list(dict.fromkeys(analysis["data_notes"])) or ["数据来源为产险对标 Excel。"]
    for note in notes:
        lines.append(f"- {note}")
    lines.append("")
    lines.append("## 图表说明")
    lines.append("")
    lines.append("- 图1：各公司保费增速（回答：谁跑赢行业）")
    lines.append("- 图2：阳光业务结构变化（回答：阳光增长来自哪里）")
    lines.append("- 图3：保费增速 × 综合成本率变化（回答：谁实现高质量增长）")
    lines.append("- 每张图均配一句话结论，详见 PDF 报告（图3为综合成本率同比变化）。")
    lines.append("")
    lines.append("## 附录：质检说明")
    lines.append("")
    lines.append("报告生成后由 Quality Critic Agent 独立审稿，详见运行日志。")
    return "\n".join(lines)
