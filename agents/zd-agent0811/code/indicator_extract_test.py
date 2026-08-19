from openai import OpenAI
import os
import json


# =========================
# 1. 初始化API
# =========================

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.nwafu-ai.cn/v1"
)


# =========================
# 2. 测试文本
# 后续改成自动读取chunks.json
# =========================

chunk_text = """
2024年上半年，太保产险实现原保险保费收入1118.03亿元，
同比增长7.8%，实现保险服务收入930.76亿元，同比增长4.2%。

承保综合成本率97.1%，同比下降0.8个百分点。
其中，承保综合赔付率69.6%，承保综合费用率27.5%。

"""


# =========================
# 3. 指标定义
# =========================

indicator = {
    "indicator_id": "F006",
    "indicator_name": "综合成本率",
    "description": "反映财产保险业务承保盈利能力的指标"
}



# =========================
# 4. 构造Prompt
# =========================

prompt = f"""

你是一名保险行业研究员。

请根据下面的年报文本，
提取指定保险经营指标。


指标信息：

指标编号：
{indicator['indicator_id']}

指标名称：
{indicator['indicator_name']}

指标说明：
{indicator['description']}


年报文本：

{chunk_text}


请严格按照JSON格式返回：

{{
"indicator_name":"",
"indicator_value":"",
"unit":"",
"business_scope":"",
"source_text":"",
"confidence_score":""
}}

要求：

1. indicator_value只填写数字；
2. 不要编造不存在的数据；
3. source_text填写对应原文；
4. confidence_score范围0-1。


"""


# =========================
# 5. 调用模型
# =========================


response = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {
            "role":"user",
            "content":prompt
        }
    ],
    temperature=0
)


answer=response.choices[0].message.content


print(answer)


# =========================
# 6. 保存结果
# =========================

with open(
    "../output/extracted_test_result.json",
    "w",
    encoding="utf-8"
) as f:
    f.write(answer)


print("\n结果已经保存")