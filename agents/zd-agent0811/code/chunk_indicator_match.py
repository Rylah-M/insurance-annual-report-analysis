import json
import os
import re
import sys
from collections import defaultdict
from io import StringIO

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tag_utils import resolve_tag, resolve_chunk_file, OUTPUT_DIR


# ======================
# 文件路径（自动识别chunk标识）
# ======================

tag = resolve_tag()

chunk_file = resolve_chunk_file()

indicator_file = os.path.join(OUTPUT_DIR, "indicator_dictionary.json")

output_file = os.path.join(OUTPUT_DIR, f"indicator_match_result_{tag}.json")


print("处理chunk:", chunk_file)

print("输出标识:", tag)


# ======================
# 读取文件
# ======================

with open(chunk_file, "r", encoding="utf-8") as f:
    chunks = json.load(f)


with open(indicator_file, "r", encoding="utf-8") as f:
    indicators = json.load(f)


# ======================
# 匹配辅助函数
# ======================

def normalize_text(s):
    """去除所有空白字符，用于宽松匹配"""
    return "".join(s.split())


# 已知险种/生态行标签(简繁),用于修复 MinerU 表格行标签合并/丢失错位
LINE_LABELS = [
    "健康险", "健康保險", "健康險", "健康生态", "健康生態",
    "汽车保险", "汽車保險", "车险", "車險", "汽车生态", "汽車生態",
    "机动车辆保险", "機動車輛保險",
    "责任险", "責任險", "责任保险", "責任保險",
    "家庭财产保险", "家庭財產保險", "意外险", "意外險", "意外伤害保险", "意外傷害保險",
    "信用保险", "信用保險", "保证险", "保證險", "保证保险", "保證保險",
    "货运险", "貨運險", "货物运输保险", "貨物運輸保險",
    "农险", "農險", "农业保险", "農業保險", "企财险", "企財險", "企业财产保险", "企業財產保險",
    "其他", "退貨運費險", "總計", "合计",
]

METRIC_HINTS = [
    "原保险保费收入", "原保險保費收入", "保险服务收入", "保險服務收入",
    "保险服务费用", "保險服務費用", "承保利润", "承保利潤", "承保溢利",
    "综合成本率", "綜合成本率", "综合赔付率", "綜合賠付率", "综合费用率", "綜合費用率",
    "保费收入", "保費收入", "保费", "保費", "投资收益", "投資收益",
]


def _repair_table_df(df):
    """修复 MinerU 表格行标签错位:
    当某行标签单元格含 2+ 个险种名、且上一行无标签但有数值时,
    把第一个险种名还给上一行,本行保留最后一个险种名。"""
    rows = [[str(v).strip() for v in row.tolist()] for _, row in df.iterrows()]

    def labels_in(cell):
        return [lab for lab in LINE_LABELS if lab and lab in cell]

    for i in range(1, len(rows)):
        prev, cur = rows[i - 1], rows[i]
        if not prev or not cur:
            continue
        if prev and cur and prev[0] in ("", "nan") and cur[0] not in ("", "nan"):
            labs = labels_in(cur[0])
            has_values = any(v and v not in ("nan", "") for v in prev[1:])
            if len(labs) >= 2 and has_values:
                prev[0] = labs[0]
                cur[0] = labs[-1]
    return pd.DataFrame(rows)


def repair_table_html(html: str) -> str:
    """修复 MinerU 表格行标签错位并重建为简单 HTML,供提取阶段直接读取。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S)
    cells_list = []
    for row in rows:
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        cells_list.append(cells)
    for i in range(1, len(cells_list)):
        prev, cur = cells_list[i - 1], cells_list[i]
        if not prev or not cur:
            continue
        if prev and cur and prev[0] in ("", "nan") and cur[0] not in ("", "nan"):
            labs = [lab for lab in LINE_LABELS if lab and lab in cur[0]]
            has_values = any(v and v not in ("nan", "") for v in prev[1:])
            if len(labs) >= 2 and has_values:
                prev[0] = labs[0]
                cur[0] = labs[-1]
    rebuilt = ["<table>"]
    for cells in cells_list:
        rebuilt.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    rebuilt.append("</table>")
    return "".join(rebuilt)


def _metric_hint(chunk):
    """从章节标题/内容提取指标名(表头缺失时表格的指标名在章节标题里)。"""
    head = f"{chunk.get('title') or ''} {chunk.get('section') or ''}"
    for metric in METRIC_HINTS:
        if metric in head:
            return metric
    text = (chunk.get("content") or "")[:600]
    for metric in METRIC_HINTS:
        if metric in text:
            return metric
    return ""


def table_semantic_text(chunk):
    """
    把表格的“行标签 × 表头”组合成语义短语，解决表格结构问题：
    表头放指标（如“保险服务收入”）、行标签放险种（如“车险”）时，
    原文里“车险”和“保险服务收入”并不相邻，关键词匹配不到。
    这里生成“车险保险服务收入”“车险原保险保费收入”等组合，让关键词直接命中。
    """
    parts = []
    metric_hint = _metric_hint(chunk)
    for t in chunk.get("tables", []):
        html = t.get("content", "")
        try:
            parsed = pd.read_html(StringIO(html))
        except Exception:
            continue
        if not parsed:
            continue
        df = parsed[0]
        df = _repair_table_df(df)
        if all(str(c).isdigit() for c in df.columns):
            # read_html 未把首行识别为表头时，手动提升
            header = [str(v).strip() for v in df.iloc[0].tolist()]
            data = df.iloc[1:]
        else:
            header = []
            for c in df.columns:
                if isinstance(c, tuple):
                    header.append("".join(str(x) for x in c if str(x) != "nan").strip())
                else:
                    header.append(str(c).strip())
            data = df
        for _, row in data.iterrows():
            cells = [str(v).strip() for v in row.tolist()]
            row_label = cells[0] if cells else ""
            if not row_label or row_label in ("nan", ""):
                continue
            parts.append(row_label)
            for j in range(1, len(header)):
                col = header[j]
                if not col or col in ("nan", ""):
                    continue
                if j < len(cells):
                    parts.append(row_label + col)
            if metric_hint:
                parts.append(row_label + metric_hint)
    return "\n".join(parts)


DOMAIN_TAILS = [
    "保费收入",
    "综合成本率",
    "保险服务收入",
    "保险服务费用",
    "占比",
    "充足率",
    "准备金",
]


# 相关指标扩散：细分/下级指标候选不足时，从上级或同族指标召回结果中扩散。
# 例如"车险综合成本率"依赖"综合成本率"的表头列 + "车险"行，
# 表格格式不规范时关键词可能只命中上级指标，这里把上级命中的 chunk 补进下级。
RELATED_INDICATORS = {
    "车险综合成本率": ["综合成本率"],
    "非车险综合成本率": ["综合成本率"],
    "综合赔付率": ["综合成本率"],
    "综合费用率": ["综合成本率"],
    "车险保费收入": ["原保险保费收入"],
    "非车险保费收入": ["原保险保费收入"],
    "农业保险保费": ["原保险保费收入"],
    "健康险保费": ["原保险保费收入"],
    "车险业务占比": ["原保险保费收入"],
    "非车险业务占比": ["原保险保费收入"],
    "车险保险服务收入": ["保险服务收入"],
    "非车保险服务收入": ["保险服务收入"],
    "健康险保险服务收入": ["保险服务收入"],
    "责任险保险服务收入": ["保险服务收入"],
    "意外险保险服务收入": ["保险服务收入"],
    "保证险保险服务收入": ["保险服务收入"],
    "货运险保险服务收入": ["保险服务收入"],
    "农险保险服务收入": ["保险服务收入"],
    "企财险保险服务收入": ["保险服务收入"],
    "新能源车险保险服务收入": ["保险服务收入"],
    "非车非保证险保费": ["非车险保费收入", "原保险保费收入"],
}


# 扩散补入时的险种限定词:目标为险种级指标时,候选 chunk 必须同时包含险种词,
# 避免把"保险服务收入""原保险保费收入"等总口径命中的 chunk 无差别补进下级指标。
EXPAND_REQUIRED_TERMS = {
    "车险综合成本率": ["车险", "机动车辆保险", "机动车辆险", "汽车生态", "車險", "機動車輛保險", "汽車生態", "汽车保险"],
    "非车险综合成本率": ["非车险", "非机动车辆保险", "非机动车辆险", "非車險", "非機動車輛保險"],
    "车险保费收入": ["车险", "机动车辆保险", "机动车辆险", "汽车生态", "車險", "機動車輛保險", "汽車生態", "汽车保险"],
    "非车险保费收入": ["非车险", "非机动车辆保险", "非机动车辆险", "非車險", "非機動車輛保險"],
    "农业保险保费": ["农险", "农业保险", "農險", "農業保險"],
    "健康险保费": ["健康险", "健康保险", "健康生态", "健康生態", "健康險", "健康保險"],
    "车险业务占比": ["车险", "机动车辆保险", "机动车辆险", "汽车生态", "車險", "機動車輛保險", "汽車生態"],
    "非车险业务占比": ["非车险", "非机动车辆保险", "非机动车辆险", "非車險", "非機動車輛保險"],
    "车险保险服务收入": ["车险", "机动车辆保险", "机动车辆险", "汽车生态", "汽车保险", "車險", "機動車輛保險", "汽車生態", "汽車保險"],
    "非车保险服务收入": ["非车险", "非机动车辆保险", "非机动车辆险", "非車險", "非機動車輛保險"],
    "健康险保险服务收入": ["健康险", "健康保险", "健康生态", "健康險", "健康保險", "健康生態"],
    "责任险保险服务收入": ["责任险", "责任保险", "責任險", "責任保險"],
    "意外险保险服务收入": ["意外险", "意外伤害保险", "意外險", "意外傷害保險"],
    "保证险保险服务收入": ["保证险", "保证保险", "保證險", "保證保險"],
    "货运险保险服务收入": ["货运险", "货物运输保险", "貨運險", "貨物運輸保險"],
    "农险保险服务收入": ["农险", "农业保险", "農險", "農業保險"],
    "企财险保险服务收入": ["企财险", "企业财产保险", "企財險", "企業財產保險"],
    "新能源车险保险服务收入": ["新能源车险", "新能源汽车保险", "新能源車險", "新能源汽車保險"],
    "非车非保证险保费": [
        "非车非保证", "剔除保证保险", "不含保证保险", "扣除保证保险", "排除保证保险",
        "非車非保證", "剔除保證保險", "不含保證保險", "扣除保證保險", "排除保證保險",
    ],
}


def _contains_any(item: dict, terms: list[str]) -> bool:
    text = _item_text(item)
    return any(term in text for term in terms)


def _item_text(item: dict) -> str:
    parts = [str(item.get("content") or "")]
    for table in item.get("tables") or []:
        parts.append(re.sub(r"<[^>]+>", " ", str(table.get("content") or "")))
    return " ".join(parts)


# 意健险(意外伤害及健康保险)合并披露标记
YJ_COMBINED_MARKERS = [
    "意外伤害及健康保险", "意外伤害及健康险", "意外伤害和健康保险",
    "意外险与健康险", "意健险", "意外伤害及", "意外傷害及",
    "意外傷害及健康保險", "意外傷害及健康險", "意外險與健康險", "意健險",
]


def _is_yj_indicator(name: str) -> bool:
    return ("意健" in name) or ("意外伤害及健康" in name) or ("意外傷害及健康" in name)


def _exclude_yj_conflict(indicator_name: str, text: str) -> bool:
    """互斥规则:年报按'意外伤害及健康保险/意健险'合并披露时,
    意外险/健康险的单独指标不应再命中合并值(避免两处重复提取同一数值)。
    合并披露表格只有合并行;分开披露时表格会另有'意外伤害保险'独立行。"""
    if _is_yj_indicator(indicator_name):
        return False
    ntext = normalize_text(text)
    has_combined = any(marker in ntext for marker in YJ_COMBINED_MARKERS)
    if not has_combined:
        return False
    has_sep_accident = ("意外伤害保险" in ntext) or ("意外傷害保險" in ntext)
    return not has_sep_accident


def _exclude_life_health_segment(indicator_name: str, text: str) -> bool:
    """健康险单独指标排除'寿险及健康险业务'段位噪音(平安等综合集团报告)。"""
    name = indicator_name or ""
    if not ("健康险" in name or "健康保险" in name):
        return False
    ntext = normalize_text(text)
    has_life_marker = any(
        marker in ntext
        for marker in ["寿险及健康险业务", "壽險及健康險業務", "寿险及健康险", "壽險及健康險"]
    )
    if not has_life_marker:
        return False
    has_pc_marker = any(
        marker in ntext
        for marker in ["产险", "财险", "财产保险", "產險", "財險", "財產保險"]
    )
    return not has_pc_marker


def _candidate_allowed(indicator_name: str, title, section) -> bool:
    """保费类与保险服务收入类候选硬隔离,防止把服务收入当保费提取(或反之)。"""
    head = f"{title or ''} {section or ''}"
    name = indicator_name or ""
    if "保费" in name and ("保险服务收入" in head or "保險服務收入" in head):
        return False
    if "保险服务收入" in name:
        if ("保费" in head or "保費" in head) and not (
            "保险服务收入" in head or "保險服務收入" in head
        ):
            return False
    return True


def keyword_matches(keyword, text, ntext):

    if not keyword:
        return False

    # 1. 原文直接包含关键词
    if keyword in text:
        return True

    # 2. 忽略空白后包含关键词（例如换行/空格隔开）
    nkw = normalize_text(keyword)
    if nkw in ntext:
        return True

    # 3. 宽松匹配：
    #    "车险保费收入" 可命中 "车险业务保费收入"
    #    "机动车辆险综合成本率" 可命中 "机动车辆险业务综合成本率"
    for tail in DOMAIN_TAILS:
        if nkw.endswith(tail):
            prefix = nkw[:-len(tail)]
            if prefix and tail in ntext:
                start = 0
                while True:
                    pos_prefix = ntext.find(prefix, start)
                    if pos_prefix == -1:
                        break
                    pos_tail = ntext.find(tail, pos_prefix)
                    if pos_tail != -1 and pos_tail <= pos_prefix + 40:
                        return True
                    start = pos_prefix + 1

    return False


# ======================
# 指标召回
# ======================

results = []


for indicator in indicators:

    indicator_name = indicator.get(
        "indicator_name",
        ""
    )

    keywords = indicator.get(
        "keyword",
        []
    )


    if not keywords:
        continue


    for chunk in chunks:

        text = (
            chunk.get("content","")
            +
            str(chunk.get("tables",""))
        )

        # 表格语义化文本：行标签×表头组合
        text += "\n" + table_semantic_text(chunk)

        ntext = normalize_text(text)


        for keyword in keywords:

            if keyword_matches(keyword, text, ntext):

                if not _candidate_allowed(
                    indicator_name,
                    chunk.get("title"),
                    chunk.get("section"),
                ):
                    continue
                if _exclude_yj_conflict(indicator_name, text):
                    continue
                if _exclude_life_health_segment(indicator_name, text):
                    continue

                results.append({

                    "indicator_name":
                    indicator_name,


                    "matched_keyword":
                    keyword,


                    "chunk_id":
                    chunk["chunk_id"],


                    "company":
                    chunk["company"],


                    "year":
                    chunk["year"],


                    "section":
                    chunk["section"],


                    "content":
                    chunk["content"],

                "tables":
                    [
                        {
                            **t,
                            "content": repair_table_html(t["content"])
                            if t.get("content") else t.get("content"),
                        }
                        for t in (chunk.get("tables") or [])
                    ]

                })

                break
# ======================
# 相关指标候选扩散
# ======================

by_indicator = defaultdict(list)

for item in results:
    by_indicator[item["indicator_name"]].append(item)

extra_items = []

for target, related in RELATED_INDICATORS.items():

    existing_ids = {item["chunk_id"] for item in by_indicator.get(target, [])}
    required_terms = EXPAND_REQUIRED_TERMS.get(target)

    for rel in related:

        for item in by_indicator.get(rel, []):

            if item["chunk_id"] not in existing_ids:
                if required_terms and not _contains_any(item, required_terms):
                    continue
                if not _candidate_allowed(target, item.get("title"), item.get("section")):
                    continue
                if _exclude_yj_conflict(target, _item_text(item)):
                    continue
                if _exclude_life_health_segment(target, _item_text(item)):
                    continue

                new_item = dict(item)

                new_item["indicator_name"] = target

                new_item["matched_keyword"] = f"扩散自:{rel}"

                extra_items.append(new_item)

                existing_ids.add(item["chunk_id"])


results.extend(extra_items)


# ======================
# 输出
# ======================

with open(
    output_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        results,
        f,
        ensure_ascii=False,
        indent=4
    )


print("指标召回完成")
print("匹配数量:", len(results))
print("扩散补入数量:", len(extra_items))
print("输出:",output_file)
