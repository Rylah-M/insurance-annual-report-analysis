from openai import OpenAI
import os
import json
import sys
import ast
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tag_utils import resolve_tag, OUTPUT_DIR


# =========================
# 1. 初始化模型
# =========================

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
)


# =========================
# 2. 文件路径（自动识别chunk标识）
# =========================

tag = resolve_tag()

match_file = os.path.join(OUTPUT_DIR, f"indicator_match_result_{tag}_v3.json")

output_file = os.path.join(OUTPUT_DIR, f"extracted_indicator_result_{tag}.json")


print("输出标识:", tag)


# =========================
# 3. 读取召回结果
# =========================

with open(match_file, "r", encoding="utf-8") as f:
    matches = json.load(f)


print("召回记录数量:", len(matches))


# =========================
# 4. 按指标分组
# =========================

indicator_groups = defaultdict(list)


for item in matches:

    indicator_name = item["indicator_name"]

    indicator_groups[indicator_name].append(item)


print("指标数量:", len(indicator_groups))


# =========================
# 5. 工具函数
# =========================

def clean_json_text(text):

    text = text.strip()

    if text.startswith("```"):

        lines = text.splitlines()

        if lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    if text and text[0] not in "{[":

        first_obj = text.find("{")
        first_arr = text.find("[")

        candidates = [pos for pos in [first_obj, first_arr] if pos != -1]

        if candidates:
            start = min(candidates)
            end_obj = text.rfind("}")
            end_arr = text.rfind("]")
            end = max(end_obj, end_arr)

            if end > start:
                text = text[start:end + 1].strip()

    return text


def normalize_result_item(result, indicator_name, chunks):

    result["indicator_id"] = result.get(
        "indicator_id",
        chunks[0].get("indicator_id", "")
    )
    result["indicator_name"] = result.get(
        "indicator_name",
        indicator_name
    )
    return result


def error_summary(exc):
    """把 OpenAI 异常中的字典原文转换为可读的简短说明。"""
    text = str(exc)
    try:
        start = text.find("{")
        if start != -1:
            data = ast.literal_eval(text[start:])
            error = data.get("error", data) if isinstance(data, dict) else {}
            if isinstance(error, dict):
                message = error.get("message") or data.get("message") or text
                code = error.get("code") or data.get("code") or ""
                return f"HTTP {code}: {message}" if code else str(message)
    except Exception:
        pass
    return text


def build_candidate_text(chunks):

    candidate_text = ""

    for i, chunk in enumerate(chunks):

        tables = chunk.get("tables", [])

        table_text = ""

        if tables:
            table_parts = []
            for j, t in enumerate(tables):
                table_parts.append(
                    f"表格{j+1} ({t.get('table_id', '')}):\n{t.get('content', '')}"
                )
            table_text = "\n\n".join(table_parts)

        table_section = ("表格:\n" + table_text) if table_text else ""

        candidate_text += f"""

======== 候选{i+1} ========

公司:
{chunk.get('company', '')}

年份:
{chunk.get('year', '')}

章节:
{chunk.get('section', '')}

chunk_id:
{chunk.get('chunk_id', '')}

文本:
{chunk.get('content', '')}

{table_section}

"""

    return candidate_text


def build_prompt(indicator_name, chunks):

    first_chunk = chunks[0]

    candidate_text = build_candidate_text(chunks)

    return f"""

你是一名专业的保险行业研究员。

现在需要从上市财险公司年报中提取指标。


目标指标信息：

indicator_id:
{first_chunk.get('indicator_id', '')}

indicator_name:
{indicator_name}

indicator_category:
{first_chunk.get('indicator_category', '')}

definition:
{first_chunk.get('definition', '')}

standard_unit:
{first_chunk.get('standard_unit', '')}

source_priority:
{first_chunk.get('source_priority', '')}


下面提供多个候选文本。

请判断：

1. 哪个文本真正披露了该指标；
2. 提取正确数值；
3. 判断业务范围。


候选文本：

{candidate_text}


请严格返回JSON：

{{
"company":"",
"year":"",
"indicator_id":"",
"indicator_name":"",
"indicator_value":"",
"unit":"",
"business_scope":"",
"source_text":"",
"confidence_score":""
}}


要求：

- indicator_value只填写数字；
- indicator_value必须按standard_unit单位填写：原文为亿元时换算为百万元（1亿元=100百万元），为万亿元时换算为百万元（1万亿元=1,000,000百万元）；
- 不要选择同比增长率；
- 不要选择变化百分点；
- 优先选择公司经营指标正文；
- 正文和表格中的数值均有效；若出现该指标或其近似名称（如"总投资收益"对应"投资收益"、"意外伤害及健康保险"对应"健康险"）的数值，必须提取，不要留空；
- 本指标为财产保险业务指标：只能取该公司财产保险业务（如太平财险、太保产险、平安产险、人保财险）口径的数值；
- 集团合并口径、寿险、再保险等口径均不算数；若候选文本只有集团/寿险/再保数据而没有财产保险口径数值，请返回空值并将confidence_score设为0，不要用其他口径顶替；
- 多个候选出现不同数值时，优先选择该公司的财产保险业务口径，并准确填写business_scope；
- 原文单位为港元（HK$）时，按2025年平均汇率 1港元≈0.916人民币元 换算为人民币，再按standard_unit（百万元）填写；
- 若报告未直接给出合计值，但给出了可计算的口径（如分险种之和、总原保险保费收入×占比），请计算并在source_text中注明计算方式；不要把占比或增长率直接当作指标值；
- 仅当所有候选都没有该指标的真实数值时，才返回空值；
- 如果无法判断，confidence_score降低。


"""


# =========================
# 6. 批量调用GPT提取指标
# =========================

results = []

failed_items = []

total_indicators = len(indicator_groups)

success_count = 0


for index, (indicator_name, chunks) in enumerate(indicator_groups.items(), start=1):

    print(
        f"\n[{index}/{total_indicators}] 指标: {indicator_name}，候选chunk: {len(chunks)}"
    )

    try:

        prompt = build_prompt(indicator_name, chunks)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        answer = response.choices[0].message.content

        result = json.loads(clean_json_text(answer))

        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict):
                    results.append(normalize_result_item(item, indicator_name, chunks))
        else:
            results.append(normalize_result_item(result, indicator_name, chunks))

        success_count += 1

        print("模型提取成功")

    except Exception as e:

        failed_items.append(
            {
                "indicator_name": indicator_name,
                "error": str(e)
            }
        )

        print("提取失败:", error_summary(e))
        print("继续处理下一个指标")


# =========================
# 7. 保存JSON数组结果
# =========================

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


print("\n全部指标处理完成")
print("成功数量:", success_count)
print("失败数量:", len(failed_items))
print("结果数量:", len(results))
print("输出:", output_file)
