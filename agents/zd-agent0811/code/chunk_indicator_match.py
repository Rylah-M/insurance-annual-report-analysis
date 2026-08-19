import json
import os
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


def table_semantic_text(chunk):
    """
    把表格的“行标签 × 表头”组合成语义短语，解决表格结构问题：
    表头放指标（如“保险服务收入”）、行标签放险种（如“车险”）时，
    原文里“车险”和“保险服务收入”并不相邻，关键词匹配不到。
    这里生成“车险保险服务收入”“车险原保险保费收入”等组合，让关键词直接命中。
    """
    parts = []
    for t in chunk.get("tables", []):
        html = t.get("content", "")
        try:
            parsed = pd.read_html(StringIO(html))
        except Exception:
            continue
        if not parsed:
            continue
        df = parsed[0]
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
    "非车非保证险保费": ["非车险保费收入", "原保险保费收入"],
}


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
                    chunk.get("tables", [])

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

    for rel in related:

        for item in by_indicator.get(rel, []):

            if item["chunk_id"] not in existing_ids:

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
