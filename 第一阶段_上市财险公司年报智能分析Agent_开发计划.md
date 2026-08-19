# 上市财险公司年报智能分析 Agent
## 第一阶段开发计划书：数据分析模块 + 可公网部署 Web 技术架构设计

> 项目定位：两人小型 Agent 项目。当前已完成多家公司年报指标提取、人工核验，并已建设 `database.csv`。本阶段不扩大指标体系、不推翻已有算法，重点完成数据分析模块和可公网部署的 Web 整体架构。

## 一、现有项目与成果

整体流程：

```text
PDF → MinerU → Markdown → Chunks
→ 指标召回 → 上下文增强 → 相关性排序 → LLM 提取
→ 人工核验 → database.csv
→ 数据分析 → 分析报告 → 智能问答
```

### 1. PDF 解析 Agent

已有项目：

`/Users/mayuhang/Documents/parse_v1/`

请先阅读：

`/Users/mayuhang/Documents/parse_v1/README.md`

已有功能：PDF → Markdown → Markdown Splitter → JSON chunks。

本阶段只预留接口，不重新开发 PDF 解析算法。

### 2. 指标提取 Agent

已有项目：

`/Users/mayuhang/Documents/zd-agent0810/`

请阅读：

`/Users/mayuhang/Documents/zd-agent0810/database_readme_myh.md`

已有四阶段：

```text
召回 → 增强 → 排序 → LLM 提取
```

已经对多家公司进行人工核验。目前为 4 家上市公司 × 14 个指标，共 49 个可比格。

| 公司 | 一致 | 不一致 | 库中缺失 |
|---|---:|---:|---:|
| 中国人保 | 12 | 0 | 1 |
| 中国太保 | 12 | 1 | 1 |
| 中国平安 | 11 | 0 | 2 |
| 中国太平 | 1 | 0 | 8 |

不要重新扩大指标体系，不要重新设计已有提取算法。

### 3. 数据库

已经建设完成 `database.csv`。

必须先读取真实文件确认：

- 文件位置
- 编码
- 行列数
- 字段名
- 字段类型
- 公司
- 年份
- 指标
- 数值
- 单位
- 业务范围
- 空值
- 重复记录

不要假设字段结构，不要修改原始 CSV。

---

# 二、本阶段目标

只做两件事：

### A. 数据分析模块

将 `database.csv` 转化为真实、可复用、可供网页调用的分析结果，至少实现：

1. 公司列表
2. 年份列表
3. 指标列表
4. 单指标多公司横向比较
5. 单公司指标概览
6. 基础描述性统计
7. 排名
8. 年度变化（数据允许时）
9. 图表数据接口
10. 为分析报告提供结构化统计结果

### B. Web 整体技术架构

最终不是只能在我的 Mac 上运行的本地网页，而是：

> 可以部署到服务器，其他电脑通过浏览器访问。

推荐架构：

```text
浏览器
  ↓
React Web 前端
  ↓ HTTP / REST API
FastAPI 后端
  ↓
Python 数据分析 / Agent
  ↓
database.csv
```

未来再接入 PDF Agent、指标提取 Agent、报告 Agent、问答 Agent。

---

# 三、推荐技术栈

考虑到这是两人小型项目，不要过度工程化。

推荐：

```text
前端：React + Vite + TypeScript + ECharts + Ant Design（或同类组件库）
后端：Python + FastAPI
数据：database.csv + Pandas
未来：LLM API、PDF Agent、指标提取 Agent、问答 Agent
```

暂时不强制引入 MySQL/PostgreSQL。

---

# 四、数据分析模块

建议建立：

```text
backend/
├── data_loader.py
├── analysis/
│   ├── statistics.py
│   └── comparison.py
└── api/
```

### 1. 数据读取

`database.csv → DataFrame → 清洗 → 分析`

要求：

- 不修改原始 CSV
- 正确处理编码、空值、数字/字符串
- 不写死公司、年份、指标
- 不使用 `/Users/mayuhang/...` 绝对路径

### 2. 基础 API

至少设计：

```text
GET /api/companies
GET /api/years
GET /api/indicators
GET /api/analysis/comparison
GET /api/analysis/company
```

接口命名可根据实际情况优化，但必须清晰、方便前端调用。

### 3. 横向比较

例如：

```text
指标：综合成本率
年份：2024
```

API 返回数据库真实值：

```json
[
  {"company":"中国人保","value":98.2,"unit":"%"},
  {"company":"中国太保","value":97.1,"unit":"%"}
]
```

不能把数据复制到 React 代码中。

### 4. 单公司概览

根据数据库实际可用指标生成：

- 经营规模
- 盈利能力
- 业务结构
- 偿付能力
- 资产负债

具体分类优先使用已有指标字典/数据库信息，不重新扩大指标体系。

### 5. 描述性统计

针对同一指标分别计算：

- 最大值
- 最小值
- 平均值
- 中位数（样本允许时）
- 公司排名
- 与平均水平的差异

不同单位指标不能混合统计。

---

# 五、为分析报告预留结构化结果

本阶段暂时不要求完成完整报告，但必须能输出类似：

```json
{
  "company": "中国太保",
  "year": 2024,
  "metrics": {
    "综合成本率": {"value": 97.1, "unit": "%"},
    "保费增长率": {"value": 7.8, "unit": "%"}
  },
  "comparison": {
    "综合成本率": {
      "rank": 2,
      "company_average_difference": -1.1
    }
  }
}
```

以后再让 LLM：

```text
结构化统计结果 → 业务解释 → 分析报告
```

不要让 LLM 自己随意计算核心数字。

---

# 六、Web 页面

参考已有 UI 设计图，左侧导航保留：

```text
项目总览
文档解析
指标提取
数据分析
智能问答
```

本阶段重点完成：

**项目总览 + 数据分析**

其他页面先完成路由和占位。

## 项目总览

必须使用真实数据库数据，不要虚构：

```text
12 家公司
286 个指标
96.8%
```

等数字。

当前可根据真实数据动态显示：

```text
覆盖公司：4
核心指标：14
可比数据：49
数据质量：根据真实人工核验结果计算
```

如果某项暂时无法准确计算，不要虚构。

## 数据分析页面

建议：

```text
数据分析

公司：全部 ▼
年份：2024 ▼
指标：综合成本率 ▼

核心指标横向对比
        ↓
公司经营指标概览
        ↓
指标排名
        ↓
年度变化
```

图表优先使用 ECharts。

---

# 七、未来接口预留

虽然本阶段不实现全部功能，但目录和 API 要允许未来接入：

### PDF 解析

```text
POST /api/documents/upload
POST /api/documents/parse
GET  /api/documents/status
```

### 指标提取

```text
POST /api/extraction/start
GET  /api/extraction/status
GET  /api/extraction/result
```

### 智能问答

```text
POST /api/chat
```

---

# 八、部署兼容要求

最终用户应该：

```text
打开浏览器
↓
访问网站
↓
直接使用
```

不需要安装 Python、Node.js、Codex 或下载项目。

因此：

- 前后端分离
- 不依赖本机绝对路径
- 使用相对路径/环境变量/配置文件
- API Key 放 `.env`
- `.env` 加入 `.gitignore`
- 不把业务数据写死在前端
- 不把 API Key 写入代码

本阶段暂不锁定具体云平台。MVP 完成后再选择 Vercel/Render/Railway 或国内云服务器 + Nginx 等部署方案。

---

# 九、推荐目录

可以根据现有项目实际情况调整，但推荐：

```text
project/
├── backend/
│   ├── main.py
│   ├── api/
│   ├── analysis/
│   ├── data/
│   ├── services/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── data/
│   └── database.csv
├── docs/
└── README.md
```

不要为了迁移而删除或覆盖已有：

```text
/Users/mayuhang/Documents/zd-agent0810/
/Users/mayuhang/Documents/parse_v1/
```

如需移动文件，先说明原因并保留备份。

---

# 十、开发顺序

严格按以下顺序执行：

## Step 1：阅读现有项目

阅读：

```text
/Users/mayuhang/Documents/parse_v1/README.md
/Users/mayuhang/Documents/zd-agent0810/database_readme_myh.md
```

并定位 `database.csv`。

## Step 2：检查 database.csv

输出：

- 行数
- 列数
- 字段名
- 数据类型
- 公司数量
- 年份数量
- 指标数量
- 空值
- 重复
- 单位

## Step 3：设计数据分析层

完成：

```text
data_loader
statistics
comparison
```

## Step 4：设计 FastAPI

完成公司、年份、指标、比较分析、公司分析等 API。

## Step 5：设计 React

完成项目总览和数据分析页面。

## Step 6：前后端联调

确认：

```text
React
 ↓
FastAPI
 ↓
Python
 ↓
database.csv
```

真实跑通。

## Step 7：完善 README

说明：

- 项目结构
- 环境要求
- 后端启动
- 前端启动
- API
- 数据文件
- 环境变量
- 开发模式
- 未来部署方式

---

# 十一、明确禁止

本阶段不要：

1. 扩大指标体系
2. 重新设计四阶段指标提取算法
3. 重新跑历史年报
4. 虚构数据库数据
5. 把数据写死在前端
6. 使用本机绝对路径
7. 将 API Key 写入代码
8. 为了展示效果制造不存在的公司/指标
9. 过度工程化
10. 为了使用数据库而强制引入关系型数据库

这是一个两人小型项目，优先保证**完整、真实、可运行、可展示**。

---

# 十二、Codex 执行要求

不要一次性生成大量代码。

采用：

```text
检查现有项目
 ↓
分析 database.csv
 ↓
提出技术架构
 ↓
创建最小可运行后端
 ↓
测试 API
 ↓
创建最小可运行前端
 ↓
联调
 ↓
逐步完善 UI
```

每一步都运行实际测试。

如果现有项目结构与计划冲突，优先保护已有 Agent 代码，不要直接删除或覆盖。

---

# 十三、验收标准

完成后应能够在本地开发环境启动：

```bash
cd backend
python3 -m uvicorn main:app --reload
```

以及：

```bash
cd frontend
npm install
npm run dev
```

并满足：

- 网页可以读取真实 `database.csv`
- 公司列表动态读取
- 指标列表动态读取
- 年份动态读取
- 可以选择指标并进行公司横向比较
- 图表与 CSV 可以人工核对
- 前端没有写死业务数据
- 没有 `/Users/mayuhang/...` 绝对路径依赖
- API Key 不出现在代码或 Git 中
- 项目可按 README 在另一台电脑启动
- 架构可以继续接入 PDF 解析、指标提取、分析报告、智能问答

---

# 十四、最终产品目标

最终形成：

```text
上市财险公司年报智能分析 Agent

                浏览器
                   ↓
              Web 前端
                   ↓
              FastAPI API
                   ↓
        ┌──────────┼──────────┐
        ↓          ↓          ↓
      文档解析    指标提取    数据分析
        ↓          ↓          ↓
     Markdown     指标数据   database.csv
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
                 分析报告             智能问答
```

最终用户只需要访问网站，即可完成：

```text
上传年报
 ↓
自动解析
 ↓
自动提取指标
 ↓
进入数据库
 ↓
公司横向分析
 ↓
生成分析报告
 ↓
业务问答
```

**本阶段的核心原则：先把真实数据分析闭环和 Web 架构做稳，再逐步把已经完成的 PDF 解析 Agent、指标提取 Agent、分析报告 Agent 和问答 Agent 接入。**
