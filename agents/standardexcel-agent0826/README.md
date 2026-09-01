# standardexcel-agent（第十阶段）

本 Agent 基于 `database_result.csv`、`indicator_metadata.xlsx`、
`indicator_dictionary.xlsx` 自动生成上市财险公司全期间横向对标分析底稿
`standardexcel.xlsx`，实现：

```text
数据库数据 -> 指标筛选 -> 口径过滤 -> 指标匹配 -> Excel自动生成
```

## 目录结构

```text
agents/standardexcel-agent0826
├── main.py                 # 执行入口
├── config.py               # 路径、期间、公司顺序、口径与格式配置
├── data_loader.py          # 读取三个输入文件
├── indicator_filter.py     # 口径过滤、指标匹配、按指标/公司/报告期去重
├── excel_generator.py      # 生成对比Sheet与汇总Sheet并设置格式
├── indicator_metadata.xlsx # 指标筛选与分类规则
└── output/
    └── standardexcel.xlsx  # 生成结果
```

## 输入文件

| 文件 | 作用 |
| --- | --- |
| `database/database_result.csv` | AI 提取的指标数据库，不改动原始文件 |
| `agents/standardexcel-agent0826/indicator_metadata.xlsx` | 指标筛选、分类、单位、展示规则中心 |
| `agents/zd-agent0811/indicator/indicator_dictionary.xlsx` | 指标定义、关键词、计算规则 |

## 运行方式

```bash
cd agents/standardexcel-agent0826
python main.py
```

可选参数：

```bash
python main.py --output /path/to/standardexcel.xlsx
```

## 输出Sheet

| Sheet | 内容 |
| --- | --- |
| 首页说明 | 项目名称、数据来源、数据范围、口径说明 |
| 盈利能力对比 | `indicator_category = 盈利能力指标` |
| 业务规模对比 | `indicator_category = 业务规模指标` |
| 经营效率对比 | `indicator_category = 经营效率指标` |
| 偿付能力对比 | `indicator_category = 风险管理指标` |
| 汇总 | 四个对比Sheet按分析角度纵向合并 |

## Sheet结构

每个对比Sheet：

- 第一行：`2022Q2、2022Q4、2023Q2、2023Q4、2024Q2、2024Q4、2025Q2、2025Q4、2026Q2、2026Q4`。
- A列：公司名称，顺序为 人保、太保、平安、大地、太平、众安（产险业务）、阳光，阳光固定最后。
- B列：按指标块合并单元格，显示指标名称（含单位）。
- 每个指标块最后一行：`所有上市公司合计`，金额类指标求和、百分比类指标取均值。
- 缺失值显示为 `-`。

汇总Sheet：A列为分析角度（盈利能力、业务规模、经营效率、偿付能力），
四个对比表纵向合并放置在A列右侧。

## 处理逻辑

1. 读取三个输入文件。
2. 按 `indicator_id` 匹配数据库指标；如果数据库中不存在该 ID，则回退按
   `indicator_name` 匹配。
3. 仅保留 `business_scope_type in {财险口径, 特殊财险口径}`，删除集团口径。
4. 同一公司、同一指标、同一报告期若存在多个口径，优先 `财险口径`，再按提取
   置信度排序。
5. 以公司为行、报告期为列生成横向对比表，并为每个指标块输出合计行。

金额使用 `#,##0.00` 千分位格式，百分比使用 `97.6%` 显示格式；数据列宽度固定
为 18，保证打开后数字完整显示。

## 验收对照

- `standardexcel.xlsx` 存在。
- 不包含集团口径指标。
- 指标均来自 `database_result.csv`。
- 指标分类来自 `indicator_metadata.xlsx`。
- 指标定义来自 `indicator_dictionary.xlsx`。
- 覆盖 2022-2026 年各年 Q2/Q4，以及全部列示公司，支持多公司多期间横向比较。

## 后续扩展

`main.py` 已支持 `--output` 参数，后续 Web 页面可调用该模块生成 Excel 下载文件。
