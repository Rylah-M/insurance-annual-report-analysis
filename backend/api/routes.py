from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4
from typing import Any
import threading
import time
from urllib.parse import quote

import pandas as pd
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi import File, Form, UploadFile
from fastapi.responses import FileResponse, Response

from analysis.comparison import compare_indicator, company_overview, report_snapshot, trend_data
from analysis.report import company_report_data
from agent.chat_agent import answer_question
from agent.report_agent import REPORT_DIR, build_report_data, generate_report_files
from database import get_db_path, list_reports, save_report_artifact
from data_loader import dataframe_profile, load_database, records_for_json
from services.indicator_service import (
    import_database_for_task,
    read_result,
    start_extraction_background,
)
from services.parse_service import start_parse_background
from services.mineru_manager import restart_mineru, stop_mineru
from services.llm_settings import (
    DEFAULT_BASE_URL,
    effective_llm_env,
    is_current_owner,
    load_settings,
    mask_key,
    save_settings,
)
from services.task_store import (
    append_log,
    cancel_task,
    create_task,
    get_task,
    list_tasks,
    update_task,
)


router = APIRouter(prefix="/api")
public_router = APIRouter()


def _indicator_rows(df) -> list[dict[str, Any]]:
    rows = (
        df[["indicator_id", "indicator_name", "unit"]]
        .drop_duplicates()
        .sort_values(["indicator_id", "indicator_name"])
    )
    return [
        {
            "id": row.indicator_id,
            "name": row.indicator_name,
            "unit": row.unit,
            "indicator_id": row.indicator_id,
            "indicator_name": row.indicator_name,
        }
        for row in rows.itertuples()
    ]


def _get_indicator_value(
    company: str,
    indicator: str,
    year: int,
) -> dict[str, Any]:
    df = load_database()
    matched = df[
        (df["company"] == company)
        & (df["indicator_name"] == indicator)
        & (df["year"] == year)
    ].copy()
    if matched.empty:
        raise HTTPException(status_code=404, detail="未找到匹配的公司、年份和指标记录")

    row = matched.iloc[0]
    value = row["indicator_value"]
    return {
        "company": company,
        "indicator": indicator,
        "year": int(row["year"]),
        "report_period": row["report_period"] if "report_period" in row else None,
        "value": None if pd.isna(value) else float(value),
        "unit": row["unit"],
        "business_scope": None if pd.isna(row["business_scope"]) else row["business_scope"],
        "confidence_score": None
        if "confidence_score" not in row or pd.isna(row["confidence_score"])
        else float(row["confidence_score"]),
        "review_status": row["review_status"] if "review_status" in row else None,
    }


def _simple_compare(indicator: str, year: int | None) -> list[dict[str, Any]]:
    comparison = compare_indicator(load_database(), indicator, year)
    return [
        {
            "company": item["company"],
            "year": item["year"],
            "value": item["value"],
            "unit": item["unit"],
        }
        for item in comparison["values"]
    ]


def _bar_chart(indicator: str, year: int | None) -> dict[str, Any]:
    comparison = compare_indicator(load_database(), indicator, year)
    return {
        "title": f"{indicator}比较" if year is None else f"{year}年{indicator}比较",
        "indicator": indicator,
        "year": year,
        "x": comparison["chart"]["xAxis"],
        "y": comparison["chart"]["series"][0]["data"],
        "unit": comparison["chart"]["series"][0]["unit"],
    }


def _normalize_quarter(year: int, quarter: str | None) -> str | None:
    if not quarter:
        return None
    quarter = quarter.strip()
    if quarter.upper().startswith("Q"):
        return f"{year}{quarter.upper()}"
    return quarter


def _period_filter(df: pd.DataFrame, company: str, year: int, quarter: str | None) -> pd.DataFrame:
    filtered = df[(df["company"] == company) & (df["year"] == year)].copy()
    normalized = _normalize_quarter(year, quarter)
    if normalized and "report_period" in filtered.columns:
        filtered = filtered[filtered["report_period"] == normalized]
    return filtered


def _company_period_data(company: str, year: int, quarter: str | None) -> list[dict[str, Any]]:
    df = load_database()
    filtered = _period_filter(df, company, year, quarter)
    if filtered.empty:
        raise HTTPException(status_code=404, detail="当前公司暂无该报告期数据")
    rows = []
    for row in filtered.sort_values(["indicator_id", "indicator_name"]).itertuples():
        rows.append(
            {
                "company": row.company,
                "year": int(row.year),
                "quarter": row.report_period if hasattr(row, "report_period") else None,
                "indicator_id": row.indicator_id,
                "indicator": row.indicator_name,
                "value": None if pd.isna(row.indicator_value) else float(row.indicator_value),
                "unit": row.unit,
                "business_scope": row.business_scope
                if isinstance(row.business_scope, str)
                else None,
                "source_text": row.source_text
                if hasattr(row, "source_text") and isinstance(row.source_text, str)
                else None,
            }
        )
    return rows


def _comparison_matrix(year: int, quarter: str | None = None) -> dict[str, Any]:
    df = load_database()
    normalized = _normalize_quarter(year, quarter)
    filtered = df[df["year"] == year].copy()
    if normalized and "report_period" in filtered.columns:
        filtered = filtered[filtered["report_period"] == normalized]
    companies_list = sorted(filtered["company"].dropna().unique().tolist())
    indicators_list = sorted(filtered["indicator_name"].dropna().unique().tolist())
    rows = []
    for indicator_name in indicators_list:
        indicator_df = filtered[filtered["indicator_name"] == indicator_name]
        row: dict[str, Any] = {"indicator": indicator_name}
        unit = None
        for company_name in companies_list:
            matched = indicator_df[indicator_df["company"] == company_name]
            if matched.empty:
                row[company_name] = None
                continue
            value = matched.iloc[0]["indicator_value"]
            unit = matched.iloc[0]["unit"]
            row[company_name] = None if pd.isna(value) else float(value)
        row["unit"] = unit
        rows.append(row)
    return {
        "year": year,
        "quarter": normalized,
        "companies": companies_list,
        "rows": rows,
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/metadata")
def metadata() -> dict:
    return dataframe_profile(load_database())


@router.get("/records")
def records() -> list[dict]:
    return records_for_json(load_database())


@router.get("/database/download")
def download_database_csv(
    company: str | None = Query(None),
    year: int | None = Query(None),
    report_period: str | None = Query(None),
    indicator: str | None = Query(None),
    filename: str | None = Query(None),
) -> Response:
    df = load_database()
    if company:
        df = df[df["company"] == company]
    if year is not None:
        df = df[df["year"] == year]
    if report_period:
        df = df[df["report_period"] == report_period]
    if indicator:
        keyword = indicator.strip()
        mask = df["indicator_name"].astype(str).str.contains(
            keyword, case=False, na=False
        )
        if "indicator_standard_name" in df.columns:
            mask = mask | df["indicator_standard_name"].astype(str).str.contains(
                keyword, case=False, na=False
            )
        df = df[mask]
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False, encoding="utf-8-sig")
    safe_name = (filename or "").strip().replace("\\", "_").replace("/", "_")
    safe_name = "".join(ch for ch in safe_name if ch not in '\x00\r\n"')
    if not safe_name:
        safe_name = "database_overview"
    if not safe_name.lower().endswith(".csv"):
        safe_name += ".csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="database_overview.csv"; '
                f"filename*=UTF-8''{quote(safe_name)}"
            )
        },
    )


@router.get("/companies")
def companies() -> list[str]:
    df = load_database()
    return sorted(df["company"].dropna().unique().tolist())


@router.get("/years")
def years() -> list[int]:
    df = load_database()
    return sorted(int(year) for year in df["year"].dropna().unique().tolist())


@router.get("/quarters")
def quarters() -> list[str]:
    df = load_database()
    if "report_period" not in df.columns:
        return []
    return sorted(df["report_period"].dropna().unique().tolist())


@router.get("/indicators")
def indicators() -> list[dict]:
    return _indicator_rows(load_database())


@router.get("/analysis/comparison")
def comparison(
    indicator: str = Query(..., description="指标名称"),
    year: int | None = Query(None, description="年份"),
) -> dict:
    df = load_database()
    if indicator not in set(df["indicator_name"].dropna()):
        raise HTTPException(status_code=404, detail="指标不存在")
    return compare_indicator(df, indicator, year)


@router.get("/analysis/company")
def company_analysis(
    company: str = Query(..., description="公司名称"),
    year: int | None = Query(None, description="年份"),
) -> dict:
    df = load_database()
    if company not in set(df["company"].dropna()):
        raise HTTPException(status_code=404, detail="公司不存在")
    return company_overview(df, company, year)


@router.get("/analysis/trend")
def trend(
    company: str = Query(..., description="公司名称"),
    indicator: str = Query(..., description="指标名称"),
) -> dict:
    df = load_database()
    return trend_data(df, company, indicator)


@router.get("/analysis/report-snapshot")
def report_structure(
    company: str = Query(..., description="公司名称"),
    year: int = Query(..., description="年份"),
) -> dict:
    df = load_database()
    return report_snapshot(df, company, year)


@router.get("/indicator/value")
def api_indicator_value(
    company: str = Query(..., description="公司名称"),
    indicator: str = Query(..., description="指标名称"),
    year: int = Query(..., description="年份"),
) -> dict:
    return _get_indicator_value(company, indicator, year)


@router.get("/analysis/compare")
def api_analysis_compare(
    indicator: str = Query(..., description="指标名称"),
    year: int | None = Query(None, description="年份"),
) -> list[dict]:
    return _simple_compare(indicator, year)


@router.get("/chart/bar")
def api_chart_bar(
    indicator: str = Query(..., description="指标名称"),
    year: int | None = Query(None, description="年份"),
) -> dict:
    return _bar_chart(indicator, year)


@router.get("/chart/trend")
def api_chart_trend(
    company: str = Query(..., description="公司名称"),
    indicator: str = Query(..., description="指标名称"),
) -> dict:
    trend = trend_data(load_database(), company, indicator)
    return {
        "title": f"{company}{indicator}趋势",
        "company": company,
        "indicator": indicator,
        "x": trend["chart"]["xAxis"],
        "y": trend["chart"]["series"][0]["data"],
        "series": trend["chart"]["series"],
        "unit": (trend["chart"]["series"][0] or {}).get("unit"),
        "values": trend["values"],
    }


@router.get("/report/company")
def api_company_report(
    company: str = Query(..., description="公司名称"),
    year: int = Query(..., description="年份"),
) -> dict:
    df = load_database()
    if company not in set(df["company"].dropna()):
        raise HTTPException(status_code=404, detail="公司不存在")
    return company_report_data(df, company, year)


@router.get("/company")
def api_company_alias() -> list[str]:
    return companies()


@router.get("/data")
def api_company_period_data(
    company: str = Query(..., description="公司名称"),
    year: int = Query(..., description="年份"),
    quarter: str | None = Query(None, description="报告期，如 Q3 或 2024Q3"),
) -> list[dict]:
    return _company_period_data(company, year, quarter)


@router.get("/compare")
def api_compare_matrix(
    year: int = Query(..., description="年份"),
    quarter: str | None = Query(None, description="报告期，如 Q3 或 2024Q3"),
) -> dict:
    return _comparison_matrix(year, quarter)


@router.post("/report/generate")
def generate_report(
    company: str = Body(..., description="公司名称"),
    year: int = Body(..., description="年份"),
) -> dict[str, Any]:
    df = load_database()
    if company not in set(df["company"].dropna()):
        raise HTTPException(status_code=404, detail="公司不存在")
    if int(year) not in set(df["year"].dropna().astype(int)):
        raise HTTPException(status_code=404, detail="年份不存在")

    data = build_report_data(df, company, int(year))
    files = generate_report_files(df, company, int(year))
    save_report_artifact(
        company,
        int(year),
        data.get("report_period"),
        data.get("title", f"{company} {year}年经营分析报告"),
        {
            "json": Path(files["json"]).name,
            "markdown": Path(files["markdown"]).name,
            "html": Path(files["html"]).name,
            "pdf": Path(files["pdf"]).name if files.get("pdf") else "",
        },
    )
    return {**data, "files": files}


@router.get("/report/download")
def download_report(
    company: str = Query(...),
    year: int = Query(...),
    format: str = Query("html", pattern="^(html|md|markdown|pdf|json)$"),
) -> FileResponse:
    df = load_database()
    if company not in set(df["company"].dropna()):
        raise HTTPException(status_code=404, detail="公司不存在")
    data = build_report_data(df, company, int(year))
    files = generate_report_files(df, company, int(year))
    save_report_artifact(
        company,
        int(year),
        data.get("report_period"),
        data.get("title", f"{company} {year}年经营分析报告"),
        {
            "json": Path(files["json"]).name,
            "markdown": Path(files["markdown"]).name,
            "html": Path(files["html"]).name,
            "pdf": Path(files["pdf"]).name if files.get("pdf") else "",
        },
    )
    key = "markdown" if format in ("md", "markdown") else format
    path = files.get(key)
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="报告文件尚未生成或 PDF 组件不可用")
    media_types = {
        "html": "text/html; charset=utf-8",
        "markdown": "text/markdown; charset=utf-8",
        "pdf": "application/pdf",
        "json": "application/json; charset=utf-8",
    }
    return FileResponse(path, media_type=media_types.get(format, "application/octet-stream"))


@router.get("/report/artifacts")
def report_artifacts(company: str | None = Query(None)) -> dict[str, Any]:
    return {
        "database": str(get_db_path()),
        "report_dir": str(REPORT_DIR),
        "reports": list_reports(company),
    }


@router.post("/chat")
def chat(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")
    return answer_question(question)


@router.post("/report/upload")
async def upload_report(
    file: UploadFile = File(...),
    company: str = Form(...),
    year: str = Form(...),
    quarter: str = Form("Q4"),
    market: str = Form("A股"),
    start_page: int = Form(1),
    end_page: int = Form(0),
    page_mode: str = Form("label"),
    output_name: str = Form(""),
) -> dict[str, Any]:
    if not company.strip():
        raise HTTPException(status_code=400, detail="公司名称不能为空")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")
    if quarter not in {"Q1", "Q2", "Q3", "Q4"}:
        raise HTTPException(status_code=400, detail="报告期仅支持 Q1/Q2/Q3/Q4")
    if market not in {"A股", "H股"}:
        raise HTTPException(status_code=400, detail="市场仅支持 A股 / H股")
    if int(start_page) < 1:
        raise HTTPException(status_code=400, detail="起始页必须大于等于 1")
    if int(end_page) > 0 and int(end_page) < int(start_page):
        raise HTTPException(status_code=400, detail="结束页不能小于起始页")
    if page_mode not in {"label", "physical"}:
        raise HTTPException(status_code=400, detail="页码模式仅支持 label / physical")

    task_id = uuid4().hex[:16]
    custom_name = output_name.strip() or None
    task = create_task(
        task_id,
        company=company.strip(),
        year=str(year).strip(),
        quarter=quarter,
        market=market,
        source_file=file.filename,
    )
    upload_dir = Path(get_db_path()).resolve().parents[1] / "tasks" / task_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{task_id}_{Path(file.filename).name}"
    pdf_path = upload_dir / safe_name
    content = await file.read()
    pdf_path.write_bytes(content)
    append_log(task_id, f"已接收 PDF：{file.filename}（{len(content) / 1024 / 1024:.1f} MB）")
    update_task(task_id, status="uploaded", progress=10, stage="PDF 上传完成")
    start_parse_background(
        task_id,
        pdf_path,
        company.strip(),
        str(year).strip(),
        quarter,
        market,
        start_page=int(start_page),
        end_page=None if int(end_page) <= 0 else int(end_page),
        page_mode=page_mode,
        output_name=custom_name,
    )
    return {"task_id": task_id, "status": "uploaded"}


@router.get("/report/status/{task_id}")
def report_status(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task_id,
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "stage": task.get("stage", ""),
        "steps": task.get("steps", []),
        "logs": task.get("logs", [])[-80:],
        "error": task.get("error", ""),
        "result_file": task.get("result_file", ""),
        "output_name": task.get("output_name", ""),
        "result_rows": task.get("result_rows", 0),
        "save_to_database": task.get("save_to_database", True),
        "database_imported": task.get("database_imported", False),
        "database_path": task.get("database_path", ""),
    }


@router.get("/settings/llm")
def get_llm_settings() -> dict[str, Any]:
    settings = load_settings()
    configured = bool(settings.get("api_key")) and is_current_owner(settings)
    needs_reconfigure = bool(settings.get("foreign_key_detected")) or (
        bool(settings.get("api_key")) and not is_current_owner(settings)
    )
    return {
        "configured": configured,
        "needs_reconfigure": needs_reconfigure,
        "base_url": settings.get("base_url", DEFAULT_BASE_URL),
        "api_key_masked": mask_key(settings.get("api_key", "")),
        "updated_at": settings.get("updated_at", ""),
    }


@router.post("/settings/llm")
def set_llm_settings(
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    api_key = (payload.get("api_key") or "").strip()
    base_url = (payload.get("base_url") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    if base_url and not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="接口地址必须以 http:// 或 https:// 开头")
    settings = save_settings(api_key, base_url or DEFAULT_BASE_URL)
    return {
        "configured": True,
        "needs_reconfigure": False,
        "base_url": settings["base_url"],
        "api_key_masked": mask_key(settings["api_key"]),
        "updated_at": settings["updated_at"],
    }


@router.post("/settings/llm/test")
def test_llm_settings(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    from openai import OpenAI

    api_key = (payload.get("api_key") or "").strip()
    base_url = (payload.get("base_url") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    client = OpenAI(api_key=api_key, base_url=base_url or DEFAULT_BASE_URL)
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
            timeout=30,
        )
        return {"ok": True, "reply": response.choices[0].message.content[:50]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


@router.post("/report/cancel/{task_id}")
def cancel_report_task(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("status") not in {"processing", "extracting", "uploaded"}:
        raise HTTPException(status_code=409, detail="当前任务状态不支持取消")
    cancel_task(task_id, "用户手动终止")
    append_log(task_id, "用户已请求终止任务")

    if task.get("status") == "processing":
        try:
            stopped = stop_mineru()
            append_log(task_id, f"MinerU 服务已中断（{stopped}），正在恢复...")
        except Exception as exc:
            append_log(task_id, f"中断 MinerU 失败: {exc}")

    def _restart_later() -> None:
        time.sleep(1)
        try:
            restart_mineru()
        except Exception:
            pass

    threading.Thread(target=_restart_later, daemon=True).start()
    return {"task_id": task_id, "status": "cancelled"}


@router.post("/indicator/extract/{task_id}")
def start_indicator_extract(
    task_id: str,
    payload: dict[str, Any] = Body(default={}),
) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("status") == "failed":
        raise HTTPException(status_code=400, detail="解析任务失败，无法启动指标提取")
    if task.get("status") == "extracting":
        return {"task_id": task_id, "status": "extracting", "message": "指标提取正在进行中"}
    if task.get("status") == "processing":
        raise HTTPException(status_code=409, detail="解析仍在进行中，请等待完成")
    if task.get("status") == "success" and task.get("result_rows"):
        return {"task_id": task_id, "status": "success", "result_file": task.get("result_file", "")}
    update_task(task_id, status="extracting")
    start_extraction_background(task_id)
    return {
        "task_id": task_id,
        "status": "started",
    }


@router.post("/indicator/import/{task_id}")
def import_indicator_result(task_id: str) -> dict[str, Any]:
    try:
        return import_database_for_task(task_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/indicator/result/{task_id}")
def indicator_result(task_id: str) -> dict[str, Any]:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.get("status") != "success" or not task.get("result_rows"):
        return {
            "task_id": task_id,
            "status": task.get("status", "unknown"),
            "stage": task.get("stage", ""),
            "rows": [],
        }
    tag = task.get("output_name", "")
    results = read_result(tag)
    rows = []
    for item in results:
        rows.append(
            {
                "company": item.get("company", task.get("company", "")),
                "year": item.get("year", task.get("year", "")),
                "quarter": task.get("quarter", ""),
                "market": task.get("market", ""),
                "indicator_id": item.get("indicator_id", ""),
                "indicator_name": item.get("indicator_name", ""),
                "indicator_value": item.get("indicator_value", ""),
                "unit": item.get("unit", ""),
                "business_scope": item.get("business_scope", ""),
                "source_text": item.get("source_text", ""),
                "confidence_score": item.get("confidence_score", ""),
            }
        )
    return {
        "task_id": task_id,
        "status": "success",
        "company": task.get("company", ""),
        "year": task.get("year", ""),
        "quarter": task.get("quarter", ""),
        "market": task.get("market", ""),
        "rows": rows,
    }


@router.get("/report/tasks")
def report_tasks() -> dict[str, Any]:
    return {"tasks": list_tasks()}


@public_router.get("/companies")
def public_companies() -> list[str]:
    return companies()


@public_router.get("/quarters")
def public_quarters() -> list[str]:
    return quarters()


@public_router.get("/indicators")
def public_indicators() -> list[dict]:
    return indicators()


@public_router.get("/indicator/value")
def public_indicator_value(
    company: str = Query(..., description="公司名称"),
    indicator: str = Query(..., description="指标名称"),
    year: int = Query(..., description="年份"),
) -> dict:
    return _get_indicator_value(company, indicator, year)


@public_router.get("/analysis/compare")
def public_analysis_compare(
    indicator: str = Query(..., description="指标名称"),
    year: int | None = Query(None, description="年份"),
) -> list[dict]:
    return _simple_compare(indicator, year)


@public_router.get("/chart/bar")
def public_chart_bar(
    indicator: str = Query(..., description="指标名称"),
    year: int | None = Query(None, description="年份"),
) -> dict:
    return _bar_chart(indicator, year)


@public_router.get("/chart/trend")
def public_chart_trend(
    company: str = Query(..., description="公司名称"),
    indicator: str = Query(..., description="指标名称"),
) -> dict:
    return api_chart_trend(company, indicator)


@public_router.get("/report/company")
def public_company_report(
    company: str = Query(..., description="公司名称"),
    year: int = Query(..., description="年份"),
) -> dict:
    return api_company_report(company, year)
