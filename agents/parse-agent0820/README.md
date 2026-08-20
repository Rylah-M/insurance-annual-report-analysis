# parse_v1 · 年报 PDF 解析 Agent（含 Markdown Splitter）

带 Web 界面的年报 PDF 解析 Agent：上传 PDF → 选择或输入公司 / 下拉选择年份 /
报告时间（Q1-Q4）/ 市场（可选，未上市可不选）
（命名与数据库标准一致）→ 开源 MinerU 解析 → **Markdown Splitter 后处理**
→ 输出原始 Markdown + 结构化 JSON chunks。

## 整体流程

```
PDF 上传（Web 界面）
      │
      ▼
parse agent（app.py → parser.py）
      │  requests POST /file_parse（backend=pipeline）
      ▼
MinerU API 服务（localhost:8000，外部依赖）
      │
      ▼
原始 Markdown
      │
      ▼
Markdown Splitter（cleaner.py + splitter.py + output_manager.py）
      │
      ▼
output/<公司>_<年份>_<报告时间>_<市场>/
    ├── <公司>_<年份>_<报告时间>_<市场>.md             MinerU 原始 Markdown
    ├── <公司>_<年份>_<报告时间>_<市场>_chunks.json    按标题层级切分的结构化文本块
    └── <公司>_<年份>_<报告时间>_<市场>_metadata.json  文件基本信息
```

## 输出示例

```
output/中国平安_2012_Q3_A股/
    中国平安_2012_Q3_A股.md
    中国平安_2012_Q3_A股_chunks.json
    中国平安_2012_Q3_A股_metadata.json

未上市的公司可不选市场，命名自动省略市场段：

output/大地财险_2025_Q4/
    大地财险_2025_Q4.md
    大地财险_2025_Q4_chunks.json
    大地财险_2025_Q4_metadata.json
```

chunks.json 中单个 chunk 的结构：

```json
{
  "chunk_id": "pingan_2012_q3_a_001",
  "company": "中国平安",
  "year": 2012,
  "quarter": "Q3",
  "market": "A股",
  "section": "经营情况讨论与分析",
  "title": "财产保险业务",
  "content": "该章节完整文本内容（含标题层级，已删除图片引用）",
  "tables": [
    {
      "table_id": "table_001",
      "content": "<table>...</table> 或 markdown 管道表格"
    }
  ],
  "position": 1
}
```

metadata.json：

```json
{
  "company": "中国平安",
  "year": 2012,
  "quarter": "Q3",
  "market": "A股",
  "source_file": "中国平安2012年三季报.pdf",
  "total_chunks": 312,
  "created_time": "2026-08-10 15:00:00"
}
```

## 代码结构

```
parse_v1/
├── app.py                   # Web 界面（上传 + 下拉菜单 + 解析进度 + 下载）
├── parser.py                # MinerU 解析（PDF → raw.md，含后处理调度）
├── cleaner.py               # Markdown 清洗：删除图片引用，保留标题/正文/表格
├── splitter.py              # Markdown → chunks.json（基于标题层级切分）
├── output_manager.py        # 统一输出目录管理与 metadata.json
├── test_splitter.py         # Splitter 验证测试
├── start_mineru_api.sh      # 启动 MinerU API 服务
├── config/
│   └── companies.json       # 年份 / 报告时间 / 市场 + company_codes（公司不预设）
├── data/                    # uploads / tmp / mineru_api_output
├── output/                  # 最终结果（raw.md + chunks.json + metadata.json）
└── test_output/             # test_splitter.py 的输出
```

对应你建议的 parse_agent 结构：`mineru_parser.py = parser.py`（为避免破坏正在运行的
界面，保留了原文件名），其余模块一一对应。

## Markdown Splitter 切分规则

**不按固定字数、不按句切分**，基于 Markdown 标题层级：

1. 默认粒度：一级标题（`section`）+ 二级标题（`title`），每个 chunk 包含该
   二级标题下的**完整正文**与**全部表格**；
2. 年报编号标题（`一、` / `（一）` / `1、` / `（1）`）会被识别为更低层级，
   嵌套在真实章节之内，不再单独成 chunk，避免碎片化；
3. 纯数字标题（MinerU 常把页码识别成 `## 14`）作为噪声并入父级；
4. 跨页续段（如 `11. 其他资产(续)`）自动并入原章节 chunk；
5. 超长章节（默认超过 **12000 tokens**，可通过 `max_tokens` 调整）才允许继续
   拆分：先按三级标题 `###`，再按段落（空行）切分，切分后保留
   `section` / `title`；
6. 表格（HTML `<table>` 或 Markdown 管道表格）从正文中提取，放入 chunk 的
   `tables` 字段并**绑定到所属章节**，**禁止表格单独成 chunk**；
7. 图片引用（`![](images/xxx.jpg)`、`<img>`）在 chunk 内容中删除，图片附近的
   文本保留。

### 效果（太保24Q2 完整样本，146 页）

- chunk 数量：143（目标：300 页年报 50-150 chunks）
- 表格：162/162 全部保留并绑定到章节
- 图片引用：45 处全部删除，正文与表格不受影响

## 使用步骤

### 0 秒上手：一键启动（推荐）

macOS 上直接双击项目里的 **start.command**（或桌面上的“启动Agent.command”），
会自动启动 MinerU 解析服务和 Web 界面，并打开浏览器；服务以后台方式运行，
日志在 `data/logs/` 下。终端里也可以一条命令启动：

```bash
bash start.command
```

> 服务会随电脑重启而停止，下次使用再双击一次即可，不需要手动 `cd` 或输入命令。

### 环境准备（目标电脑首次使用）

前置要求（二选一）：

- 方式 A：安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或
  Anaconda（macOS / Linux / Windows 均可）；
- 方式 B：本机已有 **Python 3.10-3.13**（MinerU 3.4.4 的要求，3.9 及以下不支持）。

一键安装（推荐）：

```bash
bash setup.sh
```

setup.sh 会自动检测：有 conda 就用 conda 环境，没有就用系统 Python 在项目内创建
`.venv`；然后安装 streamlit / requests → 安装开源 MinerU → 下载 MinerU 模型
（约 1-2 GB）。如果模型下载失败，先执行 `export MINERU_MODEL_SOURCE=modelscope`
再重跑。

也可以不运行 setup.sh，手动创建虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install mineru
mineru-models-download
```

Windows 激活虚拟环境用 `.venv\Scripts\activate`。

或手动安装：

```bash
conda create -n annual_report python=3.11 -y
conda activate annual_report
pip install -r requirements.txt
pip install mineru
mineru-models-download
```

### Step 1：启动 MinerU API 服务

```bash
./start_mineru_api.sh
```

### Step 2：启动 Web 界面

```bash
conda activate annual_report
streamlit run app.py
```

浏览器打开 http://localhost:8501：上传 PDF → 公司支持下拉选择（之前解析过的
公司）或手动输入任意公司名称 → 下拉选择年份 / 报告时间 / 市场（未上市选
“不选（未上市）”）→ 点击“开始解析”。完成后可下载 `<输出名>.md`、
`<输出名>_chunks.json`、`<输出名>_metadata.json`，并在线预览正文与前 5 个 chunk。

### Step 3：命令行单独使用（测试 / 批量）

```bash
python parser.py 中国平安2024年度报告.pdf \
  --company 中国平安 --year 2012 --quarter Q3 --market A股
```

常用参数：`--quarter Q1-Q4`（可选）、`--start-page/--end-page`、
`--keep-images`、`--overwrite`。

> 页码说明：
> - 默认按 **PDF 阅读器显示的页码** 输入，系统自动读取 PDF 页码标签做映射
>   （例如物理第 36 页在阅读器里显示为 32，就填 32）；没有页码标签的 PDF
>   直接按物理页码（1 起）处理。
> - 部分 PDF 存在**重复页码**（如附录重新从 1 编号），此时无法自动判断指向哪一段，
>   界面会给出提示并展示“页码对照表”；请切换到 **“按物理页码（PDF 第 N 页）”**
>   模式，按对照表左侧的物理页码输入（命令行加 `--page-mode physical`）。
> - 界面默认解析全部页（结束页填 0）。

### Step 4：运行 Splitter 测试

```bash
python test_splitter.py                 # 使用项目内已有太保 md 样本
python test_splitter.py --input a.md    # 指定输入
```

输出到 `test_output/`（raw.md + chunks.json + metadata.json），并检查：
章节切分、表格保留数量一致、图片引用已删除、JSON 可正常读取。

## 关键约定

- **MinerU 不作为 Python 库直接调用**：先启动 `mineru-api`（8000 端口），
  parse agent 通过 HTTP POST `/file_parse` 调用；
- **backend 固定 `pipeline`**：避免触发 VLM 模型下载（约 2.3GB）；
- **不要依赖 `mineru` CLI 自动拉起临时 API**：容易出现 502，服务单独运行；
- API 表单字段使用 3.4.4 正确的 `lang_list / start_page_id / end_page_id /
  table_enable / formula_enable`（旧脚本里的 `lang / start_page` 等会被忽略）。

## 未来兼容性

- 支持多公司 / 多年份 / 多报告时间 / 多市场，**不硬编码**：company / year /
  quarter / market 由 parse agent 传入；
- 公司支持界面手动输入，无需配置；如需要快捷预设项，在 `config/companies.json`
  的 `companies` 列表添加即可；
- `company_codes` 用于已知公司生成规范 chunk_id（如 `pingan_2012_q3_a_001`），
  未登记的公司回退使用公司名作为代码；
- 市场代码映射：A股→a，H股/港股→h，B股→b。
