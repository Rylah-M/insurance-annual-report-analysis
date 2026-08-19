import { useEffect, useMemo, useState } from "react";
import { Download, FilterX, Search } from "lucide-react";
import { api, Metadata } from "../api/request";
import { DataCard } from "../components/Card";

export function Dashboard({
  metadata,
  onNavigate
}: {
  metadata: Metadata | null;
  onNavigate: (page: string) => void;
}) {
  const [records, setRecords] = useState<Array<Record<string, unknown>>>([]);
  const [companyFilter, setCompanyFilter] = useState("");
  const [yearFilter, setYearFilter] = useState("");
  const [periodFilter, setPeriodFilter] = useState("");
  const [indicatorFilter, setIndicatorFilter] = useState("");
  const [fileName, setFileName] = useState("database_overview.csv");

  useEffect(() => {
    api
      .records()
      .then(setRecords)
      .catch(() => setRecords([]));
  }, []);

  const dataQuality = metadata
    ? `${Math.round((metadata.available_values / Math.max(metadata.rows, 1)) * 1000) / 10}%`
    : "加载中";
  const coverage = metadata?.years.length
    ? `${Math.min(...metadata.years)}-${Math.max(...metadata.years)}`
    : "加载中";

  const columns = useMemo(() => {
    if (metadata?.field_names?.length) return metadata.field_names;
    return records.length ? Object.keys(records[0]) : [];
  }, [metadata, records]);

  const periods = useMemo(
    () =>
      Array.from(
        new Set(
          records
            .map((row) => String(row.report_period ?? ""))
            .filter(Boolean)
        )
      ).sort(),
    [records]
  );

  const filtered = useMemo(() => {
    const keyword = indicatorFilter.trim().toLowerCase();
    return records.filter((row) => {
      const company = String(row.company ?? "");
      const year = row.year === null || row.year === undefined ? "" : String(row.year);
      const period = String(row.report_period ?? "");
      const indicator =
        String(row.indicator_name ?? "") + String(row.indicator_standard_name ?? "");
      if (companyFilter && company !== companyFilter) return false;
      if (yearFilter && year !== yearFilter) return false;
      if (periodFilter && period !== periodFilter) return false;
      if (keyword && !indicator.toLowerCase().includes(keyword)) return false;
      return true;
    });
  }, [records, companyFilter, yearFilter, periodFilter, indicatorFilter]);

  const renderCell = (value: unknown) =>
    value === null || value === undefined || value === "" ? "-" : String(value);

  const clearFilters = () => {
    setCompanyFilter("");
    setYearFilter("");
    setPeriodFilter("");
    setIndicatorFilter("");
  };

  const downloadUrl = useMemo(
    () =>
      api.databaseDownload({
        company: companyFilter || undefined,
        year: yearFilter || undefined,
        report_period: periodFilter || undefined,
        indicator: indicatorFilter.trim() || undefined,
        filename: fileName.trim() || undefined
      }),
    [companyFilter, yearFilter, periodFilter, indicatorFilter, fileName]
  );

  return (
    <section className="page">
      <header>
        <p>Dashboard</p>
        <h1>上市财险公司年报智能分析 Agent</h1>
      </header>

      <div className="quick-actions">
        <button className="primary-action" onClick={() => onNavigate("upload")}>
          上传年报
        </button>
        <button className="primary-action" onClick={() => onNavigate("autoReport")}>
          生成分析报告
        </button>
        <button className="ghost-action" onClick={() => onNavigate("chat")}>
          智能问答
        </button>
        <button className="ghost-action" onClick={() => onNavigate("analysis")}>
          数据分析
        </button>
      </div>

      <div className="stats-grid">
        <DataCard label="覆盖公司" value={metadata?.company_count ?? "加载中"} />
        <DataCard label="指标数量" value={metadata?.indicator_count ?? "加载中"} />
        <DataCard label="数据记录" value={metadata?.rows ?? "加载中"} />
        <DataCard label="年报覆盖范围" value={coverage} note={`可用数值率 ${dataQuality}`} />
      </div>

      <div className="overview-layout">
        <section className="panel">
          <h2>项目介绍</h2>
          <div className="feature-list">
            <div>
              <strong>结构化指标库</strong>
              <span>年报数据经解析与提取后写入 SQLite 指标库，支持快速检索。</span>
            </div>
            <div>
              <strong>自动分析报告</strong>
              <span>基于指标数据自动生成文字分析、图表与可下载报告。</span>
            </div>
            <div>
              <strong>智能问答 Agent</strong>
              <span>数据库检索结合 LLM，回答业务规模、盈利与偿付能力问题。</span>
            </div>
          </div>
        </section>

        <section className="panel">
          <h2>数据文件画像</h2>
          <div className="fact-list">
            <div>
              <span>字段数</span>
              <strong>{metadata?.columns ?? "-"}</strong>
            </div>
            <div>
              <span>年份</span>
              <strong>{metadata?.years.join("、") || "-"}</strong>
            </div>
            <div>
              <span>单位</span>
              <strong>{metadata?.units.join("、") || "-"}</strong>
            </div>
            <div>
              <span>重复记录</span>
              <strong>{metadata?.duplicate_rows ?? "-"}</strong>
            </div>
            <div>
              <span>重复业务键</span>
              <strong>{metadata?.duplicate_keys ?? "-"}</strong>
            </div>
          </div>
        </section>
      </div>

      <div className="overview-layout">
        <section className="panel">
          <h2>当前数据范围</h2>
          <div className="tag-row">
            {(metadata?.companies ?? []).map((company) => (
              <span key={company}>{company}</span>
            ))}
          </div>
          <div className="field-cloud">
            {(metadata?.indicators ?? []).map((indicator) => (
              <span key={indicator}>{indicator}</span>
            ))}
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="task-title">
          <h2>数据库总览</h2>
          <span className="muted">{filtered.length} / {records.length} 条</span>
          <div className="db-download-row">
            <label>
              下载文件名
              <input
                value={fileName}
                onChange={(event) => setFileName(event.target.value)}
                placeholder="database_overview.csv"
              />
            </label>
            <a className="ghost-action" href={downloadUrl} download={fileName}>
              <Download size={16} />
              下载 CSV
            </a>
          </div>
        </div>

        <div className="toolbar db-filter-bar">
          <label>
            公司
            <select value={companyFilter} onChange={(event) => setCompanyFilter(event.target.value)}>
              <option value="">全部</option>
              {(metadata?.companies ?? []).map((company) => (
                <option key={company} value={company}>
                  {company}
                </option>
              ))}
            </select>
          </label>
          <label>
            年份
            <select value={yearFilter} onChange={(event) => setYearFilter(event.target.value)}>
              <option value="">全部</option>
              {(metadata?.years ?? []).map((year) => (
                <option key={year} value={String(year)}>
                  {year}
                </option>
              ))}
            </select>
          </label>
          <label>
            报告期
            <select value={periodFilter} onChange={(event) => setPeriodFilter(event.target.value)}>
              <option value="">全部</option>
              {periods.map((period) => (
                <option key={period} value={period}>
                  {period}
                </option>
              ))}
            </select>
          </label>
          <label className="db-search">
            指标名称
            <span className="db-search-input">
              <Search size={15} />
              <input
                value={indicatorFilter}
                onChange={(event) => setIndicatorFilter(event.target.value)}
                placeholder="输入指标关键词"
              />
            </span>
          </label>
          <button className="ghost-action compact" onClick={clearFilters}>
            <FilterX size={16} />
            清除筛选
          </button>
        </div>

        <div className="compare-table-wrap db-table">
          <table className="compare-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, index) => (
                <tr key={index}>
                  {columns.map((column) => (
                    <td key={column}>{renderCell(row[column])}</td>
                  ))}
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={columns.length || 1} className="muted">
                    当前筛选条件下暂无记录。
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
