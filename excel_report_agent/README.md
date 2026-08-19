# Excel → 产险经营分析报告生成 Agent

按《第七阶段_保险上市公司经营分析Agent_V2_计划书_Excel到PDF_MD.md》实现 V2：

- `excel_reader.py`：读取 `3-产险对标` Sheet，标准化为指标/公司/期间/数值/同比/备注；
- `analysis.py`：Analysis Engine，完成趋势、横向对标、结构、增长贡献、盈利质量、
  规模×盈利矩阵、指标联动、风险信号与阳光专项分析，并生成带证据链和置信度的 Insight；
- `narrative.py`：按计划书章节组织 Markdown 分析母版；
- `pdf_builder.py`：用 reportlab 生成正式 PDF（页眉页脚、页码、表格、图表结论）；
- `critic.py`：Quality Critic Agent，对数据、分析、逻辑、报告与 So What 进行独立审稿。

## 运行

```bash
cd /Users/mayuhang/Documents/UI_0813
/Users/mayuhang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m excel_report_agent.main \
  --input "2025年上市公司年报数据对标-产险V3.xlsx" \
  --output output/产险报告
```

默认输入路径为 `阳光学习资料/0806‘agent/2025年上市公司年报数据对标-产险V3.xlsx`，
默认输出到 `output/产险报告/`，最终只交付两个文件：

```text
2025年上市公司产险经营分析.md
2025年上市公司产险经营分析.pdf
```
