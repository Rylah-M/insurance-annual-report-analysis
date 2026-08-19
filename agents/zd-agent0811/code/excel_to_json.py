import pandas as pd
import json
import os


# ==========================
# 文件路径
# ==========================

excel_file = "../indicator/indicator_dictionary.xlsx"

output_file = "../output/indicator_dictionary.json"


# ==========================
# 读取Excel
# ==========================

df = pd.read_excel(
    excel_file,
    sheet_name="indicator_dictionary"
)


# 去除空值

df = df.fillna("")


# ==========================
# Excel转换JSON
# ==========================

indicator_list = []


for _, row in df.iterrows():

    indicator = {

        "indicator_id": row["indicator_id"],

        "indicator_category": row["indicator_category"],

        "indicator_name": row["indicator_name"],


        # 指标别名拆分
        "alias": [
            x.strip()
            for x in str(row["indicator_alias"]).split("|")
            if x.strip()
        ],


        # 关键词拆分
        "keyword": [
            x.strip()
            for x in str(row["keyword"]).split("|")
            if x.strip()
        ],


        "definition": row["definition"],

        "unit": row["unit"],

        "data_type": row["data_type"],

        "calculation_rule": row["calculation_rule"],

        "source_priority": row["source_priority"]

    }


    indicator_list.append(indicator)



# ==========================
# 输出JSON
# ==========================

with open(
    output_file,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        indicator_list,
        f,
        ensure_ascii=False,
        indent=4
    )


print("Excel转换JSON完成")
print("指标数量:", len(indicator_list))
print("输出位置:", output_file)
