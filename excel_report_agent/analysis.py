from __future__ import annotations

from typing import Any

from .excel_reader import LISTED_COMPANIES


CURRENT = "2025"
PREVIOUS = "2024"
PREV2 = "2023"

METRICS = [
    "原保险保费收入",
    "综合成本率",
    "承保利润",
    "净利润",
    "综合赔付率",
    "综合费用率",
    "保险服务收入",
]
LINES = ["整体", "车险", "非车险", "非车非保证险"]


def find_record(
    records: list[dict[str, Any]],
    metric: str,
    company: str,
    line: str = "整体",
) -> dict[str, Any] | None:
    for record in records:
        if (
            record["indicator"] == metric
            and record["company"] == company
            and record["line"] == line
        ):
            return record
    return None


def _growth(
    record: dict[str, Any] | None,
    current: str = CURRENT,
    previous: str = PREVIOUS,
) -> float | None:
    if record is None:
        return None
    if record["growth"].get(current) is not None:
        return record["growth"][current]
    current_value = record["values"].get(current)
    previous_value = record["values"].get(previous)
    if current_value is None or previous_value in (None, 0):
        return None
    return current_value / previous_value - 1


def _pt_change(record: dict[str, Any] | None, current: str = CURRENT) -> float | None:
    if record is None:
        return None
    return record["growth"].get(current)


def _value(record: dict[str, Any] | None, period: str) -> float | None:
    if record is None:
        return None
    return record["values"].get(period)


def build_model(records: list[dict[str, Any]]) -> dict[str, Any]:
    model: dict[str, Any] = {"records": records}
    for metric in METRICS:
        model[metric] = {}
        for line in LINES:
            model[metric][line] = {
                company: find_record(records, metric, company, line)
                for company in LISTED_COMPANIES + ["阳光", "上市公司合计"]
            }

    # 分险种行业合计：优先 Excel，缺失时用上市公司可取值汇总计算
    def aggregate_growth(line: str) -> float | None:
        excel_record = model["原保险保费收入"][line]["上市公司合计"]
        if excel_record and excel_record["growth"].get(CURRENT) is not None:
            return excel_record["growth"][CURRENT]
        current_sum, previous_sum, count = 0.0, 0.0, 0
        for company in LISTED_COMPANIES:
            record = model["原保险保费收入"][line][company]
            current_value = _value(record, CURRENT)
            previous_value = _value(record, PREVIOUS)
            if current_value is None or previous_value is None:
                continue
            current_sum += current_value
            previous_sum += previous_value
            count += 1
        if count < 2 or previous_sum == 0:
            return None
        return current_sum / previous_sum - 1

    def aggregate_values(line: str) -> tuple[float | None, float | None]:
        current_sum, previous_sum = 0.0, 0.0
        count = 0
        for company in LISTED_COMPANIES:
            record = model["原保险保费收入"][line][company]
            current_value = _value(record, CURRENT)
            previous_value = _value(record, PREVIOUS)
            if current_value is None or previous_value is None:
                continue
            current_sum += current_value
            previous_sum += previous_value
            count += 1
        if count < 2:
            return None, None
        return current_sum, previous_sum

    model["aggregate_growth"] = {
        line: aggregate_growth(line) for line in ["车险", "非车险", "非车非保证险"]
    }
    model["aggregate_values"] = {
        line: aggregate_values(line) for line in ["车险", "非车险", "非车非保证险"]
    }
    return model


def company_growth(
    model: dict[str, Any],
    metric: str,
    company: str,
    line: str = "整体",
) -> float | None:
    if company == "上市公司合计" and metric == "原保险保费收入":
        if line == "整体":
            return _growth(model[metric][line][company])
        return model["aggregate_growth"].get(line)
    return _growth(model[metric][line][company])


def company_value(
    model: dict[str, Any],
    metric: str,
    company: str,
    line: str = "整体",
    period: str = CURRENT,
) -> float | None:
    if company == "上市公司合计" and metric == "原保险保费收入":
        values = model["aggregate_values"].get(line)
        if values:
            return values[0] if period == CURRENT else values[1]
    return _value(model[metric][line][company], period)


def peer_stats(
    model: dict[str, Any],
    metric: str,
    line: str = "整体",
    use_growth: bool = True,
) -> dict[str, Any]:
    values: list[tuple[str, float]] = []
    for company in LISTED_COMPANIES:
        value = (
            company_growth(model, metric, company, line)
            if use_growth
            else company_value(model, metric, company, line)
        )
        if value is not None:
            values.append((company, value))
    sunshine = (
        company_growth(model, metric, "阳光", line)
        if use_growth
        else company_value(model, metric, "阳光", line)
    )
    if not values:
        return {"sunshine": sunshine, "average": None, "min": None, "max": None, "rank": None, "diff": None}
    average = sum(value for _, value in values) / len(values)
    min_value = min(values, key=lambda item: item[1])
    max_value = max(values, key=lambda item: item[1])
    rank = (
        sum(1 for _, value in values if value > sunshine) + 1
        if sunshine is not None
        else None
    )
    return {
        "sunshine": sunshine,
        "average": average,
        "min": min_value[1],
        "min_company": min_value[0],
        "max": max_value[1],
        "max_company": max_value[0],
        "rank": rank,
        "diff": sunshine - average if sunshine is not None and average is not None else None,
    }


def trend_analysis(
    model: dict[str, Any],
    metric: str,
    company: str,
    line: str = "整体",
) -> dict[str, Any]:
    record = model[metric][line][company]
    values = {
        period: _value(record, period)
        for period in [PREV2, PREVIOUS, CURRENT]
    }
    growth_24 = (
        values[PREVIOUS] / values[PREV2] - 1
        if values[PREVIOUS] is not None and values[PREV2] not in (None, 0)
        else None
    )
    growth_25 = (
        values[CURRENT] / values[PREVIOUS] - 1
        if values[CURRENT] is not None and values[PREVIOUS] not in (None, 0)
        else None
    )
    direction = "数据不足"
    if growth_24 is not None and growth_25 is not None:
        if growth_25 > growth_24 + 0.02:
            direction = "增长动能增强"
        elif growth_24 > growth_25 + 0.02:
            direction = "增长动能减弱"
        elif growth_24 < 0 < growth_25:
            direction = "由负转正"
        elif growth_25 < 0 and growth_24 < 0:
            direction = "持续下降"
        else:
            direction = "整体平稳"
    return {
        "values": values,
        "growth_24": growth_24,
        "growth_25": growth_25,
        "direction": direction,
    }


def structure_analysis(model: dict[str, Any]) -> dict[str, Any]:
    lines = ["车险", "非车险", "非车非保证险"]
    result = {"sunshine": [], "listed": []}
    for scope in ("sunshine", "listed"):
        company = "阳光" if scope == "sunshine" else "上市公司合计"
        for line in lines:
            current = None
            previous = None
            total_current = company_value(model, "原保险保费收入", company, "整体", CURRENT)
            total_previous = company_value(model, "原保险保费收入", company, "整体", PREVIOUS)
            line_current = company_value(model, "原保险保费收入", company, line, CURRENT)
            line_previous = company_value(model, "原保险保费收入", company, line, PREVIOUS)
            if total_current not in (None, 0) and line_current is not None:
                current = line_current / total_current
            if total_previous not in (None, 0) and line_previous is not None:
                previous = line_previous / total_previous
            result[scope].append(
                {
                    "line": line,
                    "current": current,
                    "previous": previous,
                    "change": (
                        current - previous
                        if current is not None and previous is not None
                        else None
                    ),
                }
            )
    return result


def contribution_analysis(model: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for scope, company in [("sunshine", "阳光"), ("listed", "上市公司合计")]:
        total_current = company_value(model, "原保险保费收入", company, "整体", CURRENT)
        total_previous = company_value(model, "原保险保费收入", company, "整体", PREVIOUS)
        if total_current is None or total_previous is None or total_current == total_previous:
            result[scope] = {
                "total_increment": None,
                "lines": [],
                "note": "保费增量数据不足或接近持平，增长贡献分析意义有限。",
            }
            continue
        total_increment = total_current - total_previous
        if abs(total_increment) < 1:
            result[scope] = {
                "total_increment": None,
                "lines": [],
                "note": "保费增量接近持平，增长贡献分析意义有限。",
            }
            continue
        lines = []
        for line in ["车险", "非车险", "非车非保证险"]:
            current = company_value(model, "原保险保费收入", company, line, CURRENT)
            previous = company_value(model, "原保险保费收入", company, line, PREVIOUS)
            if current is None or previous is None:
                continue
            increment = current - previous
            lines.append(
                {
                    "line": line,
                    "increment": increment,
                    "contribution": increment / total_increment if total_increment else None,
                }
            )
        result[scope] = {"total_increment": total_increment, "lines": lines}
    return result


def quality_matrix(model: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for company in LISTED_COMPANIES + ["阳光"]:
        premium_growth = company_growth(model, "原保险保费收入", company, "整体")
        cost_pt = _pt_change(model["综合成本率"]["整体"][company])
        premium = company_value(model, "原保险保费收入", company, "整体")
        if premium_growth is None or cost_pt is None:
            rows.append(
                {
                    "company": company,
                    "premium_growth": premium_growth,
                    "cost_pt": cost_pt,
                    "quadrant": "数据不足",
                    "judgement": "数据不足，暂不判定",
                }
            )
            continue
        if premium_growth > 0 and cost_pt < 0:
            quadrant = "高质量增长"
            judgement = "规模增长与承保质量同步改善。"
        elif premium_growth > 0 and cost_pt > 0:
            quadrant = "增长质量承压"
            judgement = "规模增长但承保质量承压。"
        elif premium_growth < 0 and cost_pt < 0:
            quadrant = "主动优化/收缩"
            judgement = "规模收缩伴随成本率改善，可能存在主动压缩低质量业务的迹象（推测，待验证）。"
        else:
            quadrant = "双重承压"
            judgement = "规模和承保质量双重承压。"
        rows.append(
            {
                "company": company,
                "premium_growth": premium_growth,
                "cost_pt": cost_pt,
                "premium": premium,
                "quadrant": quadrant,
                "judgement": judgement,
            }
        )
    return rows


def cross_metric_linkage(model: dict[str, Any]) -> list[str]:
    notes = []
    sunshine_premium = company_growth(model, "原保险保费收入", "阳光", "整体")
    sunshine_cost_pt = _pt_change(model["综合成本率"]["整体"]["阳光"])
    sunshine_underwriting_growth = company_growth(model, "承保利润", "阳光", "整体")
    non_auto_growth = company_growth(model, "原保险保费收入", "阳光", "非车险")
    car_growth = company_growth(model, "原保险保费收入", "阳光", "车险")
    if sunshine_premium is not None and sunshine_cost_pt is not None:
        if sunshine_premium > 0 and sunshine_cost_pt > 0:
            notes.append("阳光保费增长与综合成本率上升并存，增长质量承压。")
        elif sunshine_premium > 0 and sunshine_cost_pt < 0:
            notes.append("阳光保费增长伴随成本率改善，规模与质量同步改善。")
    if sunshine_underwriting_growth is not None and sunshine_premium is not None:
        if sunshine_premium > 0 and sunshine_underwriting_growth < 0:
            notes.append("阳光保费增长但承保利润下降，规模增长未转化为承保盈利。")
    if non_auto_growth is not None and car_growth is not None:
        if non_auto_growth > car_growth + 0.02:
            notes.append("阳光非车增速明显高于车险，增长动能向非车倾斜。")
    return notes


def signals(model: dict[str, Any]) -> list[dict[str, Any]]:
    signals_list: list[dict[str, Any]] = []
    structure = structure_analysis(model)
    contribution = contribution_analysis(model)

    # A/B: 增长引擎与结构转型
    for scope, company in [("sunshine", "阳光"), ("listed", "上市公司合计")]:
        for item in contribution[scope]["lines"]:
            if item["contribution"] is not None and item["contribution"] >= 0.5:
                signals_list.append(
                    {
                        "type": "增长引擎",
                        "scope": scope,
                        "message": f"{company}整体保费增长主要由{item['line']}贡献（贡献度约{item['contribution'] * 100:.0f}%）。",
                        "confidence": "high",
                    }
                )
        for item in structure[scope]:
            if item["change"] is not None and abs(item["change"]) >= 0.02:
                direction = "提高" if item["change"] > 0 else "下降"
                signals_list.append(
                    {
                        "type": "结构转型",
                        "scope": scope,
                        "message": f"{company}的{item['line']}占比{direction}约{abs(item['change']) * 100:.1f}pt，业务结构发生变化。",
                        "confidence": "high",
                    }
                )

    # C/D/E: 质量矩阵与风险
    for row in quality_matrix(model):
        if row["quadrant"] == "高质量增长":
            signals_list.append(
                {
                    "type": "高质量增长",
                    "scope": row["company"],
                    "message": f"{row['company']}规模增长与承保质量同步改善。",
                    "confidence": "high",
                }
            )
        elif row["quadrant"] == "增长质量承压":
            signals_list.append(
                {
                    "type": "增长质量承压",
                    "scope": row["company"],
                    "message": f"{row['company']}保费增长但综合成本率上升，增长质量承压。",
                    "confidence": "high",
                }
            )
        elif row["quadrant"] == "双重承压":
            signals_list.append(
                {
                    "type": "风险暴露",
                    "scope": row["company"],
                    "message": f"{row['company']}保费下降且成本率上升，规模与盈利同步承压。",
                    "confidence": "high",
                }
            )

    # F: 行业分化
    for line in ["车险", "非车险", "非车非保证险"]:
        stats = peer_stats(model, "原保险保费收入", line)
        if stats["min"] is not None and stats["max"] is not None and stats["max"] - stats["min"] >= 0.2:
            signals_list.append(
                {
                    "type": "行业分化",
                    "scope": "行业",
                    "message": f"{line}业务上市公司增速分化明显：最高 {stats['max_company']} {stats['max'] * 100:.1f}%，最低 {stats['min_company']} {stats['min'] * 100:.1f}%。",
                    "confidence": "high",
                }
            )
    return signals_list


def sunshine_position(model: dict[str, Any]) -> dict[str, Any]:
    strengths: list[str] = []
    weaknesses: list[str] = []
    opportunities: list[str] = []
    risks: list[str] = []

    premium_growth = company_growth(model, "原保险保费收入", "阳光", "整体")
    cost_pt = _pt_change(model["综合成本率"]["整体"]["阳光"])
    underwriting_growth = company_growth(model, "承保利润", "阳光", "整体")
    underwriting = company_value(model, "承保利润", "阳光", "整体")
    cost = company_value(model, "综合成本率", "阳光", "整体")
    cost_avg = peer_stats(model, "综合成本率", "整体", use_growth=False)["average"]
    growth_avg = peer_stats(model, "原保险保费收入", "整体")["average"]
    if premium_growth is not None and growth_avg is not None:
        if premium_growth > growth_avg:
            strengths.append(
                f"阳光保费增速 {premium_growth * 100:.1f}%，高于上市公司平均 {growth_avg * 100:.1f}%。"
            )
        else:
            weaknesses.append(
                f"阳光保费增速 {premium_growth * 100:.1f}%，低于上市公司平均 {growth_avg * 100:.1f}%。"
            )
    if cost is not None and cost_avg is not None:
        if cost < cost_avg:
            strengths.append(
                f"阳光综合成本率 {cost * 100:.2f}%，优于上市公司平均 {cost_avg * 100:.2f}%。"
            )
        else:
            weaknesses.append(
                f"阳光综合成本率 {cost * 100:.2f}%，高于上市公司平均 {cost_avg * 100:.2f}%。"
            )
    if cost_pt is not None and cost_pt > 0.005:
        weaknesses.append(f"阳光综合成本率同比上升 {cost_pt * 100:.1f}pt，承保盈利能力承压。")
    if underwriting is not None and underwriting < 0:
        risks.append(f"阳光承保利润为 {underwriting:.1f} 亿元，处于承保亏损状态。")
    if underwriting_growth is not None and premium_growth is not None and premium_growth > 0 and underwriting_growth < 0:
        risks.append("阳光保费增长与承保利润下降并存，规模增长未转化为承保盈利。")

    structure = structure_analysis(model)
    for item in structure["sunshine"]:
        if item["line"] == "非车非保证险" and item["current"] is not None:
            opportunities.append(
                f"阳光非车非保证险占比 {item['current'] * 100:.1f}%，为结构性增长赛道，存在进一步扩张空间。"
            )
    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "opportunities": opportunities,
        "risks": risks,
    }


def _insight_priority(insight: dict[str, Any]) -> int:
    score = 0
    if insight["confidence"] == "high":
        score += 3
    if insight["sunshine_relevance"]:
        score += 3
    score += min(insight["magnitude"], 3)
    return score


def build_insights(model: dict[str, Any]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    premium_growth = company_growth(model, "原保险保费收入", "阳光", "整体")
    growth_avg = peer_stats(model, "原保险保费收入", "整体")["average"]
    non_auto_growth = company_growth(model, "原保险保费收入", "阳光", "非车险")
    car_growth = company_growth(model, "原保险保费收入", "阳光", "车险")
    cost = company_value(model, "综合成本率", "阳光", "整体")
    cost_pt = _pt_change(model["综合成本率"]["整体"]["阳光"])
    cost_avg = peer_stats(model, "综合成本率", "整体", use_growth=False)["average"]
    underwriting = company_value(model, "承保利润", "阳光", "整体")
    contribution = contribution_analysis(model)

    if premium_growth is not None and growth_avg is not None:
        diff = premium_growth - growth_avg
        insights.append(
            {
                "id": "I01",
                "statement": (
                    f"阳光保费增速 {premium_growth * 100:.1f}%，{'高于' if diff > 0 else '低于'}上市公司平均 {growth_avg * 100:.1f}%。"
                ),
                "evidence": [
                    {"metric": "阳光保费增速", "value": f"{premium_growth * 100:.1f}%"},
                    {"metric": "上市公司平均增速", "value": f"{growth_avg * 100:.1f}%"},
                ],
                "comparison": {"sunshine": f"{premium_growth * 100:.1f}%", "listed_average": f"{growth_avg * 100:.1f}%"},
                "interpretation": [
                    f"阳光增长表现{'相对较强' if diff > 0 else '相对偏弱'}，与行业平均的差异为 {diff * 100:.1f}pt。"
                ],
                "confidence": "high",
                "magnitude": abs(diff) * 100,
                "sunshine_relevance": True,
                "so_what": "阳光整体增长动能是强是弱，决定其市场份额与行业位置的变化方向。",
            }
        )

    if non_auto_growth is not None and car_growth is not None and non_auto_growth > car_growth:
        contribution_text = ""
        for item in contribution["sunshine"]["lines"]:
            if item["line"] == "非车险" and item["contribution"] is not None:
                contribution_text = f"非车险贡献了阳光新增保费的约 {item['contribution'] * 100:.0f}%。"
        insights.append(
            {
                "id": "I02",
                "statement": "阳光整体增长动能正在向非车业务转移。",
                "evidence": [
                    {"metric": "阳光非车保费增速", "value": f"{non_auto_growth * 100:.1f}%"},
                    {"metric": "阳光车险保费增速", "value": f"{car_growth * 100:.1f}%"},
                    {"metric": "非车增长贡献", "value": contribution_text or "数据不足"},
                ],
                "comparison": {"sunshine_non_auto": f"{non_auto_growth * 100:.1f}%", "sunshine_auto": f"{car_growth * 100:.1f}%"},
                "interpretation": ["非车增速明显高于车险，整体增长由非车业务带动。"],
                "confidence": "high",
                "magnitude": abs(non_auto_growth - car_growth) * 100,
                "sunshine_relevance": True,
                "so_what": "阳光未来增长对非车业务依赖度提高，需同步观察非车业务的承保质量。",
            }
        )

    if cost is not None and cost_avg is not None:
        diff = (cost - cost_avg) * 100
        insights.append(
            {
                "id": "I03",
                "statement": f"阳光综合成本率 {cost * 100:.2f}%，{'优于' if diff < 0 else '高于'}上市公司平均 {cost_avg * 100:.2f}%。",
                "evidence": [
                    {"metric": "阳光综合成本率", "value": f"{cost * 100:.2f}%"},
                    {"metric": "上市公司平均综合成本率", "value": f"{cost_avg * 100:.2f}%"},
                ],
                "comparison": {"sunshine": f"{cost * 100:.2f}%", "listed_average": f"{cost_avg * 100:.2f}%"},
                "interpretation": [f"阳光成本率与行业差异 {diff:.1f}pt，承保盈利能力{'相对占优' if diff < 0 else '相对承压'}。"],
                "confidence": "high",
                "magnitude": abs(diff),
                "sunshine_relevance": True,
                "so_what": "综合成本率决定承保盈利空间，是判断阳光增长质量的核心指标。",
            }
        )

    if cost_pt is not None and abs(cost_pt) >= 0.005:
        insights.append(
            {
                "id": "I04",
                "statement": f"阳光综合成本率同比{'上升' if cost_pt > 0 else '下降'} {abs(cost_pt) * 100:.1f}pt。",
                "evidence": [{"metric": "阳光综合成本率同比变化", "value": f"{cost_pt * 100:+.1f}pt"}],
                "comparison": {},
                "interpretation": [
                    "承保盈利能力有所承压。" if cost_pt > 0 else "承保质量有所改善。"
                ],
                "confidence": "high",
                "magnitude": abs(cost_pt) * 100,
                "sunshine_relevance": True,
                "so_what": "成本率变化方向决定阳光承保盈利趋势，需结合赔付率与费用率进一步定位来源。",
            }
        )

    if underwriting is not None and underwriting < 0:
        insights.append(
            {
                "id": "I05",
                "statement": f"阳光承保利润为 {underwriting:.1f} 亿元，处于承保亏损状态。",
                "evidence": [{"metric": "阳光承保利润", "value": f"{underwriting:.1f} 亿元"}],
                "comparison": {},
                "interpretation": ["阳光承保端出现亏损，规模增长尚未转化为承保盈利。"],
                "confidence": "high",
                "magnitude": 3,
                "sunshine_relevance": True,
                "so_what": "承保亏损叠加保费低增长，是管理层需要优先关注的经营风险。",
            }
        )

    for item in contribution["sunshine"]["lines"]:
        if item["contribution"] is not None and item["contribution"] >= 0.5:
            insights.append(
                {
                    "id": f"I06-{item['line']}",
                    "statement": f"阳光整体保费增长主要由{item['line']}贡献（约 {item['contribution'] * 100:.0f}%）。",
                    "evidence": [
                        {"metric": f"阳光{item['line']}增长贡献", "value": f"{item['contribution'] * 100:.0f}%"},
                    ],
                    "comparison": {},
                    "interpretation": ["整体增长来源集中，业务结构变化明显。"],
                    "confidence": "high",
                    "magnitude": item["contribution"] * 100,
                    "sunshine_relevance": True,
                    "so_what": "增长依赖单一业务时，需关注该业务的可持续性与承保质量。",
                }
            )

    for insight in insights:
        insight["priority"] = _insight_priority(insight)
    insights.sort(key=lambda item: item["priority"], reverse=True)
    return insights


def build_analysis_v2(records: list[dict[str, Any]]) -> dict[str, Any]:
    model = build_model(records)
    premium_growth = company_growth(model, "原保险保费收入", "阳光", "整体")
    industry_growth = company_growth(model, "原保险保费收入", "上市公司合计", "整体")
    cost = company_value(model, "综合成本率", "阳光", "整体")
    cost_avg = peer_stats(model, "综合成本率", "整体", use_growth=False)["average"]

    return {
        "report_period": "2025",
        "report_type": "保险上市公司经营分析 Agent V2",
        "model": model,
        "premium": {
            "industry_growth": industry_growth,
            "sunshine_growth": premium_growth,
            "companies": [
                {
                    "company": company,
                    "value": company_value(model, "原保险保费收入", company, "整体"),
                    "growth": company_growth(model, "原保险保费收入", company, "整体"),
                }
                for company in LISTED_COMPANIES + ["阳光", "上市公司合计"]
            ],
            "peer": peer_stats(model, "原保险保费收入", "整体"),
            "lines": [
                {
                    "line": line,
                    "industry_growth": company_growth(model, "原保险保费收入", "上市公司合计", line),
                    "sunshine_growth": company_growth(model, "原保险保费收入", "阳光", line),
                }
                for line in ["车险", "非车险", "非车非保证险"]
            ],
            "trend_sunshine": trend_analysis(model, "原保险保费收入", "阳光", "整体"),
            "trend_industry": trend_analysis(model, "原保险保费收入", "上市公司合计", "整体"),
        },
        "structure": structure_analysis(model),
        "contribution": contribution_analysis(model),
        "profitability": {
            "companies": [
                {
                    "company": company,
                    "underwriting": company_value(model, "承保利润", company, "整体"),
                    "combined_ratio": company_value(model, "综合成本率", company, "整体"),
                    "cost_pt": _pt_change(model["综合成本率"]["整体"][company]),
                    "net_profit": company_value(model, "净利润", company, "整体"),
                }
                for company in LISTED_COMPANIES + ["阳光", "上市公司合计"]
            ],
            "sunshine_cost": cost,
            "sunshine_cost_avg": cost_avg,
            "loss_ratio_sunshine": company_value(model, "综合赔付率", "阳光", "整体"),
            "expense_ratio_sunshine": company_value(model, "综合费用率", "阳光", "整体"),
        },
        "quality_matrix": quality_matrix(model),
        "cross_metrics": cross_metric_linkage(model),
        "signals": signals(model),
        "sunshine_position": sunshine_position(model),
        "insights": build_insights(model),
        "data_notes": [record["note"] for record in records if record.get("note")],
        "pending_questions": _pending_questions(model),
    }


def _pending_questions(model: dict[str, Any]) -> list[str]:
    questions: list[str] = []
    structure = structure_analysis(model)
    for item in structure["sunshine"]:
        if item["change"] is not None and abs(item["change"]) >= 0.02:
            questions.append(
                f"阳光{item['line']}占比变化明显（{item['change'] * 100:+.1f}pt），具体业务调整原因需结合公司年报经营披露进一步验证。"
            )
    quality = quality_matrix(model)
    for row in quality:
        if row["quadrant"] == "主动优化/收缩":
            questions.append(
                f"{row['company']}保费下降伴随成本率改善，是否属于主动压缩低质量业务需结合业务披露验证。"
            )
    sunshine_car_growth = company_growth(model, "原保险保费收入", "阳光", "车险")
    if sunshine_car_growth is not None and sunshine_car_growth < 0:
        questions.append(
            "阳光车险保费同比下降，具体是业务收缩、渠道调整还是市场竞争所致，需结合公司年报经营披露进一步验证。"
        )
    sunshine_cost_pt = _pt_change(model["综合成本率"]["整体"]["阳光"])
    if sunshine_cost_pt is not None and sunshine_cost_pt > 0.005:
        questions.append(
            "阳光综合成本率上升的来源（赔付率还是费用率）需进一步拆解，并核对披露口径差异。"
        )
    sunshine_underwriting = _value(model["承保利润"]["整体"]["阳光"], CURRENT)
    if sunshine_underwriting is not None and sunshine_underwriting < 0:
        questions.append(
            "阳光承保亏损的具体业务来源（分险种成本率、灾害或准备金影响）需结合年报披露进一步验证。"
        )
    if not questions:
        questions.append("当前数据暂未识别出需要外部资料验证的经营问题。")
    return questions
