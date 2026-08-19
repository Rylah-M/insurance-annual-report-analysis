"""splitter.py：把 MinerU 生成的年报 Markdown 切分为面向指标提取的 semantic chunks。

切分规则：
1. 基于 Markdown 标题层级（# / ## / ###），不做按句切分；
2. 默认粒度：一级标题(section) + 二级标题(title)，每个 chunk 包含该二级标题下的
   完整正文与全部表格；
3. 年报常见的编号标题（一、/（一）/1、/（1））会被识别为更低层级，
   嵌套在真实章节之下，避免把编号条目拆成碎片 chunk；
4. 纯数字标题（页码噪声）并入父级，不单独成 chunk；
5. 表格绑定最近的章节 chunk，禁止表格单独成为 chunk；
6. 仅当 chunk 超过 max_tokens（默认 12000）时，先按三级标题切分，
   再按段落（空行）切分，切分后保留 parent section / title。

company / year / market 由调用方传入，不硬编码公司名称。
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from cleaner import clean_markdown

PROJECT_ROOT = Path(__file__).resolve().parent
COMPANIES_FILE = PROJECT_ROOT / "config" / "companies.json"

DEFAULT_MAX_TOKENS = 12000

MARKET_CODES = {"A股": "a", "H股": "h", "港股": "h", "B股": "b"}

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
HTML_TABLE_RE = re.compile(r"<table[\s\S]*?</table>", re.IGNORECASE)
PIPE_TABLE_RE = re.compile(r"(?m)^[ \t]*\|[^\n]*(?:\n[ \t]*\|[^\n]*)*")
TABLE_PLACEHOLDER_RE = re.compile(r"\x00TABLE_(\d+)\x00")

# 年报编号前缀 → 隐含层级（MinerU 常把它们压平成 ##）
ENUM_PATTERNS = (
    (3, re.compile(r"^[一二三四五六七八九十百]+、")),   # 一、
    (4, re.compile(r"^（[一二三四五六七八九十百]+）")),  # （一）
    (5, re.compile(r"^\d{1,3}、")),                     # 1、
    (6, re.compile(r"^（\d{1,3}）")),                    # （1）
    (6, re.compile(r"^\(\d{1,3}\)")),                    # (1)（半角）
)
PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")  # 疑似页码的纯数字标题
CONTINUATION_SUFFIXES = ("(续)", "（续）", "( 续 )", "（ 续 ）")


# ---------- 内部数据结构 ----------


@dataclass
class _Section:
    level: int          # 有效层级（经过编号前缀调整）
    md_level: int       # 原始 Markdown 层级（# 数量）
    title: str
    lines: list[str] = field(default_factory=list)
    children: list["_Section"] = field(default_factory=list)


@dataclass
class _Unit:
    """一个待输出 chunk 的最小单元（可能被进一步切分）。"""

    level: int
    section: str
    title: str
    body: str


# ---------- 工具函数 ----------


def load_company_code(company: str) -> str:
    """从 config/companies.json 读取公司英文代码（用于 chunk_id），未配置时回退为公司名。"""
    try:
        config = json.loads(COMPANIES_FILE.read_text(encoding="utf-8"))
        codes = config.get("company_codes", {})
        if company in codes:
            return str(codes[company])
    except Exception:
        pass
    return company


def build_chunk_id(
    company: str,
    year: str | int,
    market: str,
    position: int,
    quarter: str | None = None,
) -> str:
    """生成 chunk_id，例如 pingan_2012_q3_a_001。"""
    code = load_company_code(company)
    quarter_part = f"{quarter.lower()}_" if quarter else ""
    market_part = ""
    if market:
        market_code = MARKET_CODES.get(market, market[:1].lower())
        market_part = f"{market_code}_"
    return f"{code}_{year}_{quarter_part}{market_part}{position:03d}"


def estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文约 1 token/1.5 字符，英文约 1 token/4 字符。"""
    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = max(0, len(text) - cjk)
    return max(1, math.ceil(cjk / 1.5 + other / 4))


def _effective_level(md_level: int, title: str) -> tuple[int, bool]:
    """计算标题的有效层级；返回 (层级, 是否噪声标题)。"""
    title = title.strip()
    if md_level == 2 and PAGE_NUMBER_RE.match(title):
        return 0, True
    level = md_level
    for enum_level, pattern in ENUM_PATTERNS:
        if pattern.match(title):
            level = max(level, enum_level)
            break
    return level, False


def _strip_continuation(title: str) -> str:
    """去掉标题末尾的“(续)”标记，用于合并跨页续段。"""
    for suffix in CONTINUATION_SUFFIXES:
        if title.endswith(suffix):
            base = title[: -len(suffix)].strip()
            return base or title
    return title


# ---------- Markdown 解析 ----------


def _parse_sections(lines: Iterable[str]) -> list[_Section]:
    """把 Markdown 行解析成标题树（含前言区），并按有效层级组织。"""
    roots: list[_Section] = []
    stack: list[_Section] = []
    preamble: list[str] = []

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        match = HEADING_RE.match(line)
        if match:
            md_level = len(match.group(1))
            title = match.group(2).strip()
            eff_level, is_noise = _effective_level(md_level, title)
            if is_noise:
                # 页码噪声：标题行降级为正文，内容并入父级
                if stack:
                    stack[-1].lines.append(line)
                else:
                    preamble.append(line)
                continue
            section = _Section(level=eff_level, md_level=md_level, title=title)
            while stack and stack[-1].level >= eff_level:
                stack.pop()
            if stack:
                stack[-1].children.append(section)
            else:
                roots.append(section)
            stack.append(section)
        else:
            if stack:
                stack[-1].lines.append(line)
            else:
                preamble.append(line)

    if any(p.strip() for p in preamble):
        roots.insert(0, _Section(level=0, md_level=0, title="前言", lines=preamble))
    return roots


def _serialize(sec: _Section, include_heading: bool) -> str:
    """把章节及全部子章节序列化为 Markdown 文本（保留原始标题标记）。"""
    parts: list[str] = []
    if include_heading and sec.md_level > 0:
        parts.append("#" * sec.md_level + " " + sec.title)
    parts.extend(sec.lines)
    for child in sec.children:
        parts.append(_serialize(child, include_heading=True))
    return "\n".join(parts)


def _serialize_excluding(sec: _Section, excluded_level: int) -> str:
    """序列化章节自身内容，排除指定层级的子章节（用于一级标题自身正文）。"""
    parts: list[str] = []
    if sec.md_level > 0:
        parts.append("#" * sec.md_level + " " + sec.title)
    parts.extend(sec.lines)
    for child in sec.children:
        if child.level != excluded_level:
            parts.append(_serialize(child, include_heading=True))
    return "\n".join(parts)


def _collect_units(roots: list[_Section]) -> list[_Unit]:
    """按“一级标题 → 二级标题”的粒度生成切分单元（更深的标题归属上级）。"""
    units: list[_Unit] = []
    for sec in roots:
        if sec.level == 0:
            body = "\n".join(sec.lines).strip()
            if body:
                units.append(_Unit(level=0, section="前言", title="前言", body=body))
            continue

        if sec.level == 1:
            level2_children = [c for c in sec.children if c.level == 2]
            if level2_children:
                # 一级标题自身的导语/正文（含更深层编号内容）保留为独立单元
                own_body = _serialize_excluding(sec, excluded_level=2).strip()
                has_own_content = any(
                    line.strip() for line in sec.lines
                ) or any(c.level > 2 for c in sec.children)
                if own_body and has_own_content:
                    units.append(
                        _Unit(level=1, section=sec.title, title=sec.title, body=own_body)
                    )
                for child in level2_children:
                    body = _serialize(child, include_heading=True).strip()
                    if body:
                        units.append(
                            _Unit(level=2, section=sec.title, title=child.title, body=body)
                        )
            else:
                body = _serialize(sec, include_heading=True).strip()
                if body:
                    units.append(
                        _Unit(level=1, section=sec.title, title=sec.title, body=body)
                    )
        else:
            body = _serialize(sec, include_heading=True).strip()
            if body:
                units.append(
                    _Unit(level=sec.level, section=sec.title, title=sec.title, body=body)
                )
    return units


def _atomic_lines(text: str) -> list[str]:
    """把文本拆成原子行：HTML 表格与连续管道表格合并为整体，避免被拆开。"""
    lines = text.splitlines()
    atoms: list[str] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if "<table" in line.lower():
            buf = [line]
            i += 1
            while i < n and "</table>" not in lines[i].lower():
                buf.append(lines[i])
                i += 1
            if i < n:
                buf.append(lines[i])
                i += 1
            atoms.append("\n".join(buf))
        elif line.lstrip().startswith("|"):
            buf = [line]
            i += 1
            while i < n and lines[i].lstrip().startswith("|"):
                buf.append(lines[i])
                i += 1
            atoms.append("\n".join(buf))
        else:
            atoms.append(line)
            i += 1
    return atoms


def _split_by_level3(unit: _Unit) -> list[_Unit]:
    """按有效层级为 3 的标题（### 或 一、）切分超长单元。"""
    segments: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in unit.body.splitlines():
        match = HEADING_RE.match(line)
        if match:
            eff_level, _ = _effective_level(len(match.group(1)), match.group(2).strip())
            if eff_level == 3:
                segments.append((current_title, current_lines))
                current_title = match.group(2).strip()
                current_lines = [line]
                continue
        current_lines.append(line)
    segments.append((current_title, current_lines))

    result: list[_Unit] = []
    for title, lines in segments:
        body = "\n".join(lines).strip()
        if not body:
            continue
        if title:
            result.append(_Unit(level=3, section=unit.section, title=title, body=body))
        else:
            result.append(
                _Unit(level=unit.level, section=unit.section, title=unit.title, body=body)
            )
    return result


def _is_table_only(text: str) -> bool:
    """判断一段文本是否只包含表格（无正文/标题）。"""
    stripped = HTML_TABLE_RE.sub("", text)
    stripped = PIPE_TABLE_RE.sub("", stripped)
    return not stripped.strip()


def _split_by_paragraphs(unit: _Unit, max_tokens: int) -> list[_Unit]:
    """仅用于超长 chunk：按段落（空行分隔）切分，表格保持原子、绝不单独成 chunk。"""
    atoms = _atomic_lines(unit.body)
    paragraphs: list[list[str]] = []
    current: list[str] = []
    for atom in atoms:
        if atom.strip() == "":
            if current:
                paragraphs.append(current)
                current = []
        else:
            current.append(atom)
    if current:
        paragraphs.append(current)

    # 只有标题的段落并入下一段，避免出现“只有标题”的空 chunk
    merged_paragraphs: list[list[str]] = []
    i = 0
    while i < len(paragraphs):
        para = paragraphs[i]
        if len(para) == 1 and HEADING_RE.match(para[0]) and i + 1 < len(paragraphs):
            merged_paragraphs.append([para[0], "", *paragraphs[i + 1]])
            i += 2
        else:
            merged_paragraphs.append(para)
            i += 1
    paragraphs = merged_paragraphs

    pieces: list[list[str]] = []
    batch: list[str] = []
    batch_tokens = 0
    for para_atoms in paragraphs:
        para_text = "\n".join(para_atoms)
        para_tokens = estimate_tokens(para_text)
        if para_tokens > max_tokens:
            if batch:
                pieces.append(batch)
                batch, batch_tokens = [], 0
            # 段落仍然超长：按原子行分批（表格始终整体保留）
            inner: list[str] = []
            inner_tokens = 0
            for atom in para_atoms:
                atom_tokens = estimate_tokens(atom)
                if inner and inner_tokens + atom_tokens > max_tokens:
                    pieces.append(inner)
                    inner, inner_tokens = [], 0
                inner.append(atom)
                inner_tokens += atom_tokens
            if inner:
                pieces.append(inner)
        elif batch and batch_tokens + para_tokens > max_tokens:
            pieces.append(batch)
            batch, batch_tokens = [para_text], para_tokens
        else:
            if batch:
                batch.append("")
            batch.append(para_text)
            batch_tokens += para_tokens
    if batch:
        pieces.append(batch)

    # 纯表格片段并入前一片段，禁止表格单独成 chunk
    final_pieces: list[list[str]] = []
    for piece in pieces:
        text = "\n".join(piece)
        if _is_table_only(text):
            if final_pieces:
                final_pieces[-1].extend(["", *piece])
            else:
                final_pieces.append(piece)
        else:
            final_pieces.append(piece)
    pieces = final_pieces

    heading_line = f"{'#' * unit.level} {unit.title}" if unit.level > 0 else ""
    result: list[_Unit] = []
    for piece_atoms in pieces:
        body = "\n".join(piece_atoms).strip()
        if not body:
            continue
        if heading_line and not body.startswith(heading_line):
            body = f"{heading_line}\n\n{body}"
        result.append(
            _Unit(level=unit.level, section=unit.section, title=unit.title, body=body)
        )
    return result


def _split_unit(unit: _Unit, max_tokens: int) -> list[_Unit]:
    """超长单元的递归切分：三级标题 → 段落（不按句切分）。"""
    if estimate_tokens(unit.body) <= max_tokens:
        return [unit]
    level3_units = _split_by_level3(unit)
    if len(level3_units) > 1 or (
        len(level3_units) == 1 and level3_units[0].title != unit.title
    ):
        result: list[_Unit] = []
        for sub in level3_units:
            result.extend(_split_unit(sub, max_tokens))
        return result
    return _split_by_paragraphs(unit, max_tokens)


# ---------- 表格提取 ----------


def extract_tables(text: str) -> tuple[str, list[str]]:
    """把 Markdown 文本中的表格提取出来（HTML <table> 与管道表格），返回剩余文本与表格列表。"""
    tables: list[str] = []

    def _replace_html(match: re.Match) -> str:
        index = len(tables)
        tables.append(match.group(0))
        return f"\x00TABLE_{index}\x00"

    text = HTML_TABLE_RE.sub(_replace_html, text)

    def _replace_pipe(match: re.Match) -> str:
        block = match.group(0)
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if len(lines) >= 2:
            index = len(tables)
            tables.append("\n".join(lines))
            return f"\x00TABLE_{index}\x00"
        return block

    text = PIPE_TABLE_RE.sub(_replace_pipe, text)

    ordered_tables: list[str] = []
    for match in TABLE_PLACEHOLDER_RE.finditer(text):
        ordered_tables.append(tables[int(match.group(1))])
    text = TABLE_PLACEHOLDER_RE.sub("", text)
    return text, ordered_tables


# ---------- 对外入口 ----------


def split_markdown(
    markdown: str | Path,
    company: str,
    year: str | int,
    market: str,
    *,
    quarter: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict]:
    """把 Markdown 切分为结构化 chunk 列表。"""
    if isinstance(markdown, Path):
        text = markdown.read_text(encoding="utf-8")
    else:
        text = markdown

    text = clean_markdown(text)
    roots = _parse_sections(text.splitlines())
    units = _collect_units(roots)

    chunks: list[dict] = []
    position = 0
    table_counter = 0
    for unit in units:
        for piece in _split_unit(unit, max_tokens):
            content, tables = extract_tables(piece.body)
            content = content.strip()
            if not content and not tables:
                continue
            chunk_tables = []
            for table in tables:
                table_counter += 1
                chunk_tables.append(
                    {"table_id": f"table_{table_counter:03d}", "content": table}
                )
            if not content and tables:
                # 防御：纯表格片段并入上一个 chunk，禁止表格单独成 chunk
                if chunks:
                    chunks[-1]["tables"].extend(chunk_tables)
                    continue
                content = piece.title
            # 跨页续段（如“11. 其他资产(续)”）并入原章节 chunk
            base_title = _strip_continuation(piece.title)
            if (
                base_title != piece.title
                and chunks
                and chunks[-1]["section"] == piece.section
                and chunks[-1]["title"] == base_title
            ):
                chunks[-1]["content"] += "\n\n" + content
                chunks[-1]["tables"].extend(chunk_tables)
                continue
            position += 1
            chunks.append(
                {
                    "chunk_id": build_chunk_id(company, year, market, position, quarter),
                    "company": company,
                    "year": int(year) if str(year).isdigit() else year,
                    "quarter": quarter,
                    "market": market,
                    "section": piece.section,
                    "title": piece.title,
                    "content": content,
                    "tables": chunk_tables,
                    "position": position,
                }
            )
    return chunks
