import json
import os
import sys

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code")
)

from tag_utils import resolve_tag, OUTPUT_DIR


# ==============================
# 文件路径（自动识别chunk标识）
# ==============================

tag = resolve_tag()

indicator_match_file = os.path.join(OUTPUT_DIR, f"indicator_match_result_{tag}.json")

dictionary_file = os.path.join(OUTPUT_DIR, "indicator_dictionary.json")

output_file = os.path.join(OUTPUT_DIR, f"indicator_match_result_{tag}_v2.json")


print("输出标识:", tag)


# ==============================
# 读取指标标准库
# ==============================

with open(dictionary_file, "r", encoding="utf-8") as f:
    indicator_dictionary = json.load(f)


# 建立指标名称映射

indicator_map = {}

for item in indicator_dictionary:

    name = item["indicator_name"]

    indicator_map[name] = item

    # 同时加入alias
    for alias in item.get("alias", []):

        indicator_map[alias] = item



print("指标库加载完成")
print("指标数量:", len(indicator_dictionary))



# ==============================
# 读取chunk匹配结果
# ==============================

with open(indicator_match_file, "r", encoding="utf-8") as f:
    match_results = json.load(f)



# ==============================
# 增强字段
# ==============================

enhanced_results = []


match_count = 0


for item in match_results:

    indicator_name = item["indicator_name"]


    new_item = item.copy()


    if indicator_name in indicator_map:

        info = indicator_map[indicator_name]


        new_item["indicator_id"] = info["indicator_id"]

        new_item["indicator_category"] = info["indicator_category"]

        new_item["definition"] = info["definition"]

        new_item["standard_unit"] = info["unit"]

        new_item["data_type"] = info["data_type"]

        new_item["source_priority"] = info["source_priority"]

        match_count += 1


    else:

        new_item["indicator_id"] = None

        new_item["definition"] = None

        new_item["standard_unit"] = None



    enhanced_results.append(new_item)



# ==============================
# 保存
# ==============================

with open(output_file, "w", encoding="utf-8") as f:

    json.dump(
        enhanced_results,
        f,
        ensure_ascii=False,
        indent=4
    )



print("\n增强完成")
print("原始召回数量:", len(match_results))
print("成功匹配指标库:", match_count)
print("输出文件:", output_file)
