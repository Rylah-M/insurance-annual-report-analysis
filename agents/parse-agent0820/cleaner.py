"""cleaner.py：Markdown 清洗。

职责：删除 Markdown 中的图片引用（不删除图片附近的文本），
保留标题、正文与表格，供 splitter 切分使用。
"""
from __future__ import annotations

import re

IMAGE_REF_LINE_RE = re.compile(r"^!\[[^\]]*\]\([^)]*\)\s*$", re.MULTILINE)
HTML_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def clean_markdown(text: str) -> str:
    """删除独立的图片引用行（markdown 语法与 <img> 标签），保留其他内容。"""
    text = IMAGE_REF_LINE_RE.sub("", text)
    text = HTML_IMG_RE.sub("", text)
    # 合并连续空行，保持整洁
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"
