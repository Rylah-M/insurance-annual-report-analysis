import json
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tag_utils import resolve_tag, OUTPUT_DIR


# ==========================
# 文件路径（自动识别chunk标识）
# ==========================

tag = resolve_tag()

input_file = os.path.join(OUTPUT_DIR, f"indicator_match_result_{tag}_v2.json")

output_file = os.path.join(OUTPUT_DIR, f"indicator_match_result_{tag}_v3.json")


print("输出标识:", tag)



# ==========================
# 读取数据
# ==========================

with open(input_file, "r", encoding="utf-8") as f:
    data = json.load(f)



print("读取记录:", len(data))



# ==========================
# 评分函数
# ==========================

def calculate_score(item):

    score = 0


    content = item.get("content", "")

    section = item.get("section", "")

    # 表格内容同样参与评分（表格中的数字/单位也是重要信号）
    for t in item.get("tables", []):
        content += "\n" + t.get("content", "")



    # --------------------------
    # 1. 标题权重
    # --------------------------

    high_priority_words = [

        "主要指标",

        "财务指标",

        "经营业绩",

        "业务分析",

        "财产保险业务",

        "按险种",

        "分险种",

        "财务报表"

    ]


    for word in high_priority_words:

        if word in section:

            score += 3



    # --------------------------
    # 2. 数字数量
    # --------------------------

    numbers = re.findall(

        r"\d+\.?\d*",

        content

    )


    if len(numbers) > 0:

        score += 2


    if len(numbers) >= 3:

        score += 2



    # --------------------------
    # 3. 单位判断
    # --------------------------

    units = [

        "人民币百万元",

        "亿元",

        "%",

        "百万"

    ]


    for unit in units:

        if unit in content:

            score += 2



    # --------------------------
    # 4. 排除低价值章节
    # --------------------------

    low_priority_words = [

        "董事长致辞",

        "未来展望",

        "风险管理",

        "公司治理"

    ]


    for word in low_priority_words:

        if word in section:

            score -= 3



    return score





# ==========================
# 分组排序
# ==========================

for item in data:

    item["rerank_score"] = calculate_score(item)



# 按指标分组

indicator_groups = {}


for item in data:

    name = item["indicator_name"]

    if name not in indicator_groups:

        indicator_groups[name] = []


    indicator_groups[name].append(item)




# ==========================
# 每个指标保留Top5
# ==========================

result = []


for indicator, items in indicator_groups.items():


    items.sort(

        key=lambda x:x["rerank_score"],

        reverse=True

    )


    top_items = items[:5]


    result.extend(top_items)




# ==========================
# 保存
# ==========================


with open(output_file,"w",encoding="utf-8") as f:

    json.dump(

        result,

        f,

        ensure_ascii=False,

        indent=4

    )



print("排序完成")

print("原始数量:",len(data))

print("保留数量:",len(result))

print("输出:",output_file)
