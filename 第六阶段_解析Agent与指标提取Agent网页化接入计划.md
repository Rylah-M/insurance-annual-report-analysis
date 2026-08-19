```
# 第六阶段_解析Agent与指标提取Agent网页化接入计划


## 一、项目背景


当前项目：

“上市财险公司年报智能分析Agent”


已经完成以下核心能力：

1. 年报PDF解析Agent

功能：

PDF文件
↓
MinerU解析
↓
Markdown生成
↓
Markdown Splitter切片
↓
生成结构化chunks


2. 指标提取Agent

功能：

chunks
↓
指标召回
↓
候选增强
↓
rerank排序
↓
LLM指标提取
↓
结构化指标结果


目前两个Agent均已通过命令行方式运行测试。


下一阶段目标：

将已有两个Agent能力接入Web系统。


实现：

用户上传PDF年报

↓

网页调用解析Agent

↓

自动生成chunks

↓

网页调用指标提取Agent

↓

生成database_result

↓

进入数据分析页面



最终实现完整闭环：

PDF上传 → 自动解析 → 自动指标提取 → 数据分析展示



---

# 二、当前代码位置


## 1. 年报解析Agent


路径：
```

/Users/mayuhang/Documents/解析&提取_0814V1/Annual_Report_Analysis

```
该目录负责：

PDF解析流程。


需要阅读：

/Users/mayuhang/Documents/解析&提取_0814V1/Annual_Report_Analysis/parse_v1/README文件


重点理解：

- PDF上传入口
- MinerU调用方式
- Markdown生成方式
- chunks生成方式
- 当前输入输出格式



---

## 2. 指标提取Agent


路径：
```

/Users/mayuhang/Documents/解析&提取_0814V1/zd-agent0811

```
该目录负责：

指标召回和LLM提取。


核心流程：
```

chunks.json

↓

chunk_indicator_match.py

↓

chunk_rerank.py

↓

indicator_extract_agent.py

↓

extracted_indicator_result.json

```
需要保持现有流程逻辑。


---

# 三、本阶段开发目标


## 目标1：Web上传PDF调用解析Agent


新增功能：


网页增加：

“上传年报”模块。


用户输入：
```

PDF文件

公司名称

年份

报告期(Q1/Q2/Q3/Q4)

市场(A股/H股)

```
点击：
```

开始解析

```
后端：

接收PDF文件

调用：

Annual_Report_Analysis


自动完成：

PDF解析

Markdown生成

chunks生成



返回：
```

解析任务ID

解析状态

chunks路径

```
---

# 目标2：增加解析任务状态管理


由于PDF解析时间较长，需要增加任务状态。


状态包括：
```

waiting

processing

success

failed

```
进度显示：

网页显示：
```

PDF上传完成        10%

MinerU解析          40%

Markdown生成        70%

Chunk切片完成        100%

```
---

# 目标3：Web调用指标提取Agent


解析完成后：

自动触发指标提取流程。



调用：

zd-agent0811



执行：


## 第一步：指标召回


运行：
```

chunk_indicator_match.py

```
输出：
```

indicator_match_result.json

```
网页显示：
```

指标召回完成

```
---

## 第二步：候选增强和排序


运行：
```

chunk_rerank.py

```
输出：
```

indicator_match_result_v3.json

```
网页显示：
```

候选排序完成

```
---

## 第三步：LLM指标提取


运行：
```

indicator_extract_agent.py

```
输出：
```

extracted_indicator_result.json

```
网页显示：
```

指标提取完成

```
---

# 四、后端API设计


新增接口。


## 1. 上传年报接口


POST
```

/api/report/upload

```
输入：

multipart/form-data


内容：
```

file

company

year

quarter

market

```
返回：


```json
{
"task_id":"",
"status":"uploaded"
}
```

------

## 2. 查询解析进度接口

GET

```
/api/report/status/{task_id}
```

返回：

```
{
"status":"processing",
"progress":60,
"stage":"Markdown生成"
}
```

------

## 3. 启动指标提取接口

POST

```
/api/indicator/extract/{task_id}
```

执行：

chunk_indicator_match.py

↓

chunk_rerank.py

↓

indicator_extract_agent.py

返回：

```
{
"status":"success",
"result_file":""
}
```

------

## 4. 获取指标结果接口

GET

```
/api/indicator/result/{task_id}
```

返回：

结构化指标数据。

例如：

```
{
"company":"中国太保",
"year":"2024",
"indicator_name":"综合成本率",
"value":"97.1",
"unit":"%"
}
```

------

# 五、前端页面开发

## 页面1：首页

增加入口：

```
上传年报
```

------

## 页面2：解析页面

展示：

上传文件

参数选择

解析按钮

实时显示：

任务状态

进度条

------

## 页面3：指标提取页面

展示：

四阶段进度：

```
① 指标召回

② 候选排序

③ LLM提取

④ 数据生成
```

展示结果：

表格形式：

| 指标       | 数值 | 单位 | 置信度 |
| ---------- | ---- | ---- | ------ |
| 综合成本率 | 97.1 | %    | 0.98   |

------

# 六、数据库更新

当前：

database.csv

增加自动更新流程。

指标提取完成后：

自动追加：

```
company

year

quarter

market

indicator_name

indicator_value

source_text

confidence_score
```

保持历史数据。

不要覆盖已有数据。

------

# 七、代码结构建议

最终结构：

```
project

├── frontend

│

├── backend

│
├── services

│   ├── parse_service.py

│   ├── indicator_service.py


├── agents

│
│   ├── Annual_Report_Analysis

│   └── zd-agent0811


├── database


└── README.md
```

------

# 八、开发要求

## 1.

不要重新开发解析逻辑。

直接封装已有代码。

## 2.

不要修改指标提取核心算法。

只增加调用接口。

## 3.

保证命令行运行结果和网页运行结果一致。

## 4.

保留日志。

方便查看：

- PDF解析失败原因
- 指标提取失败原因

------

# 九、本阶段验收标准

完成后：

用户可以：

1. 

打开网页

1. 

上传一个新的财险公司年报PDF

1. 

选择：

公司

年份

季度

市场

1. 

点击开始分析

系统自动：

PDF解析

↓

生成chunks

↓

指标召回

↓

排序

↓

LLM提取

1. 

网页展示：

指标结果

1. 

自动进入：

数据分析页面

最终实现：

“上传一份新的上市财险公司年报，系统自动完成解析和指标提取。”

```
---

补充一个建议：

你现在这一步**不要让 Codex 直接改大量代码**。

最好的执行顺序是：

1. 先让 Codex 阅读：
```

Annual_Report_Analysis/README.md
 zd-agent0811/README.md

```
2. 让它输出：
```

当前两个Agent的输入输出接口分析
 以及Web接入方案

```
3. 确认方案后再写代码。

因为你现在已经有两个成熟模块，最大风险不是不会写，而是**接口接错导致已有成果被破坏**。这一步重点是“封装连接”，不是重新开发。
```