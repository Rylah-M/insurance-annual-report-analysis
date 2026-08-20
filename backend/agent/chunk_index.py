"""轻量 RAG 知识库：年报 chunks 入库 + BM25 检索。

数据来源：解析/指标提取流水线产出的 *_chunks.json（24 份年报、约 5 千个语义 chunk）。
策略：
- SQLite 持久化到 data/chunks.db（已在 .gitignore 中，不会上传 GitHub）；
- 检索时先按 company/year 元数据过滤，再做 BM25 打分；
- 中文分词无外部依赖：ASCII 词 + CJK 二元组（bigram）；
- 同一份报告若存在多个版本文件，只取 mtime 最新的一个；
- 磁盘上的 chunk 文件变化后，下次请求会自动重建索引（fingerprint 校验）。
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHUNK_DB_PATH = PROJECT_ROOT / "data" / "chunks.db"

CHUNK_SOURCE_GLOBS = (
    "output_chunks/*/*_chunks.json",
    "agents/zd-agent0811/chunk/*_chunks.json",
    "agents/Annual_Report_Analysis/parse_v1/output/*/*_chunks.json",
)

DEFAULT_TOP_K = 5
BM25_K1 = 1.5
BM25_B = 0.75

_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SECTION_LEAD_RE = re.compile(r"^[（(]?\s*[一二三四五六七八九十百\d]+\s*[）)、.]?")
_WHITESPACE_RE = re.compile(r"\s+")

QUARTER_ORDER = {"Q4": 0, "Q3": 1, "Q2": 2, "Q1": 3}
QUARTER_BONUS = {"Q4": 1.5, "Q3": 1.0, "Q2": 0.5, "Q1": 0.0}
SECTION_BONUS = 3.0

# 数据库使用两字短名（同事已归一化），chunk 文件仍保留全称，检索时互相兼容。
COMPANY_NAME_MAP = {
    "人保": "中国人保",
    "太保": "中国太保",
    "太平": "中国太平",
    "平安": "中国平安",
    "阳光": "中国阳光",
    "众安": "众安在线",
}

# 战略/总览类章节：回答“方针、原因、经营策略”类问题时优先召回。
STRATEGIC_SECTION_KEYWORDS = (
    "管理层讨论与分析",
    "董事长致辞",
    "公司业务概要",
    "财产保险业务",
    "人身保险业务",
    "主要业务",
    "经营计划",
    "经营情况讨论",
    "行业格局和趋势",
    "风险及应对",
    "经营策略",
    "发展展望",
    "未来展望",
    "战略",
    "工作成效",
    "机遇与挑战",
)

_INTENT_STRATEGY = ("方针", "战略", "策略", "主线", "思路", "布局", "规划", "愿景", "目标", "定位")
_INTENT_STRUCTURE = ("结构", "占比", "险种")
_INTENT_CAUSE = ("原因", "为什么", "基于", "驱动", "推动", "为何")


def _query_expansion(question: str) -> list[str]:
    """按问题意图补充检索词，缓解中文近义表达（方针/战略、原因/驱动）的漏召回。"""
    extra: list[str] = []
    if any(keyword in question for keyword in _INTENT_STRATEGY):
        extra += [
            "高质量发展", "五篇大文章", "战略", "经营", "转型",
            "布局", "规划", "目标", "坚持", "服务",
        ]
    if any(keyword in question for keyword in _INTENT_STRUCTURE):
        extra += ["车险", "非车险", "占比", "结构", "险种", "业务"]
    if any(keyword in question for keyword in _INTENT_CAUSE):
        extra += ["原因", "驱动", "推动", "优化", "调整", "改善", "变化"]
    return _tokenize(" ".join(extra))


def _section_bonus(section: str | None) -> float:
    text = section or ""
    return SECTION_BONUS if any(keyword in text for keyword in STRATEGIC_SECTION_KEYWORDS) else 0.0


def _company_matches(doc_company: str, query_company: str) -> bool:
    """chunk 公司名（全称）与查询公司名（短名/全称）双向兼容匹配。"""
    if doc_company == query_company:
        return True
    full = COMPANY_NAME_MAP.get(query_company)
    return bool(full) and doc_company == full


def _report_key(filename: str) -> str:
    """从文件名提取报告标识，如 中国人保_2025_Q4_A股。"""
    name = Path(filename).name
    if name.endswith("_chunks.json"):
        name = name[: -len("_chunks.json")]
    return name


def _iter_source_files() -> list[Path]:
    """按报告去重，每份报告只取 mtime 最新的 chunk 文件。"""
    best: dict[str, tuple[float, Path]] = {}
    for pattern in CHUNK_SOURCE_GLOBS:
        for path in PROJECT_ROOT.glob(pattern):
            key = _report_key(path.name)
            mtime = path.stat().st_mtime
            if key not in best or mtime > best[key][0]:
                best[key] = (mtime, path)
    return [item[1] for item in sorted(best.values())]


def _fingerprint() -> str:
    """基于来源文件路径 + mtime + size 的指纹，用于判断是否需要重建索引。"""
    digest = hashlib.md5()
    for path in _iter_source_files():
        stat = path.stat()
        digest.update(
            f"{path.relative_to(PROJECT_ROOT)}:{stat.st_mtime}:{stat.st_size}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _connect() -> sqlite3.Connection:
    CHUNK_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CHUNK_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chunk_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            year INTEGER NOT NULL,
            quarter TEXT NOT NULL,
            market TEXT NOT NULL,
            section TEXT,
            title TEXT,
            content TEXT NOT NULL,
            tables TEXT,
            position INTEGER,
            source_file TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_chunks_company_year
            ON chunks(company, year);
        """
    )
    conn.commit()


def _rebuild_from_files(conn: sqlite3.Connection, fingerprint: str) -> None:
    conn.execute("DELETE FROM chunks")
    rows: list[tuple[Any, ...]] = []
    for path in _iter_source_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for chunk in data:
            if not isinstance(chunk, dict):
                continue
            year = chunk.get("year")
            try:
                year = int(year) if year is not None else 0
            except (TypeError, ValueError):
                year = 0
            tables = chunk.get("tables")
            rows.append(
                (
                    chunk.get("chunk_id") or "",
                    chunk.get("company") or "",
                    year,
                    chunk.get("quarter") or "",
                    chunk.get("market") or "",
                    chunk.get("section"),
                    chunk.get("title"),
                    chunk.get("content") or "",
                    json.dumps(tables, ensure_ascii=False) if tables else None,
                    chunk.get("position"),
                    str(path),
                )
            )
    conn.executemany(
        """INSERT OR REPLACE INTO chunks
           (chunk_id, company, year, quarter, market, section, title,
            content, tables, position, source_file)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.execute(
        "INSERT OR REPLACE INTO chunk_meta (key, value) VALUES ('fingerprint', ?)",
        (fingerprint,),
    )
    conn.commit()


def ensure_chunk_index() -> str:
    """确保 SQLite 索引与磁盘 chunk 文件一致，返回当前指纹。"""
    fingerprint = _fingerprint()
    conn = _connect()
    _init_schema(conn)
    row = conn.execute(
        "SELECT value FROM chunk_meta WHERE key = 'fingerprint'"
    ).fetchone()
    if row is not None and row["value"] == fingerprint:
        count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        if count > 0:
            conn.close()
            return fingerprint
    _rebuild_from_files(conn, fingerprint)
    conn.close()
    return fingerprint


@lru_cache(maxsize=2)
def _load_chunks_cached(fingerprint: str) -> list[dict[str, Any]]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM chunks ORDER BY company, year, quarter, position"
    ).fetchall()
    conn.close()
    docs: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        tables = item.get("tables")
        if tables:
            try:
                item["tables"] = json.loads(tables)
            except Exception:
                item["tables"] = None
        docs.append(item)
    return docs


def load_all_chunks() -> list[dict[str, Any]]:
    fingerprint = ensure_chunk_index()
    return _load_chunks_cached(fingerprint)


def _tokenize(text: str) -> list[str]:
    """轻量中文分词：ASCII 单词 + CJK 字符二元组，零外部依赖。"""
    tokens = [match.group(0).lower() for match in _ASCII_TOKEN_RE.finditer(text)]
    chinese = "".join(_CJK_CHAR_RE.findall(text))
    if len(chinese) >= 2:
        tokens.extend(chinese[index : index + 2] for index in range(len(chinese) - 1))
    return tokens


def _chunk_text(chunk: dict[str, Any]) -> str:
    """检索用文本：正文 + 表格纯文本。"""
    parts = [chunk.get("content") or ""]
    tables = chunk.get("tables")
    if tables:
        for table in tables:
            if isinstance(table, dict) and table.get("content"):
                plain = _HTML_TAG_RE.sub(" ", str(table["content"]))
                parts.append(_WHITESPACE_RE.sub(" ", plain))
    return "\n".join(parts)


def _section_key(section: str | None) -> str:
    """归一化章节名，去掉序号与标点，用于跨报告期去重。"""
    text = _SECTION_LEAD_RE.sub("", (section or "").strip())
    return _WHITESPACE_RE.sub(
        "", re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)
    )


def _bm25_scores(
    query_tokens: list[str], docs: list[dict[str, Any]]
) -> list[float]:
    token_lists = [_tokenize(_chunk_text(doc)) for doc in docs]
    total = len(token_lists)
    if total == 0 or not query_tokens:
        return [0.0] * total
    doc_freq: Counter[str, int] = Counter()
    for tokens in token_lists:
        doc_freq.update(set(tokens))
    avgdl = sum(len(tokens) for tokens in token_lists) / total
    query_set = set(query_tokens)
    scores: list[float] = []
    for tokens in token_lists:
        term_freq = Counter(tokens)
        doc_len = len(tokens)
        score = 0.0
        for term in query_set:
            freq = term_freq.get(term)
            if not freq:
                continue
            df = doc_freq.get(term, 0)
            idf = math.log(1 + (total - df + 0.5) / (df + 0.5))
            score += (
                idf
                * freq
                * (BM25_K1 + 1)
                / (freq + BM25_K1 * (1 - BM25_B + BM25_B * doc_len / avgdl))
            )
        scores.append(score)
    return scores


def _make_excerpt(content: str, query_tokens: list[str], max_len: int = 420) -> str:
    """围绕首个命中词取上下文窗口，找不到命中则取正文开头。"""
    text = _WHITESPACE_RE.sub(" ", content.replace("#", " ")).strip()
    terms = sorted(
        {term for term in query_tokens if len(term) >= 2}, key=len, reverse=True
    )
    best_pos = -1
    for term in terms:
        pos = text.find(term)
        if pos >= 0 and (best_pos < 0 or pos < best_pos):
            best_pos = pos
    if best_pos < 0:
        return text[:max_len] + ("…" if len(text) > max_len else "")
    start = max(0, best_pos - 140)
    end = min(len(text), best_pos + 280)
    excerpt = text[start:end]
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(text):
        excerpt += "…"
    return excerpt


def retrieve_chunks(
    question: str,
    company: str | None = None,
    year: int | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """按公司/年份过滤后，用 BM25 检索最相关的年报 chunk。"""
    docs = load_all_chunks()
    if not docs:
        return []
    pool = docs
    if company:
        pool = [doc for doc in pool if _company_matches(doc["company"], company)]
    if year:
        year_pool = [doc for doc in pool if doc["year"] == year]
        if year_pool:
            pool = year_pool
    if not pool:
        return []

    query_tokens = _tokenize(question) + _query_expansion(question)
    if not query_tokens:
        return []
    scores = _bm25_scores(query_tokens, pool)
    adjusted = [
        score
        + _section_bonus(doc.get("section"))
        + QUARTER_BONUS.get(doc.get("quarter") or "", 0.0)
        for doc, score in zip(pool, scores)
    ]
    ranked = list(zip(pool, adjusted))
    ranked.sort(
        key=lambda item: (
            -item[1],
            -(item[0].get("year") or 0),
            QUARTER_ORDER.get(item[0].get("quarter") or "", 9),
            item[0].get("position") or 0,
        )
    )

    seen_sections: set[tuple[str, int, str]] = set()
    results: list[dict[str, Any]] = []
    for doc, score in ranked:
        section = _section_key(doc.get("section"))
        key = (doc.get("company") or "", int(doc.get("year") or 0), section)
        if key in seen_sections:
            continue
        seen_sections.add(key)
        item = dict(doc)
        item["score"] = round(float(score), 4)
        item["excerpt"] = _make_excerpt(
            doc.get("content") or "", _tokenize(question)
        )
        results.append(item)
        if len(results) >= top_k:
            break
    return results


def rebuild() -> dict[str, Any]:
    """强制重建索引并返回统计信息。"""
    fingerprint = ensure_chunk_index()
    docs = _load_chunks_cached(fingerprint)
    return {
        "fingerprint": fingerprint,
        "reports": len(_iter_source_files()),
        "chunks": len(docs),
    }


if __name__ == "__main__":
    info = rebuild()
    print(
        f"chunks index ready: {info['reports']} reports, "
        f"{info['chunks']} chunks -> {CHUNK_DB_PATH}"
    )
