"""parse_v1 Web 界面：上传 PDF → 选择公司/年份/市场 → MinerU 解析 → 输出 Markdown + 结构化 chunks。

启动方式：
    conda activate annual_report
    streamlit run app.py

使用前请先启动 MinerU API 服务（./start_mineru_api.sh 或 mineru-api）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

from output_manager import discover_companies, list_completed
from parser import (
    UPLOAD_DIR,
    build_output_name,
    check_service_health,
    get_api_base_url,
    get_pdf_page_info,
    load_companies_config,
    parse_pdf,
)

st.set_page_config(
    page_title="parse_v1 · 年报 PDF 解析 Agent",
    page_icon="📄",
    layout="wide",
)

config = load_companies_config()
CUSTOM_COMPANY_LABEL = "✏️ 输入新公司..."
known_companies = sorted(set(config.get("companies", [])) | set(discover_companies()))
company_options = known_companies + [CUSTOM_COMPANY_LABEL]
years = config.get("years") or [str(y) for y in range(2015, 2027)]
quarters = config.get("quarters") or ["Q1", "Q2", "Q3", "Q4"]
markets = config.get("markets") or ["A股", "H股"]

st.title("📄 parse_v1 · 年报 PDF 解析 Agent")
st.caption(
    "上传年报 PDF → 选择公司 / 年份 / 市场（下拉菜单，命名与数据库标准一致）"
    "→ 开源 MinerU 解析 → 输出 Markdown + 结构化 JSON chunks"
)

with st.sidebar:
    st.header("⚙️ 配置")
    st.caption(
        "公司支持下拉选择或手动输入；年份、报告时间、市场下拉项来自 "
        "config/companies.json。"
    )
    st.divider()
    st.caption("MinerU API 地址：" + get_api_base_url())
    if st.button("重新检查 MinerU 服务", key="check_service", use_container_width=True):
        try:
            health = check_service_health()
            st.success(f"✅ 服务正常（version={health.get('version')}）")
        except Exception as exc:  # noqa: BLE001 —— 向用户展示完整错误
            st.error(str(exc))

# 服务状态提示
try:
    health = check_service_health()
    st.success(f"✅ MinerU 服务已连接：{get_api_base_url()}（version={health.get('version')}）")
except Exception:
    st.warning(
        "⚠️ MinerU 服务未启动。请先运行 ./start_mineru_api.sh "
        "或在终端执行 conda activate annual_report && mineru-api。"
    )

col_upload, col_meta = st.columns([3, 2], gap="medium")

with col_upload:
    uploaded = st.file_uploader("上传年报 PDF", type=["pdf"])
    if uploaded is not None:
        st.write(f"📎 {uploaded.name}（{uploaded.size / 1024 / 1024:.1f} MB）")
        upload_key = f"{uploaded.name}|{uploaded.size}"
        if st.session_state.get("_upload_key") != upload_key:
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            saved_path = UPLOAD_DIR / f"{int(time.time())}_{uploaded.name}"
            saved_path.write_bytes(uploaded.getbuffer())
            st.session_state["_upload_key"] = upload_key
            st.session_state["_upload_path"] = str(saved_path)
            st.session_state.pop("_page_info", None)
        saved_path = Path(st.session_state.get("_upload_path", ""))
        if saved_path.exists() and st.session_state.get("_page_info") is None:
            st.session_state["_page_info"] = get_pdf_page_info(saved_path)
        page_info = st.session_state.get("_page_info") or {}
        if page_info:
            total = page_info.get("total_pages", 0)
            duplicates = page_info.get("duplicates", {})
            if duplicates:
                sample = "、".join(list(duplicates)[:5])
                st.warning(
                    f"⚠️ 该 PDF 存在重复页码（如 {sample} 等），通常来自附录重新编号；"
                    "此时请改用“按物理页码”输入，并参考下方页码对照表。"
                )
            with st.expander(f"📖 页码对照（共 {total} 页）"):
                label_map = page_info.get("label_map", {})
                physical_to_label = {}
                for label, indices in label_map.items():
                    for index in indices:
                        physical_to_label[index + 1] = label
                rows = [
                    (i, physical_to_label.get(i, str(i)))
                    for i in range(1, total + 1)
                ]
                shown = rows[:8] + ([("...", "...")] if total > 16 else []) + rows[-8:]
                st.table(
                    {
                        "物理页（PDF 第 N 页）": [str(r[0]) for r in shown],
                        "阅读器显示页码": [str(r[1]) for r in shown],
                    }
                )
                st.caption(
                    "输入页码时请按你阅读器里看到的页码填；若遇到重复页码，切到"
                    "“按物理页码”并填左侧数字。"
                )

with col_meta:
    st.subheader("报告信息")
    company_choice = st.selectbox("公司", company_options)
    if company_choice == CUSTOM_COMPANY_LABEL:
        company = st.text_input(
            "输入公司名称",
            value=st.session_state.get("custom_company", ""),
            placeholder="例如：众安在线",
        )
        st.session_state["custom_company"] = company
        if not company.strip():
            st.warning("请输入公司名称后再开始解析")
    else:
        company = company_choice
        st.session_state["custom_company"] = ""
    year = st.selectbox("年份", years)
    quarter = st.selectbox("报告时间", quarters)
    market_choice = st.selectbox("市场", ["不选（未上市）", *markets])
    market = None if market_choice == "不选（未上市）" else market_choice
    output_name = build_output_name(company, year, market, quarter)
    st.text_input(
        "输出命名（自动生成）",
        value=(
            f"{output_name}.md / {output_name}_chunks.json / "
            f"{output_name}_metadata.json"
        ),
        disabled=True,
    )

with st.expander("解析选项（默认与已验证参数一致）"):
    page_mode_label = st.radio(
        "页码输入方式",
        ["按阅读器显示页码（自动映射）", "按物理页码（PDF 第 N 页）"],
        index=0,
        horizontal=True,
        help="有重复页码（如附录重新编号）时请选择“按物理页码”",
    )
    page_mode = "physical" if page_mode_label.startswith("按物理") else "label"
    p1, p2 = st.columns(2)
    start_page = p1.number_input(
        "起始页（PDF 页码，从 1 开始）",
        min_value=1,
        value=1,
        help="按 PDF 阅读器显示的页码输入；系统会自动识别 PDF 页码标签（如物理 36 页显示为 32，则填 32）",
    )
    end_page = p2.number_input(
        "结束页（0 = 全部）",
        min_value=0,
        value=0,
        help="0 表示解析到最后一页；否则按 PDF 阅读器显示的页码输入",
    )
    o1, o2 = st.columns(2)
    keep_images = o1.checkbox(
        "保留图片",
        value=False,
        help="默认关闭：只输出文本与表格，不抓取无关图片",
    )
    overwrite = o2.checkbox("覆盖已存在的结果", value=False)
    st.caption(
        "解析后端固定为 pipeline；语言 ch；关闭图片分析；保留表格；关闭公式。"
    )

if st.button("🚀 开始解析", type="primary", key="start_parse", disabled=uploaded is None, use_container_width=True):
    if uploaded is None:
        st.warning("请先上传 PDF")
        st.stop()

    pdf_path = Path(st.session_state.get("_upload_path", ""))
    if not pdf_path.exists():
        st.error("上传文件未保存成功，请重新上传")
        st.stop()

    log_lines: list[str] = []
    status = st.status(f"正在解析 {output_name} ...", expanded=True)
    log_area = st.empty()

    def log_callback(line: str) -> None:
        log_lines.append(str(line))
        log_area.code("\n".join(log_lines[-30:]), language="text")

    try:
        result = parse_pdf(
            pdf_path,
            company,
            year,
            market,
            quarter=quarter,
            start_page=int(start_page),
            end_page=None if end_page <= 0 else int(end_page),
            page_mode=page_mode,
            keep_images=keep_images,
            overwrite=overwrite,
            log_callback=log_callback,
        )
        status.update(
            label=(
                f"✅ 解析完成：{output_name}（{result.total_chunks} 个 chunk，"
                f"耗时 {result.duration_seconds:.1f} 秒）"
            ),
            state="complete",
            expanded=False,
        )
        st.success(
            f"输出目录：{result.final_dir}（共 {result.total_chunks} 个 chunk）"
        )
        c1, c2, c3 = st.columns(3)
        c1.download_button(
            "⬇️ 下载 Markdown",
            data=result.markdown_path.read_text(encoding="utf-8"),
            file_name=f"{output_name}.md",
            mime="text/markdown",
        )
        c2.download_button(
            "⬇️ 下载 chunks.json",
            data=result.chunks_path.read_text(encoding="utf-8"),
            file_name=f"{output_name}_chunks.json",
            mime="application/json",
        )
        c3.download_button(
            "⬇️ 下载 metadata.json",
            data=result.metadata_path.read_text(encoding="utf-8"),
            file_name=f"{output_name}_metadata.json",
            mime="application/json",
        )
        with st.expander("内容预览（前 3000 字）"):
            st.markdown(result.markdown_path.read_text(encoding="utf-8")[:3000])
        with st.expander("chunks 预览（前 5 个）"):
            chunks = json.loads(result.chunks_path.read_text(encoding="utf-8"))
            st.json(chunks[:5])
    except FileExistsError as exc:
        status.update(label="⚠️ 输出已存在", state="error", expanded=False)
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001 —— 向用户展示完整错误
        status.update(label="❌ 解析失败", state="error", expanded=False)
        st.error(str(exc))

st.divider()
st.subheader("📂 已完成解析")
completed = list_completed()
if not completed:
    st.info("还没有解析结果")
else:
    for item in completed:
        chunks_text = f" · {item['total_chunks']} chunks" if item.get("total_chunks") else ""
        size_text = f" · {item['raw_size_kb']} KB" if item.get("raw_size_kb") else ""
        st.write(f"- **{item['name']}**{chunks_text}{size_text} · `{item['path']}`")
