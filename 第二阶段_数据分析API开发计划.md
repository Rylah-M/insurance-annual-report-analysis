------



```
第二阶段_数据分析API开发计划.md
```

内容核心：

```
基于第一阶段完成的Web架构设计，
现在开始实现数据分析后端。

目标：
database.csv
↓
Python分析模块
↓
FastAPI API

要求：
1. 读取真实database.csv
2. 不修改数据库
3. 不写死数据
4. 完成公司/年份/指标接口
5. 完成横向比较接口
6. 完成公司画像接口
7. FastAPI Swagger测试通过

暂不开发React页面。
```

------

你现在这个项目其实已经进入**产品工程阶段**，而不是算法验证阶段。对于两人小组来说，最重要的是先把 **“数据库 → API → 网页展示”跑通**，这样你们的 Agent 才从实验代码变成可展示系统。

按照你的建议，你完成一个第二阶段_数据分析API开发计划.md给我

根据你目前的进度，我建议**不要马上开发前端页面细节**，而是先把「数据分析模块 API」做出来。

原因：

你现在已经完成：

```
PDF年报
   ↓
MinerU解析
   ↓
Markdown
   ↓
chunks
   ↓
指标召回
   ↓
增强
   ↓
排序
   ↓
LLM提取
   ↓
database_result.csv
```

下一步需要把：

```
database_result.csv
        ↓
数据分析逻辑
        ↓
API接口
        ↓
网页展示
```

连接起来。

否则前端只是静态页面，没有真实数据驱动。

下面这个计划书可以直接复制给 Codex。

文件名：

```
第二阶段_数据分析API开发计划.md
```

------

```
# 第二阶段：数据分析 API 开发计划

## 项目名称

上市财险公司年报智能分析 Agent

---

# 一、当前项目状态

目前已经完成：

## 第一阶段：年报解析与指标提取

流程：

PDF年报

↓

MinerU解析

↓

Markdown文件

↓

Chunk切片

↓

指标召回

↓

指标增强

↓

相关性排序

↓

LLM指标提取


最终输出：

database_result.csv


该文件作为后续所有数据分析模块的数据源。

---

# 二、第二阶段目标

开发数据分析模块 API。

目标：

将 database_result.csv 转化为可被网页调用的数据分析服务。


实现：

1. 公司指标查询
2. 指标横向比较
3. 描述性统计分析
4. 图表数据生成
5. AI分析报告的数据支撑


最终提供 REST API 给前端网页调用。

---

# 三、开发原则

## 1. 数据源统一

读取：
```

database/database_result.csv

```
禁止直接读取PDF或chunks。


所有分析基于结构化数据库。

---

## 2. 前后端分离

采用：

前端：

React / Vue


后端：

Python FastAPI


结构：
```

Frontend

```
 |
 |
```

FastAPI

```
 |
```

Analysis Engine

```
 |
```

database_result.csv

```
---

# 四、目录设计


建议新增：
```

project

├── database

│   └── database_result.csv

├── backend

│
 ├── main.py              # API入口
 │
 ├── analysis
 │   │
 │   ├── load_data.py     # 数据读取
 │   │
 │   ├── statistics.py    # 描述统计
 │   │
 │   ├── comparison.py    # 公司比较
 │   │
 │   └── report.py        # 分析报告生成
 │
 └── requirements.txt

```
---

# 五、数据库读取模块


开发：
```

load_data.py

```
功能：

1. 自动读取database_result.csv

2. 字段检查

3. 数据类型转换


需要识别字段：
```

company

year

report_period

market

indicator_id

indicator_name

indicator_value

unit

business_scope

confidence_score

```
输出：

pandas DataFrame


---

# 六、API设计


## 1. 获取公司列表


接口：
```

GET /companies

```
返回：

```json
[
 "中国人保",
 "中国平安",
 "中国太保"
]
```

------

## 2. 获取指标列表

接口：

```
GET /indicators
```

返回：

```
[
 {
 "id":"F006",
 "name":"综合成本率",
 "unit":"%"
 }
]
```

------

# 七、核心分析接口

## 1. 指标查询

接口：

```
GET /indicator/value
```

参数：

```
company

indicator

year
```

返回：

```
{
"company":"中国太保",
"indicator":"综合成本率",
"value":97.1,
"unit":"%"
}
```

------

## 2. 公司横向比较

接口：

```
GET /analysis/compare
```

输入：

```
indicator=综合成本率

year=2024
```

返回：

```
[
{
"company":"中国人保",
"value":98.2
},

{
"company":"中国太保",
"value":97.1
}
]
```

用于生成柱状图。

------

# 八、描述性统计模块

开发：

statistics.py

实现：

## 指标均值

例如：

综合成本率平均水平

## 最大值

风险最高公司

## 最小值

表现最好公司

## 排名

输出：

```
{
"mean":98.1,

"max_company":"中国平安",

"min_company":"中国太保"
}
```

------

# 九、图表数据接口

提供给前端。

## 柱状图

例如：

不同公司综合成本率比较。

接口：

```
GET /chart/bar
```

返回：

```
{
"title":"综合成本率比较",

"x":[
中国人保,
中国平安,
中国太保
],

"y":[
98.1,
97.5,
97.1
]
}
```

------

## 趋势图

接口：

```
GET /chart/trend
```

支持：

2022-2024年度变化。

------

# 十、业务分析报告接口

目标：

为后续AI报告模块提供数据。

接口：

```
GET /report/company
```

输入：

```
company=中国太保

year=2024
```

输出：

包括：

## 1. 基础经营情况

例如：

保费收入

市场规模

## 2. 盈利能力

净利润

综合成本率

承保利润

## 3. 偿付能力

核心偿付能力充足率

## 4. 风险分析

指标异常变化。

返回JSON。

------

# 十一、测试要求

完成后必须测试：

## 测试1

查询公司列表。

## 测试2

查询综合成本率。

## 测试3

生成4家公司横向比较。

## 测试4

生成一个公司分析报告数据。

------

# 十二、与前端连接

完成API后：

提供：

```
API文档

Swagger地址

接口说明
```

供网页调用。

------

# 十三、本阶段最终输出

完成：

```
backend

├── main.py

├── analysis

│   ├── load_data.py

│   ├── statistics.py

│   ├── comparison.py

│   └── report.py


requirements.txt


API接口文档
```

最终效果：

网页可以：

选择公司

↓

选择指标

↓

调用API

↓

展示：

- 图表
- 排名
- 分析结果

------

# 十四、注意事项

1. 不修改已有指标提取流程。
2. 不扩大指标库。
3. 所有分析基于database_result.csv。
4. 保持未来可以部署到服务器。
5. API设计需要考虑未来接入LLM生成报告。

```
---

你发给 Codex 后，我建议它完成这一阶段时**不要让它直接做网页美化**，重点检查三个东西：

1. **FastAPI 是否成功启动**
   
应该出现：
```

Uvicorn running on http://127.0.0.1:8000

```
2. 浏览器打开：
```

http://127.0.0.1:8000/docs

```
看到 Swagger API 页面。

3. API 返回的数据是否和你的 `database_result.csv` 一致。


完成第二阶段后，下一步才是：

**第三阶段：前端页面开发（把你给的UI设计图变成真实网页）**

届时前端直接调用这些 API，就可以实现你图里的：

- 数据分析看板
- 公司横向比较
- 指标趋势图
- AI业务分析报告

这时你的项目才从“脚本型Agent”真正变成“可展示的软件产品”。
```