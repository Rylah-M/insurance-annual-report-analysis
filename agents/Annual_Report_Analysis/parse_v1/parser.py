"""parse_v1 核心：通过 MinerU 本地 API 解析年报 PDF，并按数据库命名规范归档。

调用方式（重要）：
    MinerU 不作为 Python 库直接调用，而是先启动本地 FastAPI 服务：

        conda activate annual_report
        mineru-api            # 默认 http://127.0.0.1:8000，保持窗口不关闭

    然后本模块通过 HTTP POST /file_parse 完成解析，固定使用 pipeline 后端，
    避免触发 VLM / hybrid 模型下载。

输出命名规范（与数据库标准一致）：
    <公司>_<年份>_<报告时间>_<市场>/<公司>_<年份>_<报告时间>_<市场>.md
        + _chunks.json + _metadata.json

例如：中国平安_2012_Q3_A股/
    中国平安_2012_Q3_A股.md              MinerU 原始 Markdown
    中国平安_2012_Q3_A股_chunks.json     按标题层级切分后的结构化文本块
    中国平安_2012_Q3_A股_metadata.json   文件基本信息
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from output_manager import write_metadata
from splitter import split_markdown

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
COMPANIES_FILE = CONFIG_DIR / "companies.json"
DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
TMP_DIR = DATA_DIR / "tmp"
OUTPUT_DIR = PROJECT_ROOT / "output"

NAME_SEPARATOR = "_"
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"

logger = logging.getLogger("parse_v1")


# ---------- 配置 ----------


def load_companies_config() -> dict:
    """读取公司/年份/市场数据源，命名须与数据库标准保持一致。"""
    if not COMPANIES_FILE.exists():
        return {"companies": [], "years": [], "markets": ["A股", "H股"]}
    with open(COMPANIES_FILE, encoding="utf-8") as f:
        return json.load(f)


def build_output_name(
    company: str,
    year: str | int,
    market: str,
    quarter: str | None = None,
) -> str:
    """按数据库命名规范生成输出名：<公司>_<年份>_<报告时间>_<市场>。"""
    parts = [str(company), str(year)]
    if quarter:
        parts.append(quarter)
    if market:
        parts.append(str(market))
    return NAME_SEPARATOR.join(parts)


def validate_selection(
    company: str,
    year: str | int,
    market: str,
    quarter: str | None = None,
) -> None:
    """校验年份/报告时间/市场（公司支持手动输入，只校验非空）。"""
    if not company or not str(company).strip():
        raise ValueError("公司名称不能为空")
    config = load_companies_config()
    if str(year) not in config.get("years", []):
        raise ValueError(
            f"年份“{year}”不在配置列表中，请先在 config/companies.json 添加"
        )
    if market and market not in config.get("markets", ["A股", "H股"]):
        raise ValueError(f"市场“{market}”不在配置列表中（可选：A股 / H股；未上市可不选）")
    if quarter is not None and quarter not in config.get("quarters", ["Q1", "Q2", "Q3", "Q4"]):
        raise ValueError(f"报告时间“{quarter}”不在配置列表中（可选：Q1 / Q2 / Q3 / Q4）")


def get_api_base_url() -> str:
    return os.environ.get("MINERU_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


class PageRangeAmbiguousError(ValueError):
    """页码标签存在重复（如附录重新从 1 编号），无法唯一映射。"""


def _build_page_label_map(pdf_path: Path) -> tuple[dict[str, list[int]], int]:
    """读取 PDF 页码标签，返回 {标签: [物理页索引,...]} 与总页数。"""
    labels: dict[str, list[int]] = {}
    total = 0
    try:
        import pypdfium2 as pdfium

        doc = pdfium.PdfDocument(str(pdf_path))
        total = len(doc)
        for index in range(total):
            try:
                label = doc.get_page_label(index)
            except Exception:
                label = ""
            if label and label.strip():
                labels.setdefault(label.strip(), []).append(index)
        doc.close()
    except Exception:
        labels = {}
    return labels, total


def get_pdf_page_info(pdf_path: Path) -> dict:
    """返回 PDF 页码信息（总页数、标签映射、重复标签），供界面展示对照表。"""
    labels, total = _build_page_label_map(pdf_path)
    duplicates = {
        label: [index + 1 for index in indices]
        for label, indices in labels.items()
        if len(indices) > 1
    }
    return {
        "total_pages": total,
        "label_map": labels,
        "duplicates": duplicates,
    }


def resolve_page_range(
    start_page: int,
    end_page: int | None,
    *,
    pdf_path: Path | None = None,
    labels: dict[str, list[int]] | None = None,
    total: int | None = None,
    page_mode: str = "label",
) -> tuple[int, int | None, list[str]]:
    """把用户输入的页码解析为 MinerU 物理页索引（0 起），返回 (起始索引, 结束索引, 提示)。

    page_mode:
      "label"    按 PDF 页码标签（阅读器显示的页码）映射；无标签回退物理页；
                标签重复（如附录重新编号）时抛出 PageRangeAmbiguousError。
      "physical" 直接按物理页码（1 起）换算，永远唯一。
    """
    if page_mode == "physical":
        start_id = max(0, int(start_page) - 1)
        end_id = max(0, int(end_page) - 1) if end_page is not None else None
        return start_id, end_id, []

    if labels is None or total is None:
        if pdf_path is None:
            raise ValueError("page_mode=label 时需要提供 pdf_path")
        labels, total = _build_page_label_map(pdf_path)

    warnings: list[str] = []

    def resolve(display_page: int) -> int:
        key = str(display_page).strip()
        if key in labels:
            matches = labels[key]
            if len(matches) == 1:
                return matches[0]
            physical = [index + 1 for index in matches]
            raise PageRangeAmbiguousError(
                f"页码 {display_page} 在 PDF 中出现多次（对应物理页 {physical}），"
                "通常是附录重新从 1 编号导致，无法自动判断您指的是哪一段。\n"
                "请改用“按物理页码”输入（界面勾选该模式 / 命令行加 --page-mode physical），"
                "或参照界面上的“页码对照”表换算。"
            )
        warnings.append(
            f"PDF 中没有找到页码 {display_page} 的标签，已按物理第 {display_page} 页处理。"
        )
        return max(0, int(display_page) - 1)

    start_id = resolve(start_page)
    end_id = resolve(end_page) if end_page is not None else None
    return start_id, end_id, warnings


# ---------- MinerU API ----------


@dataclass
class ParseResult:
    output_name: str
    final_dir: Path
    markdown_path: Path
    chunks_path: Path
    metadata_path: Path
    total_chunks: int
    pdf_path: Path
    duration_seconds: float


def check_service_health(base_url: str | None = None) -> dict:
    """检查 MinerU 服务是否可用，不可用时给出启动指引。"""
    base_url = base_url or get_api_base_url()
    try:
        resp = requests.get(f"{base_url}/health", timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"无法连接 MinerU 服务（{base_url}）：{exc}\n"
            "请先单独打开一个终端启动服务：\n"
            "    conda activate annual_report\n"
            "    mineru-api\n"
            "并确认 curl http://127.0.0.1:8000/health 返回 healthy。"
        ) from exc
    payload = resp.json()
    if payload.get("status") != "healthy":
        raise RuntimeError(f"MinerU 服务状态异常：{json.dumps(payload, ensure_ascii=False)}")
    return payload


def _find_markdown_in_dir(root: Path, pdf_stem: str) -> Path | None:
    """在 MinerU 结果目录中定位 Markdown 文件。"""
    candidates = list(root.rglob("*.md"))
    for candidate in candidates:
        if candidate.stem == pdf_stem:
            return candidate
    return candidates[0] if candidates else None


def _extract_zip_response(
    resp: requests.Response,
    pdf_stem: str,
) -> tuple[str, Path | None]:
    """把 /file_parse 返回的 zip 解压，返回 (原始 Markdown 文本, 图片目录或 None)。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = TMP_DIR / f"{pdf_stem}_result.zip"
    unpack_dir = TMP_DIR / f"{pdf_stem}_unpack"
    zip_path.write_bytes(resp.content)
    if unpack_dir.exists():
        shutil.rmtree(unpack_dir)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(unpack_dir)

    raw_md = _find_markdown_in_dir(unpack_dir, pdf_stem)
    if raw_md is None:
        shutil.rmtree(unpack_dir, ignore_errors=True)
        raise RuntimeError("解析完成，但结果中没有找到 Markdown 文件")

    md_text = raw_md.read_text(encoding="utf-8")
    images_dir = raw_md.parent / "images"
    if not images_dir.exists():
        images_dir = None

    shutil.rmtree(unpack_dir, ignore_errors=True)
    zip_path.unlink(missing_ok=True)
    return md_text, images_dir


def _finalize_output(
    md_text: str,
    company: str,
    year: str | int,
    market: str,
    quarter: str | None,
    source_file: str,
    final_dir: Path,
    keep_images: bool,
    images_dir: Path | None,
    emit,
) -> tuple[Path, Path, Path, int]:
    """MinerU 解析完成后调用：写原始 md、切分生成 chunks.json、写 metadata.json。"""
    final_dir.mkdir(parents=True, exist_ok=True)
    output_name = build_output_name(company, year, market, quarter)
    raw_path = final_dir / f"{output_name}.md"
    raw_path.write_text(md_text, encoding="utf-8")

    if keep_images and images_dir is not None and images_dir.exists():
        shutil.copytree(images_dir, final_dir / "images", dirs_exist_ok=True)

    chunks = split_markdown(md_text, company, year, market, quarter=quarter)
    chunks_path = final_dir / f"{output_name}_chunks.json"
    chunks_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metadata_path = write_metadata(
        company,
        year,
        market,
        source_file,
        total_chunks=len(chunks),
        quarter=quarter,
        output_dir=final_dir,
    )
    emit(
        f"后处理完成：{output_name}.md + {output_name}_chunks.json"
        f"（{len(chunks)} 个 chunk）+ {output_name}_metadata.json"
    )
    return raw_path, chunks_path, metadata_path, len(chunks)


def parse_pdf(
    pdf_path: Path,
    company: str,
    year: str | int,
    market: str,
    *,
    quarter: str | None = None,
    base_url: str | None = None,
    start_page: int = 1,
    end_page: int | None = None,
    page_mode: str = "label",
    keep_images: bool = False,
    overwrite: bool = False,
    log_callback=None,
) -> ParseResult:
    """解析单个 PDF：POST MinerU /file_parse，输出 <公司>_<年份>_<市场> 目录。"""
    emit = log_callback or (lambda line: logger.info(str(line).rstrip()))
    pdf_path = Path(pdf_path)
    output_name = build_output_name(company, year, market, quarter)
    final_dir = OUTPUT_DIR / output_name

    validate_selection(company, year, market, quarter)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 不存在：{pdf_path}")
    if int(start_page) < 1:
        raise ValueError("起始页必须 ≥ 1（按 PDF 阅读器页码，从 1 开始）")
    if end_page is not None and int(end_page) < int(start_page):
        raise ValueError("结束页不能小于起始页")
    if final_dir.exists():
        if not overwrite:
            raise FileExistsError(
                f"输出已存在：{final_dir}\n如需重新解析，请设置 overwrite=True。"
            )
        emit(f"覆盖旧输出：{final_dir}")
        shutil.rmtree(final_dir)

    # 用户输入的页码 → MinerU 物理页索引（0 起）
    start_page_id, end_page_id, page_warnings = resolve_page_range(
        int(start_page),
        int(end_page) if end_page is not None else None,
        pdf_path=pdf_path,
        page_mode=page_mode,
    )
    for warning in page_warnings:
        emit(f"⚠️ {warning}")

    base_url = base_url or get_api_base_url()
    health = check_service_health(base_url)
    emit(f"MinerU 服务正常（{base_url}，version={health.get('version')}）")

    form_data = {
        "backend": "pipeline",        # 固定 pipeline，避免 VLM 模型下载
        "lang_list": "ch",
        "parse_method": "auto",
        "formula_enable": "false",
        "table_enable": "true",
        "image_analysis": "false",    # 不抓取不相关图片
        "return_md": "true",
        "return_images": "false",     # 不需要图片，输出只保留文本与表格
        "response_format_zip": "true",
        "return_original_file": "false",
        "start_page_id": str(start_page_id),
    }
    if end_page_id is not None:
        form_data["end_page_id"] = str(end_page_id)

    files = {
        "files": (
            pdf_path.name,
            open(pdf_path, "rb"),
            "application/pdf",
        )
    }

    emit(f"开始解析：{pdf_path.name}（{output_name}）")
    emit(f"POST {base_url}/file_parse  backend=pipeline  pages={start_page}-{end_page if end_page is not None else '全部'}")
    started = time.time()
    try:
        resp = requests.post(
            f"{base_url}/file_parse",
            files=files,
            data=form_data,
            timeout=3600,
        )
    finally:
        files["files"][1].close()

    duration = time.time() - started
    if resp.status_code != 200:
        detail = ""
        try:
            payload = resp.json()
            detail = json.dumps(payload, ensure_ascii=False)[:1000]
        except Exception:
            detail = resp.text[:1000]
        raise RuntimeError(
            f"MinerU 解析失败（HTTP {resp.status_code}）：{detail}"
        )

    content_type = resp.headers.get("content-type", "")
    if "zip" in content_type or resp.content[:2] == b"PK":
        md_text, images_dir = _extract_zip_response(resp, pdf_path.stem)
    else:
        # 兜底：JSON 响应中直接取 Markdown 内容
        try:
            payload = resp.json()
        except Exception as exc:
            raise RuntimeError("MinerU 返回了无法识别的响应格式") from exc
        results = payload.get("results") or {}
        data = results.get(pdf_path.name) or {}
        md_content = data.get("md_content")
        if not md_content:
            raise RuntimeError(
                f"MinerU 返回中未找到 Markdown 内容：{json.dumps(payload, ensure_ascii=False)[:1000]}"
            )
        md_text = md_content
        images_dir = None

    raw_path, chunks_path, metadata_path, total_chunks = _finalize_output(
        md_text,
        company,
        year,
        market,
        quarter,
        pdf_path.name,
        final_dir,
        keep_images,
        images_dir,
        emit,
    )

    emit(f"解析完成，耗时 {duration:.1f} 秒")
    emit(f"输出目录：{final_dir}")
    return ParseResult(
        output_name=output_name,
        final_dir=final_dir,
        markdown_path=raw_path,
        chunks_path=chunks_path,
        metadata_path=metadata_path,
        total_chunks=total_chunks,
        pdf_path=pdf_path,
        duration_seconds=duration,
    )


# ---------- 命令行入口（供测试 / 批量调用） ----------


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description=(
            "parse_v1：通过 MinerU 本地 API 解析 PDF。"
            "使用前请先启动服务：conda activate annual_report && mineru-api"
        )
    )
    arg_parser.add_argument("pdf", type=Path, help="PDF 文件路径")
    arg_parser.add_argument("--company", required=True, help="公司名（支持手动输入任意公司）")
    arg_parser.add_argument("--year", required=True, help="年份（须与 config/companies.json 一致）")
    arg_parser.add_argument("--market", default=None, choices=["A股", "H股"], help="市场（可选；未上市可不填）")
    arg_parser.add_argument("--quarter", default=None, choices=["Q1", "Q2", "Q3", "Q4"], help="报告时间（可选）")
    arg_parser.add_argument("--base-url", default=None, help="MinerU API 地址，默认 http://127.0.0.1:8000")
    arg_parser.add_argument("--start-page", type=int, default=1, help="起始页（按 PDF 阅读器显示的页码；自动识别页码标签）")
    arg_parser.add_argument("--end-page", type=int, default=None, help="结束页（按 PDF 阅读器显示的页码；不传则解析全部页）")
    arg_parser.add_argument(
        "--page-mode",
        default="label",
        choices=["label", "physical"],
        help="页码解析方式：label=按阅读器显示的页码（默认，自动映射，重复时报错）；physical=按物理页码（PDF 第 N 页，永远唯一）",
    )
    arg_parser.add_argument("--keep-images", action="store_true", default=False, help="保留 images/ 目录与图片引用（默认不保留）")
    arg_parser.add_argument("--overwrite", action="store_true")
    args = arg_parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        result = parse_pdf(
            args.pdf,
            args.company,
            args.year,
            args.market,
            quarter=args.quarter,
            base_url=args.base_url,
            start_page=args.start_page,
            end_page=args.end_page,
            page_mode=args.page_mode,
            keep_images=args.keep_images,
            overwrite=args.overwrite,
            log_callback=print,
        )
    except (PageRangeAmbiguousError, FileExistsError, FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"❌ {exc}")
        sys.exit(1)
    print("最终文件：", result.markdown_path)


if __name__ == "__main__":
    main()
