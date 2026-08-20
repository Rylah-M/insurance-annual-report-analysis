# 智能问答 Agent（qa-agent0820）

与 `agents/zd-agent0811`（解析 + 指标提取）平级的问答 Agent。

## 组成

```text
agents/qa-agent0820/code/
├── chat_agent.py          # 问答主逻辑:意图识别、DB+知识库混合上下文、LLM 生成
├── chunk_index.py         # 年报原文知识库:SQLite 入库 + 公司/年份过滤 + BM25 检索
├── consolidate_chunks.py  # 统一重切脚本:把过碎的 chunks 合并为语义块
└── README.md
```

## 与网页的关系

- 网页后端实际加载的是 `backend/agent/chat_agent.py` 和 `backend/agent/chunk_index.py`，
  它们是**薄壳**，真实代码在本目录（避免双份拷贝失同步）；
- 数据流：问题 → 结构化指标库（DB）+ 年报原文知识库（chunks）→ LLM（deepseek）→ 回答。

## 知识库说明（重要）

- **chunks / md 不入库 GitHub**（.gitignore），只存在于本地；
- 新机器 `git pull` 后需要本地生成知识库：
  1. 解析产物 md 由解析 agent 生成（本地）；
  2. 运行 `python agents/qa-agent0820/code/consolidate_chunks.py` 统一重切
     （输出 `output_chunks_v2/`，平安等超长年报从 899 碎片合并到 100+ 语义块）；
  3. 首次问答会自动重建 `data/chunks.db` 索引。
- 众安 H 股年报为繁体中文，BM25 检索分偏低（未做简繁转换），回答依赖模型读繁体。

## 已知配置

- 公司名采用短名（人保/太保/太平/平安/阳光/众安），chunk 全称自动兼容；
- 报告素材优先取 Q4 全年报；
- LLM 配置在网页「模型设置」，Key 绑定本机。
