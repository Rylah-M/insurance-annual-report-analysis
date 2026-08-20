from __future__ import annotations

import json
import os
import re
from typing import Any

import pandas as pd

from data_loader import load_database
from agent.chunk_index import retrieve_chunks


COMPANY_ALIASES = {
    "人保": ["人保", "中国人保", "人民保险", "人保财险", "人保产险"],
    "太保": ["太保", "中国太保", "太平洋保险", "太平洋财险", "太保产险"],
    "太平": ["太平", "中国太平", "太平财险"],
    "平安": ["平安", "中国平安", "平安产险", "平安财险"],
    "阳光": ["阳光", "中国阳光", "阳光保险", "阳光财险", "阳光产险"],
    "众安": ["众安", "众安在线", "众安财险"],
}

CATEGORY_KEYWORDS = {
    "业务规模": ["保费", "业务规模", "原保险保费", "车险", "非车险", "农险", "健康险"],
    "盈利能力": ["盈利", "利润", "成本率", "赔付率", "费用率", "承保"],
    "偿付能力": ["偿付能力", "充足率", "偿付"],
    "投资能力": ["投资", "投资收益", "投资资产"],
}

ANALYSIS_KEYWORDS = (
    "变化", "分析", "趋势", "结构", "如何", "怎么样", "怎样", "发展", "风险",
    "优势", "劣势", "占比", "同比", "提升", "下降", "改善", "承压", "表现",
    "亮点", "评估", "解读", "怎么看", "经营", "业务结果", "业绩", "情况",
    "增长", "放缓", "原因", "影响", "机会", "挑战", "比较", "对比",
)

STRUCTURE_KEYWORDS = ("占比", "份额", "保费", "险种", "结构")

ANALYSIS_YEAR_RANGE = 3

ANALYSIS_SYSTEM_PROMPT = (
    "你是上市财险公司年报业务分析 Agent。用户通常问的是泛业务问题"
    "（业务结构、经营变化、趋势、优劣势、风险），而不是查某个指标数值。\n"
    "回答要求：\n"
    "1. 先给一句总体判断：业务整体是改善、承压还是结构变化明显。\n"
    "2. 围绕业务规模、业务结构、盈利能力、成本管控、偿付能力、市场地位组织回答，"
    "不要按指标逐条罗列。\n"
    "3. 每个要点 = 变化方向 + 数据佐证 + 一句话业务解读（这个变化意味着什么）。\n"
    "4. 重点讲结构性变化：车险/非车险占比变动、各险种增速差异、同比变化、市场份额。\n"
    "5. 数值与同比一律以【逐年指标】【同比变化】为准，不要用检索原文里的数字"
    "代替数据库口径。\n"
    "6. 叙述性内容（经营方针、变化原因、管理层解读、市场环境、风险因素）"
    "以【年报原文（知识库检索）】为准，并在引用时标注出处"
    "（如：年报·管理层讨论与分析）。\n"
    "7. 核心论断尽量直接引用检索到的年报原话（加引号），"
    "宁可引用原文也不要只堆砌数字；每个要点至少有一处原文引用。\n"
    "8. 用户追问具体原因/方针时，先直接回答方针或原因本身"
    "（如“高质量发展”“五篇大文章”“优化业务结构”等），"
    "再用数据与原文佐证，不要只罗列数据或复述上一轮内容。\n"
    "9. 若知识库未检索到相关原文，明确说明“年报原文知识库中未找到相关表述”，"
    "不要编造方针或原因。\n"
    "10. 只使用上下文中的数据；没有对比数据时明确说明“未提供该年数据”，"
    "不要推算或编造。\n"
    "11. 涉及金额时请按单位换算成亿元表述（100百万元 = 1亿元）。\n"
    "12. 全文 200-400 字，可用小标题和要点，但不要超过 4 个要点。\n"
    "例外：如果用户明确问某个具体指标数值（如“综合成本率是多少”），"
    "则直接回答数值、单位和口径，不展开分析。"
)

DIRECT_SYSTEM_PROMPT = (
    "你是上市财险公司年报智能分析 Agent。请根据提供的结构化指标上下文，"
    "用中文简洁、准确地回答用户问题。只使用上下文中出现的数据；"
    "如果上下文没有对应数据，请明确说明数据库中暂未收录。"
)


def _metric_records(df, company: str | None, year: int | None, indicator: str | None) -> list[dict[str, Any]]:
    filtered = df.copy()
    if company:
        filtered = filtered[filtered["company"] == company]
    if year:
        filtered = filtered[filtered["year"] == int(year)]
    if indicator:
        filtered = filtered[filtered["indicator_name"] == indicator]
    rows = []
    for row in filtered.sort_values(["company", "year", "indicator_name"]).itertuples():
        rows.append(
            {
                "company": row.company,
                "year": int(row.year) if row.year is not None else None,
                "report_period": row.report_period,
                "indicator": row.indicator_name,
                "value": None if pd.isna(row.indicator_value) else float(row.indicator_value),
                "unit": row.unit,
                "business_scope": row.business_scope
                if isinstance(row.business_scope, str)
                else None,
                "source_text": row.source_text
                if isinstance(getattr(row, "source_text", None), str)
                else None,
                "source_page": row.source_page
                if isinstance(getattr(row, "source_page", None), str)
                else None,
                "confidence_score": None
                if pd.isna(getattr(row, "confidence_score", None))
                else float(row.confidence_score),
            }
        )
    return rows


def _match_company(question: str, companies: list[str]) -> str | None:
    question_text = question.lower()
    for company in companies:
        aliases = COMPANY_ALIASES.get(company, [company])
        if any(alias.lower() in question_text for alias in aliases):
            return company
    return None


def _match_year(question: str) -> int | None:
    match = re.search(r"(20\d{2})", question)
    return int(match.group(1)) if match else None


def _match_indicator(question: str, indicators: list[str]) -> str | None:
    for indicator in sorted(indicators, key=len, reverse=True):
        if indicator in question:
            return indicator
    return None


def _match_category(question: str) -> str | None:
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in question for keyword in keywords):
            return category
    return None


def _format_value(record: dict[str, Any]) -> str:
    value = record.get("value")
    if value is None:
        return "暂无数据"
    unit = record.get("unit") or ""
    return f"{value:,.2f}{unit}"


def _build_context(records: list[dict[str, Any]], question: str) -> str:
    if not records:
        return "当前数据库中未检索到与该问题直接匹配的指标记录。"
    lines = ["以下为数据库中检索到的相关指标记录："]
    for record in records:
        scope = record.get("business_scope") or ""
        source = (record.get("source_text") or "").strip()
        lines.append(
            f"- {record['company']} {record['year']}年 {record['indicator']}："
            f"{_format_value(record)}"
            + (f"（口径：{scope}）" if scope else "")
            + (f"；原文：{source}" if source else "")
        )
    return "\n".join(lines)


def _is_analysis_question(question: str) -> bool:
    return any(keyword in question for keyword in ANALYSIS_KEYWORDS)


def _period_class(row: dict[str, Any]) -> str:
    """报告期口径：annual=Q4 全年，half=Q2 半年，other=其他。"""
    period = (row.get("report_period") or "").upper()
    if period.endswith("Q4"):
        return "annual"
    if period.endswith("Q2"):
        return "half"
    return "other"


def _analysis_data(df, company: str | None, year: int | None) -> dict[str, Any]:
    """构建分析模式所需的多年度数据：逐年指标、自动同比、业务结构、原文摘录。"""
    rows = _metric_records(df, company, None, None)
    # 同一“年份+指标”可能同时存在 Q4（全年）与 Q2（半年）记录，
    # 只保留一个代表行：优先 Q4 全年，其次 Q2 半年，同口径取置信度更高者，
    # 避免把“2023全年 vs 2024半年”误算成同比。
    period_priority = {"annual": 0, "half": 1, "other": 2}
    best_rows: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        row_year = row["year"]
        if row_year is None:
            continue
        key = (row_year, row["indicator"])
        current = best_rows.get(key)
        if current is None:
            best_rows[key] = row
            continue
        current_priority = period_priority[_period_class(current)]
        new_priority = period_priority[_period_class(row)]
        if new_priority < current_priority or (
            new_priority == current_priority
            and (row.get("confidence_score") or 0) > (current.get("confidence_score") or 0)
        ):
            best_rows[key] = row
    rows = list(best_rows.values())

    years = sorted({row["year"] for row in rows if row["year"] is not None})
    if year:
        years = [y for y in years if y <= year]
    years = years[-ANALYSIS_YEAR_RANGE:]
    rows = [row for row in rows if row["year"] in years]

    by_indicator: dict[str, dict[int, dict[str, Any]]] = {}
    for row in rows:
        by_indicator.setdefault(row["indicator"], {})[row["year"]] = row

    deltas: list[dict[str, Any]] = []
    for indicator, year_map in by_indicator.items():
        for i in range(1, len(years)):
            prev_year, cur_year = years[i - 1], years[i]
            prev_rec = year_map.get(prev_year)
            cur_rec = year_map.get(cur_year)
            if not prev_rec or not cur_rec:
                continue
            if _period_class(prev_rec) != _period_class(cur_rec):
                continue
            if prev_rec["value"] is None or cur_rec["value"] is None:
                continue
            if prev_rec["value"] == 0:
                continue
            diff = cur_rec["value"] - prev_rec["value"]
            pct = diff / prev_rec["value"] * 100
            deltas.append(
                {
                    "indicator": indicator,
                    "prev_year": prev_year,
                    "cur_year": cur_year,
                    "cur_value": cur_rec["value"],
                    "diff": diff,
                    "pct": pct,
                    "unit": cur_rec.get("unit") or prev_rec.get("unit") or "",
                }
            )
    deltas.sort(key=lambda item: abs(item["pct"] or 0), reverse=True)

    structure_indicators = [
        indicator
        for indicator in by_indicator
        if any(keyword in indicator for keyword in STRUCTURE_KEYWORDS)
    ]

    excerpts: list[str] = []
    for row in rows:
        if row["year"] != years[-1]:
            continue
        text = (row.get("source_text") or "").strip()
        if not text or text in excerpts:
            continue
        excerpts.append(text if len(text) <= 120 else text[:117] + "…")
        if len(excerpts) >= 5:
            break

    return {
        "company": company,
        "years": years,
        "by_indicator": by_indicator,
        "deltas": deltas,
        "structure_indicators": structure_indicators,
        "excerpts": excerpts,
    }


def _format_analysis_context(
    data: dict[str, Any], question: str, chunks: list[dict[str, Any]] | None = None
) -> str:
    company = data["company"] or "全部公司"
    years = data["years"]
    by_indicator = data["by_indicator"]
    if not years:
        return "数据库中暂未收录可用的多年份指标数据。"

    lines = [f"【数据范围】{company}，年份：{'、'.join(str(y) for y in years)}"]
    lines.append("\n【逐年指标】")
    lines.append("指标 | " + " | ".join(str(y) + "年" for y in years) + " | 单位")
    for indicator in sorted(by_indicator.keys())[:60]:
        cells: list[str] = []
        unit = ""
        for y in years:
            record = by_indicator[indicator].get(y)
            if record:
                cells.append(_format_value(record))
                unit = record.get("unit") or unit
            else:
                cells.append("—")
        lines.append(f"{indicator} | " + " | ".join(cells) + f" | {unit}")

    if data["deltas"]:
        lines.append("\n【同比变化（系统按相邻年份自动计算）】")
        for item in data["deltas"][:30]:
            sign = "+" if item["diff"] > 0 else ""
            lines.append(
                f"- {item['indicator']}：{item['cur_year']}年 {item['cur_value']:,.2f}{item['unit']}"
                f"，较 {item['prev_year']}年 {sign}{item['diff']:,.2f}{item['unit']}"
                f"（{sign}{item['pct']:.1f}%）"
            )

    if data["structure_indicators"]:
        lines.append("\n【业务结构相关指标】")
        for indicator in data["structure_indicators"]:
            cells = []
            for y in years:
                record = by_indicator[indicator].get(y)
                if record:
                    cells.append(f"{y}年 {_format_value(record)}")
            if cells:
                lines.append(f"- {indicator}：" + "；".join(cells))

    if data["excerpts"]:
        lines.append("\n【数据库原文摘录】")
        for text in data["excerpts"]:
            lines.append(f"- {text}")

    if chunks:
        lines.append("\n【年报原文（知识库检索）】")
        lines.append(
            "以下段落按相关度从高到低排列，"
            "叙述性内容（方针、原因、管理层解读）优先引用并标注出处："
        )
        for index, chunk in enumerate(chunks, 1):
            origin = (
                f"{chunk.get('company')} {chunk.get('year')}年 "
                f"{chunk.get('quarter')} {chunk.get('market')}·{chunk.get('section')}"
            )
            lines.append(f"[{index}]（{origin}）{chunk.get('excerpt', '')}")

    return "\n".join(lines)


def _analysis_fallback(data: dict[str, Any]) -> str:
    """无 LLM 可用时的分析型兜底回答（基于自动计算的同比与业务结构）。"""
    company = data["company"] or "该公司"
    parts: list[str] = []
    if data["deltas"]:
        lines = [f"{company}关键指标变化（自动计算，最近相邻年份）："]
        for item in data["deltas"][:6]:
            sign = "+" if item["diff"] > 0 else ""
            lines.append(
                f"- {item['indicator']}：{item['cur_year']}年 {item['cur_value']:,.2f}{item['unit']}"
                f"，较 {item['prev_year']}年 {sign}{item['diff']:,.2f}{item['unit']}"
                f"（{sign}{item['pct']:.1f}%）"
            )
        parts.append("\n".join(lines))
    if data["structure_indicators"]:
        lines = [f"{company}业务结构（{'、'.join(str(y) for y in data['years'])}）："]
        for indicator in data["structure_indicators"][:10]:
            cells = []
            for y in data["years"]:
                record = data["by_indicator"][indicator].get(y)
                if record:
                    cells.append(f"{y}年 {_format_value(record)}")
            if cells:
                lines.append(f"- {indicator}：" + "；".join(cells))
        parts.append("\n".join(lines))
    if not parts:
        return "数据库中暂未收录该公司的多年份对比数据，暂时无法进行业务变化分析。"
    return "\n\n".join(parts)


def _direct_answer(
    question: str,
    company: str | None,
    year: int | None,
    records: list[dict[str, Any]],
    all_records: list[dict[str, Any]],
) -> str:
    if not company and not records:
        return "暂未在数据库中检索到与问题直接匹配的记录。请尝试输入更具体的公司名称或指标，例如“中国太保综合成本率是多少”。"

    if company and not records:
        if year:
            return f"数据库中暂未找到{company}{year}年相关指标数据。"
        return f"数据库中暂未找到{company}相关指标数据。"

    matched = records[:5]
    if "比较" in question or "对比" in question:
        indicator = matched[0]["indicator"] if matched else None
        group = all_records if all_records else matched
        lines = [
            f"根据结构化指标库，{indicator or '相关指标'}对比情况如下："
        ]
        for record in group[:8]:
            lines.append(f"- {record['company']} {record['year']}年：{_format_value(record)}")
        return "\n".join(lines)

    parts = []
    seen = set()
    for record in matched:
        key = (record["company"], record["year"], record["indicator"])
        if key in seen:
            continue
        seen.add(key)
        scope = f"，口径：{record['business_scope']}" if record.get("business_scope") else ""
        parts.append(
            f"{record['company']}{record['year']}年{record['indicator']}为{_format_value(record)}{scope}"
        )
    if not parts:
        return "数据库中暂无该指标的有效数值。"
    return "。".join(parts) + "。"


def _category_answer(category: str, company: str | None, year: int | None, df) -> str:
    records = _metric_records(df, company, year, None)
    target_names = {
        "业务规模": ["原保险保费收入", "车险保费收入", "非车险保费收入"],
        "盈利能力": ["综合成本率", "综合赔付率", "综合费用率", "承保利润", "净利润"],
        "偿付能力": ["核心偿付能力充足率", "综合偿付能力充足率"],
        "投资能力": ["投资资产", "投资资产规模", "投资收益"],
    }[category]
    selected = [record for record in records if record["indicator"] in target_names]
    if not selected:
        return f"当前数据库中暂未收录{company or '该公司'}的{category}相关指标。"
    lines = []
    for indicator in target_names:
        record = next((item for item in selected if item["indicator"] == indicator), None)
        if record:
            lines.append(f"{indicator}：{_format_value(record)}")
    prefix = f"{company or '该公司'}{year or ''}年{category}情况如下："
    return prefix + "；".join(lines) + "。"


def _call_llm(question: str, context: str, *, analysis_mode: bool = False) -> str | None:
    try:
        import httpx
    except ImportError:
        return None
    try:
        from services.llm_settings import effective_llm_env

        llm_env = effective_llm_env()
    except Exception:
        llm_env = {}
    api_key = (
        os.getenv("LLM_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or llm_env.get("OPENAI_API_KEY")
    )
    base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or llm_env.get("LLM_BASE_URL")
        or "https://api.openai.com/v1"
    )
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "deepseek-chat"
    if not api_key:
        return None
    system_prompt = ANALYSIS_SYSTEM_PROMPT if analysis_mode else DIRECT_SYSTEM_PROMPT
    user_content = (
        f"上下文：\n{context}\n\n用户问题：{question}\n\n请按业务分析的方式回答。"
        if analysis_mode
        else f"上下文：\n{context}\n\n问题：{question}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.5 if analysis_mode else 0.2,
        "max_tokens": 1500,
    }
    try:
        response = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip() if content else None
    except Exception:
        return None


def answer_question(question: str) -> dict[str, Any]:
    df = load_database()
    companies = sorted(df["company"].dropna().unique().tolist())
    indicators = sorted(df["indicator_name"].dropna().unique().tolist())
    company = _match_company(question, companies)
    year = _match_year(question)
    indicator = _match_indicator(question, indicators)
    category = _match_category(question)

    analysis_mode = _is_analysis_question(question) or (
        indicator is None and company is not None
    )

    if analysis_mode:
        data = _analysis_data(df, company, year)
        chunks = retrieve_chunks(question, company=company, year=year, top_k=5)
        context = _format_analysis_context(data, question, chunks)
        answer = _call_llm(question, context, analysis_mode=True)
        if not answer:
            answer = _analysis_fallback(data)
        records = _metric_records(df, company, year, None)
        if not records:
            records = _metric_records(df, company, None, None)
        source_records = records[:8]
        chunk_sources = [
            {
                "company": chunk.get("company"),
                "year": chunk.get("year"),
                "quarter": chunk.get("quarter"),
                "market": chunk.get("market"),
                "section": chunk.get("section"),
                "title": chunk.get("title"),
                "excerpt": chunk.get("excerpt"),
                "score": chunk.get("score"),
            }
            for chunk in chunks
        ]
    else:
        records = _metric_records(df, company, year, indicator)
        all_records = _metric_records(df, None, year, indicator)
        context = _build_context(records or all_records, question)
        answer = _call_llm(question, context, analysis_mode=False)
        if not answer:
            if category and not indicator:
                answer = _category_answer(category, company, year, df)
            else:
                answer = _direct_answer(question, company, year, records, all_records)
        source_records = (records or all_records)[:8]
        chunk_sources = []

    sources = [
        {
            "company": record["company"],
            "year": record["year"],
            "indicator": record["indicator"],
            "value": record["value"],
            "unit": record["unit"],
            "source_text": record["source_text"],
            "source_page": record["source_page"],
            "confidence_score": record["confidence_score"],
        }
        for record in source_records
    ]
    return {
        "question": question,
        "answer": answer,
        "source": sources,
        "chunk_sources": chunk_sources,
        "context": {
            "company": company,
            "year": year,
            "indicator": indicator,
            "category": category,
            "analysis_mode": analysis_mode,
        },
    }
