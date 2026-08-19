```md
# 年报智能分析 Agent 项目 README

## 1. 项目简介

本项目目标是开发一个面向保险公司年报的智能分析 Agent。

核心目标：

> 利用大语言模型（LLM）自动读取保险公司年报文本，识别关键经营指标，并按照统一指标体系抽取结构化数据。

当前开发阶段主要验证：

**已有年报切块（chunk）数据 → 指标匹配 → LLM理解 → 指标结构化抽取**

即验证 AI 是否能够真正理解年报内容，并提取目标保险经营指标。

---

# 2. 当前开发流程

目前整体流程如下：
```

年报PDF
↓
PDF解析（队友负责）
↓
Markdown清洗、切块（队友负责）
↓
chunks.json
↓
指标关键词召回
↓
indicator_match_result.json
↓
候选chunk排序
↓
indicator_match_result_v3.json
↓
LLM指标理解与抽取
↓
extracted_indicator_result.json
↓
结构化数据库
↓
extracted_indicator_database_v2.xlsx

```
---

# 3. 当前目录结构
```

zd-agent0810/

├── chunk/
│ └── chunks.json
│
├── indicator/
│ └── indicator_dictionary.xlsx
│
├── output/
│ ├── indicator_dictionary.json
│ ├── indicator_match_result.json
│ ├── indicator_match_result_v2.json
│ ├── indicator_match_result_v3.json
│ └── extracted_indicator_result.json
│
├── code/
│ ├── chunk_indicator_match.py
│ ├── chunk_rerank.py
│ ├── indicator_extract_test.py
│ ├── indicator_extract_agent.py
│ └── test_api.py
│
└── database/
└── extracted_indicator_database_v2.xlsx

```
---

# 4. 文件说明

## 4.1 chunks.json

路径：
```

chunk/chunks.json

```
作用：

存储经过 PDF 解析、Markdown 清洗和切块后的年报文本。

当前数据：

- 公司：中国太保
- 年份：2024
- chunk数量：143
- 包含表格chunk：85

单个chunk结构：

```json
{
    "chunk_id": "taibao_2024_a_026",
    "company": "中国太保",
    "year": 2024,
    "section": "4财产保险业务",
    "title": "4财产保险业务",
    "content": "年报文本内容",
    "tables": [],
    "position": 26
}
```

作用：

作为后续 AI 阅读和指标提取的原始输入。

------

# 5. 指标知识库

## indicator_dictionary.xlsx

路径：

```
indicator/indicator_dictionary.xlsx
```

作用：

定义需要从年报中提取的标准保险指标。

包含：

| 字段             | 说明         |
| ---------------- | ------------ |
| indicator_id     | 指标编号     |
| indicator_name   | 指标名称     |
| alias            | 指标别名     |
| keyword          | 匹配关键词   |
| definition       | 指标定义     |
| unit             | 标准单位     |
| data_type        | 数据类型     |
| calculation_rule | 计算规则     |
| source_priority  | 优先来源位置 |

例如：

```
F006
指标名称：
综合成本率

关键词：
综合成本率
承保综合成本率
combined ratio
```

作用：

作为 AI 提取指标时的业务知识基础。

------

# 6. indicator_dictionary.json

路径：

```
output/indicator_dictionary.json
```

作用：

将 Excel 格式指标字典转换为 JSON，方便 Python 程序读取。

用于：

- chunk匹配
- LLM prompt构造
- 指标定义提供

------

# 7. 指标召回阶段

## 7.1 chunk_indicator_match.py

作用：

根据指标字典中的关键词，在所有chunk中搜索可能包含指标的信息。

输入：

```
chunks.json

+

indicator_dictionary.json
```

输出：

```
output/indicator_match_result.json
```

当前结果：

```
总召回数：151

涉及指标：
20个

涉及chunk：
50个
```

示例：

```json
{
"indicator_name":"综合成本率",
"chunk_id":"taibao_2024_a_026",
"content":"承保综合成本率97.1%"
}
```

说明：

该阶段目标：

> 找到可能包含目标指标的年报片段。

不是最终提取。

------

# 8. 指标匹配增强阶段

## indicator_match_result_v2.json

作用：

在基础召回结果中加入指标字典信息。

新增：

- indicator_id
- indicator_category
- definition
- standard_unit
- data_type
- source_priority

例如：

```json
{
"indicator_name":"综合成本率",
"indicator_id":"F006",
"definition":"反映保险业务承保盈利能力"
}
```

目的：

让后续LLM不仅看到关键词，还理解指标含义。

------

# 9. Chunk排序阶段

## chunk_rerank.py

作用：

对召回chunk进行相关性排序。

输入：

```
indicator_match_result_v2.json
```

输出：

```
indicator_match_result_v3.json
```

当前结果：

```
原始记录：
151

排序后保留：
54
```

排序依据：

- 指标关键词出现
- chunk标题相关性
- 业务章节相关性

目标：

减少无关文本，提高LLM提取准确率。

------

# 10. LLM指标抽取阶段

## indicator_extract_test.py

作用：

测试单个chunk是否可以被LLM正确理解。

例如：

输入：

```
综合成本率
+
太保产险业务分析chunk
```

输出：

```json
{
"indicator_name":"综合成本率",
"indicator_value":"97.1",
"unit":"%",
"business_scope":"太保产险",
"source_text":"承保综合成本率97.1%",
"confidence_score":"1"
}
```

验证：

LLM已经可以理解：

- 指标名称
- 指标数值
- 单位
- 业务范围
- 来源文本

------

# 11. Agent抽取阶段

## indicator_extract_agent.py

作用：

批量调用LLM，对所有指标候选chunk进行自动抽取。

输入：

```
indicator_match_result_v3.json
```

输出：

```
output/extracted_indicator_result.json
```

目标：

形成：

```
年报文本

↓

指标识别

↓

结构化结果
```

------

# 12. extracted_indicator_database_v2.xlsx

路径：

```
database/
```

作用：

最终结构化指标数据库。

设计字段：

| 字段             | 说明     |
| ---------------- | -------- |
| company          | 公司名称 |
| year             | 年份     |
| indicator_id     | 指标编号 |
| indicator_name   | 指标名称 |
| indicator_value  | 指标值   |
| unit             | 单位     |
| business_scope   | 业务范围 |
| source_file      | 来源文件 |
| source_page      | 页码     |
| source_text      | 原文     |
| extraction_time  | 提取时间 |
| confidence_score | 置信度   |
| review_status    | 审核状态 |

用途：

后续：

- 公司横向比较
- 指标趋势分析
- 自动生成分析报告
- Agent问答

------

# 13. 当前完成情况

## 已完成

✅ 年报文本chunk化结果获取

✅ 建立保险指标字典

✅ 完成chunk关键词召回

✅ 完成指标语义信息融合

✅ 完成候选chunk排序

✅ 完成LLM API调用测试

✅ 验证单指标自动抽取可行

------

# 14. 当前待优化问题

## 1. 指标匹配准确率

目前关键词召回存在：

- 同名不同口径
- 集团指标与产险指标混淆
- 寿险指标误召回

下一步：

增加：

- business_scope约束
- source_priority规则
- 指标上下文判断

------

## 2. 多指标批量抽取

当前：

单个指标测试成功。

下一步：

实现：

```
54个候选chunk

↓

20个指标

↓

批量LLM extraction

↓

数据库写入
```

------

## 3. 数据质量验证

需要增加：

- 单位检查
- 数值格式检查
- 年份检查
- 公司范围检查
- 会计勾稽关系验证

------

# 15. 当前项目阶段总结

目前已经完成 Agent 的核心验证流程：

```
年报文本
    ↓
chunk
    ↓
指标召回
    ↓
候选文本排序
    ↓
LLM理解
    ↓
指标结构化抽取
```

当前证明：

> 基于已有年报chunk和指标知识库，大语言模型能够理解保险年报文本，并完成目标指标抽取。

下一阶段重点：

> 从单指标测试升级为完整指标库批量抽取，并连接 extracted_indicator_database，实现可查询、可分析的保险年报智能分析 Agent。

```

```