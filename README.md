# 上市财险公司年报智能分析 Agent

已完成阶段：

- 数据分析模块：读取 `data/database.csv`，输出公司、年份、指标、横向比较、公司概览、描述性统计、排名、年度变化和报告快照结构。
- Web 技术架构：React + Vite 前端通过 REST API 调用 FastAPI 后端，后端通过 pandas 读取 CSV。
- PDF 解析与指标提取接口已接入 Web，不再只是占位。
- 前端 Web 展示系统：完成 Dashboard、数据分析、业务分析结果页面。
- 第五阶段：自动分析报告 Agent、智能问答 Agent、SQLite 结构化指标库与 Docker 部署环境已完成。
- 第六阶段：解析 Agent 与指标提取 Agent 已接入 Web 系统，支持上传年报 PDF 后自动完成
  PDF 解析、chunks 生成、指标召回、候选排序、LLM 提取与数据库更新。
- 第七阶段：保险上市公司经营分析 Agent V2 已完成，读取产险对标 Excel，内置
  Analysis Engine（趋势、横向对标、结构、增长贡献、盈利质量、规模×盈利矩阵、
  指标联动、风险信号、阳光专项），形成带证据链与置信度的 Insight，并输出
  `2025年上市公司产险经营分析.md` 与 `.pdf`。

## 项目结构

```text
.
├── backend/
│   ├── main.py
│   ├── data_loader.py
│   ├── database.py
│   ├── services/
│   │   ├── parse_service.py
│   │   ├── indicator_service.py
│   │   ├── task_store.py
│   │   ├── llm_settings.py
│   │   └── mineru_manager.py
│   ├── agent/
│   │   ├── report_agent.py
│   │   ├── chat_agent.py
│   │   └── pdf_agent.py
│   ├── api/
│   ├── analysis/
│   ├── report/analysis_reports/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   └── pages/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── agents/
│   ├── parse-agent0820/
│   └── zd-agent0811/
├── data/
│   └── database.csv
├── Dockerfile
├── docker-compose.yml
├── docs/
└── 上市财险公司年报智能分析Agent_第一阶段开发计划书.md
```

## 数据文件

本项目默认使用 `database/database_result.csv`，由第六阶段指标提取完成后自动从
`agents/zd-agent0811/database_result/database.csv` 同步而来。若
`database/database_result.csv` 不存在，后端会回退读取 `data/database.csv`。
当前真实数据画像：

- 编码：UTF-8 with BOM
- 行数：448 条数据记录
- 列数：18
- 公司：6 家（中国人保、中国太保、中国太平、中国平安、中国阳光、众安在线）
- 年份：2024、2025
- 指标：以财险公司经营指标体系为准（盈利、规模、偿付能力、资产负债等）
- 重复记录：0
- 单位：`百万元`、`%`

第五阶段起，后端首次启动时会自动将 CSV 同步为 SQLite 结构化数据库
（`data/database.db`），包含 `company_info`、`indicator_data`、`report_info`
三张表。若 SQLite 初始化失败，系统自动回退读取 CSV，保证既有接口兼容。

第六阶段起，指标提取完成后会自动把 Agent 生成的
`database_result/database.csv` 同步到项目 `database/database_result.csv`
并重建 SQLite 指标库，历史记录不会覆盖。

## 第五阶段：完成情况

第五阶段完成“智能分析 Agent 能力完善与系统部署”：

- 自动分析报告 Agent：选择公司与年份一键生成经营分析报告，包含摘要、关键发现、
  业务规模、盈利能力、偿付能力、投资能力、风险与复核提示，并生成 JSON /
  Markdown / HTML / PDF 文件；
- 智能问答 Agent：数据库检索 + LLM 回答，带数据来源引用，接口不可用时自动回退
  模板回答；
- SQLite 结构化指标库：`data/database.db` 包含 `company_info`、`indicator_data`、
  `report_info` 三张表，首次启动自动从 CSV 同步，失败时回退 CSV；
- Docker 部署环境：`Dockerfile` + `docker-compose.yml`，挂载数据与报告目录。

## 第六阶段：完成情况

第六阶段完成“解析 Agent 与指标提取 Agent 网页化接入”，实现
“上传 PDF → 自动解析 → 自动指标提取 → 数据分析展示”完整闭环。

### 1. 解析 Agent 网页化

- “上传年报”页面支持上传 PDF，填写公司、年份、报告期（Q1-Q4）、市场（A股/H股）；
- 支持选择解析页码范围（起始页、结束页、阅读器页码/物理页码模式）；
- 支持自定义 chunks 输出命名，默认自动生成 `<公司>_<年份>_<报告期>_<市场>`；
- 后台封装 `agents/parse-agent0820`，不改动原解析逻辑，直接调用
  MinerU API 完成 PDF → Markdown → chunks；
- 页面实时显示任务进度：PDF 上传完成 10% → MinerU 解析 40% → Markdown 生成 70%
  → Chunk 切片完成 100%。

### 2. 任务状态与终止

- 任务状态包含 `waiting / uploaded / processing / extracting / success / failed /
  cancelled`；
- 解析或指标提取过程中可点击“终止任务”取消，取消后自动恢复 MinerU 服务；
- “最近解析任务”列表保留历史任务，切换左侧栏目不会中断后台任务，回到页面可继续
  查看进度与日志；
- 解析失败与提取失败原因会完整记录在任务日志中，可通过状态接口查看。

### 3. 指标提取 Agent 网页化

- 解析完成后可启动指标提取，按原 Agent 流程依次执行：
  指标召回（`chunk_indicator_match.py`）→ 候选增强（`indicator_match_enhance.py`）
  → 候选排序（`chunk_rerank.py`）→ LLM 指标提取（`indicator_extract_agent.py`）
  → 数据生成（`generate_indicator_database.py`）；
- 页面展示五阶段进度与提取结果表格（指标、数值、单位、置信度、业务范围），并支持
  查看来源原文；
- 提取完成后自动把 Agent 生成的 `database_result/database.csv` 同步到项目
  `database/database_result.csv` 并重建 SQLite 指标库，历史数据不会被覆盖。

### 4. 模型设置

- 左侧新增“模型设置”页面，可输入 API Key 与 LLM 接口地址，支持“测试连接”；
- Key 保存在本机 `data/llm_settings.json`（权限 600），网页只显示掩码；
- 指标提取子进程自动使用网页保存的 Key 与接口地址。

### 5. 第六阶段新增接口

```text
POST /api/report/upload
GET  /api/report/status/{task_id}
POST /api/report/cancel/{task_id}
GET  /api/report/tasks
POST /api/indicator/extract/{task_id}
GET  /api/indicator/result/{task_id}
GET  /api/settings/llm
POST /api/settings/llm
POST /api/settings/llm/test
```

### 6. 运行前提

- MinerU API 服务需先启动，默认地址 `http://127.0.0.1:8001`，可通过
  `MINERU_API_BASE_URL` 覆盖；
- LLM 指标提取使用网页“模型设置”中保存的 API Key；默认接口地址
  `https://api.nwafu-ai.cn/v1`（模型 `deepseek-chat`），可通过设置页修改；
- 解析失败与提取失败的详细日志会保留在任务状态接口中，方便排查。

## 第七阶段：完成情况

按《第七阶段_保险上市公司经营分析Agent_V2_计划书_Excel到PDF_MD.md》实现
`excel_report_agent/` V2：

- `excel_reader.py`：读取 `3-产险对标` Sheet，标准化指标、公司、期间、数值、同比与备注；
- `analysis.py`：Analysis Engine，完成趋势、横向对标、结构、增长贡献、盈利质量、
  规模×盈利矩阵、指标联动、风险信号与阳光专项分析，生成带证据链、置信度和
  So What 的 Insight；
- `narrative.py`：生成完整 Markdown 分析母版；
- `pdf_builder.py`：生成正式 PDF（页眉页脚、页码、表格、图表与图表结论）；
- `critic.py`：Quality Critic Agent 独立审稿（数据/分析/逻辑/报告/So What）；
- 运行方式：
  ```bash
  cd /Users/mayuhang/Documents/UI_0813
  /Users/mayuhang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
    -m excel_report_agent.main --output output/产险报告
  ```
- 最终输出（仅两个文件）：`2025年上市公司产险经营分析.md` 和
  `2025年上市公司产险经营分析.pdf`。

## 已知问题与注意事项

- **MinerU 依赖与运行时更新**：Codex 预置 Python 运行时更新后，之前通过
  `pip install` 安装的 `mineru`、`fastapi`、`torch` 等依赖会被清空。若启动
  `mineru-api` 提示找不到文件，需重新安装：
  ```bash
  /Users/mayuhang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
    -m pip install fastapi uvicorn python-multipart sqlalchemy requests openai "mineru[pipeline]"
  ```
- **端口占用**：本项目后端占用 8000，MinerU 使用 8001。若 8000 已被其他服务占用，
  可修改启动参数；MinerU 启动地址与解析服务保持一致。
- **解析耗时**：完整年报 PDF（约 366 页）单次解析约 8-10 分钟，MinerU 单并发，
  页面显示进度期间请勿重复上传同一份报告，避免重复排队。
- **LLM API Key**：本机默认 Key 对 DeepSeek 官方接口无效，但对
  `https://api.nwafu-ai.cn/v1` 有效，因此指标提取默认使用该接口；更换 Key 后请在
  “模型设置”页重新保存并“测试连接”。
- **API Key 安全与机器绑定**：`data/llm_settings.json` 已加入 `.gitignore` 和
  `.dockerignore`，不会进入版本库或 Docker 镜像。Key 在保存时绑定本机硬件标识；
  项目分发给其他电脑后，即使文件被一起复制，对方机器也会自动清除该 Key 并提示
  重新配置，无法直接使用原 Key。旧版本未绑定的 Key 在重启后同样需要重新保存一次。
- **自动报告饼图**：曾出现环形图不圆/内孔变形问题，已改为 SVG 描边圆环绘制
  （stroke-dasharray），外圆与内孔均为正圆；修改后需重启后端并重新生成报告。
- **同一年多报告期**：自动报告目前按“公司 + 年份”生成，若数据库同年存在多个报告期
  （如 2025Q2 与 2025Q4），指标会取同年最后一条记录，暂未提供报告期选择。
- **Docker 部署范围**：容器包含 Web 后端与前端构建，但 PDF 解析与指标提取依赖本机
  MinerU 服务和 LLM 网络访问，容器化部署时建议将解析/提取服务放在宿主机或独立服务中。

## 后端启动

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

首次调用数据接口时会自动把 `database/database_result.csv` 同步为 SQLite
数据库；未安装额外 Python 依赖时，也可直接使用预置 Python 运行时：

```bash
cd backend
/Users/mayuhang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## MinerU 解析服务启动

PDF 解析依赖 MinerU 本地服务，需单独保持一个终端运行（端口 8001）：

```bash
/Users/mayuhang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/mineru-api \
  --host 127.0.0.1 --port 8001
```

启动后可访问 `http://127.0.0.1:8001/health` 确认返回 `healthy`。

API 文档：

```text
http://127.0.0.1:8000/docs
```

第四阶段后，后端也会托管前端生产构建。只启动 FastAPI 后即可直接打开：

```text
http://127.0.0.1:8000/
```

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:5173
```

开发模式下，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 前端页面

第三阶段已完成浏览器可访问的数据分析展示系统：

- `项目总览`：展示项目名称、覆盖公司数量、指标数量、数据记录数量、年报覆盖范围和数据文件画像
- `数据分析`：支持选择公司、年份、指标，展示指标详情、业务范围、数据来源、柱状图、趋势图、描述性统计、排名表和公司经营画像
- `业务分析`：展示基础经营情况、盈利能力、偿付能力、风险分析和复核提示

第五阶段新增页面：

- `自动报告`：选择公司与年份，一键生成经营分析报告，展示文字分析、图表，
  支持下载 PDF、Markdown、HTML。
- `智能问答`：ChatGPT 风格聊天窗口，输入业务问题后由数据库检索 + LLM
  生成回答，并展示数据来源。
- `项目总览`：展示系统介绍、数据覆盖情况、已分析公司数量与指标数量。

第六阶段新增页面：

- `上传年报`：PDF 上传、公司/年份/报告期/市场选择、页码范围、chunks 命名、
  实时进度与终止按钮、最近任务列表。
- `指标提取`：五阶段进度展示、提取结果表格与来源原文。
- `模型设置`：配置指标提取使用的 API Key 与 LLM 接口地址，支持测试连接。

## 主要 API

```text
GET /companies
GET /indicators
GET /indicator/value?company=中国太保&indicator=综合成本率&year=2024
GET /analysis/compare?indicator=综合成本率&year=2024
GET /chart/bar?indicator=综合成本率&year=2024
GET /chart/trend?company=中国太保&indicator=综合成本率
GET /report/company?company=中国太保&year=2024
```

兼容第一阶段前端的 `/api` 前缀接口仍然保留：

```text
GET /api/metadata
GET /api/companies
GET /api/years
GET /api/indicators
GET /api/analysis/comparison?indicator=综合成本率&year=2024
GET /api/analysis/company?company=中国太保&year=2024
GET /api/analysis/trend?company=中国太保&indicator=综合成本率
GET /api/analysis/report-snapshot?company=中国太保&year=2024
```

第五阶段新增接口：

```text
POST /api/report/generate     生成公司经营分析报告（JSON + 文件）
GET  /api/report/download     下载报告 PDF / Markdown / HTML / JSON
GET  /api/report/artifacts    查询已生成报告清单
POST /api/chat                智能问答
```

第六阶段新增接口（解析、指标提取、模型设置）见“第六阶段：完成情况”一节。

## LLM 配置

智能问答默认使用数据库检索 + 模板回答，不依赖外部服务。配置以下环境变量后，
会自动调用 OpenAI 兼容接口生成更自然的回答；接口不可用时自动回退模板回答：

```text
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

指标提取使用另一套配置：在网页“模型设置”页保存 API Key 与接口地址，后端写入
`data/llm_settings.json`，执行指标提取时自动传给 Agent。默认接口地址
`https://api.nwafu-ai.cn/v1`，模型固定为 `deepseek-chat`。

## Docker 部署

```bash
docker compose up -d --build
```

构建完成后，其他电脑通过服务器地址访问：

```text
http://服务器地址:8000
```

容器会挂载 `./data`（SQLite 数据库）、`./backend/report/analysis_reports`
（生成报告）与 `./agents`（解析/提取 Agent 代码），重启后数据仍然保留。

## 第二阶段验收结果

已验证：

- Swagger：`GET /docs` 返回 200
- 公司列表：`GET /companies` 返回 `["中国太保"]`
- 指标查询：`GET /indicator/value?company=中国太保&indicator=综合成本率&year=2024` 返回 `97.1%`
- 横向比较：`GET /analysis/compare?indicator=综合成本率&year=2024` 返回当前数据库中的真实公司记录
- 图表数据：`GET /chart/bar`、`GET /chart/trend` 返回 `x/y` 图表数据
- 公司报告：`GET /report/company?company=中国太保&year=2024` 返回基础经营情况、盈利能力、偿付能力、风险分析 JSON

第二阶段计划中的“生成 4 家公司横向比较”当前无法形成 4 家样本，因为真实 `database_result.csv` 只有 1 家公司。接口已按多公司通用逻辑实现，后续补充多家公司数据后会自动返回多家公司比较结果。

## 第三阶段验收结果

已验证：

- `frontend/src/pages/Dashboard.tsx`、`Analysis.tsx`、`Report.tsx` 页面已拆分完成
- `frontend/src/components/Chart.tsx` 使用 ECharts 输出柱状图和折线图
- `frontend/src/components/Selector.tsx` 提供公司、年份、指标选择器
- 所有展示数据均通过 FastAPI 获取，未在前端写死业务数据
- `./node_modules/.bin/tsc --noEmit` 通过
- `./node_modules/.bin/vite build` 通过

## 第四阶段验收结果

已完成前后端联调与数据分析页增强：

- 后端新增并验证 `GET /api/company`
- 后端新增并验证 `GET /api/quarters`
- 后端新增并验证 `GET /api/data?company=中国太保&year=2024&quarter=2024Q3`
- 后端新增并验证 `GET /api/compare?year=2024&quarter=2024Q3`
- 数据分析页改为公司、年份、报告期查询，并提供“开始分析”按钮
- 页面展示业务规模、盈利能力、风险指标卡片
- 页面展示公司横向比较表
- 页面展示保费规模柱状图、综合成本率柱状图、车险/非车险业务结构饼图、趋势折线图
- FastAPI 根路径 `http://127.0.0.1:8000/` 已托管前端页面，API 与页面可共用同一服务入口

## 环境变量

前端可通过 `.env` 配置 API 地址：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

`.env` 已加入 `.gitignore`。后续接入 LLM API 时，API Key 也应只放在环境变量中，不能写入代码。

## 部署思路

MVP 可采用：

```text
浏览器
  ↓
React 静态资源
  ↓ HTTP / REST API
FastAPI
  ↓
pandas 分析层
  ↓
data/database.csv
```

部署到服务器时，将前端构建产物托管在 Nginx、Vercel 或对象存储，将 FastAPI 部署到 Render、Railway、云服务器或容器平台。生产环境建议将 `data/database.csv` 替换为挂载文件、对象存储同步文件或后续数据库服务。
