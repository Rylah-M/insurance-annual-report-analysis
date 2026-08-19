import { useEffect, useState } from "react";
import { Download, FileText, Loader2, Send } from "lucide-react";
import { api, GeneratedReport, ReportIndicator } from "../api/request";

const BASE_YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026];

function formatReportValue(value: number | null, unit: string | null) {
  if (value === null || value === undefined) return "暂无数据";
  if (unit === "%") return `${value.toFixed(2)}%`;
  if (unit === "百万元") return `${(value / 100).toFixed(2)}亿元`;
  if (unit === "万元") return `${(value / 10000).toFixed(2)}亿元`;
  return `${value.toFixed(2)}${unit ?? ""}`;
}

function IndicatorRow({ indicator }: { indicator: ReportIndicator }) {
  return (
    <div className="report-row">
      <div>
        <strong>{indicator.indicator}</strong>
        <span>{indicator.business_scope ?? "暂无业务范围"}</span>
      </div>
      <b>{formatReportValue(indicator.value, indicator.unit)}</b>
    </div>
  );
}

export function AutoReport({
  companies,
  years
}: {
  companies: string[];
  years: number[];
}) {
  const [company, setCompany] = useState("");
  const [year, setYear] = useState<number | undefined>();
  const [report, setReport] = useState<GeneratedReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const yearOptions = Array.from(new Set([...years, ...BASE_YEARS])).sort((a, b) => a - b);

  useEffect(() => {
    if (!company && companies.length) setCompany(companies[0]);
    if (!year && years.length) setYear(years[0]);
  }, [companies, years, company, year]);

  const generate = () => {
    if (!company || !year) return;
    setLoading(true);
    setError(null);
    api
      .generateReport(company, year)
      .then(setReport)
      .catch(() => setError("报告生成失败，请确认服务与数据库状态正常。"))
      .finally(() => setLoading(false));
  };

  return (
    <section className="page">
      <header>
        <p>自动报告</p>
        <h1>公司经营分析报告生成</h1>
      </header>

      <div className="analysis-action-row">
        <div className="toolbar">
          <label>
            公司
            <select value={company} onChange={(event) => setCompany(event.target.value)}>
              {companies.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            年份
            <select value={year ?? ""} onChange={(event) => setYear(Number(event.target.value))}>
              {yearOptions.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button className="primary-action" onClick={generate} disabled={loading}>
          {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
          {loading ? "生成中" : "生成分析报告"}
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      {report && (
        <>
          <section className="panel report-toolbar">
            <div>
              <h2>{report.title}</h2>
              <p className="muted">
                生成时间 {new Date(report.generated_at).toLocaleString()} · 报告期{" "}
                {report.report_period ?? report.year}
              </p>
            </div>
            <div className="download-actions">
              <a
                className="ghost-action"
                href={api.downloadReport(report.company, report.year, "pdf")}
                download
              >
                <Download size={16} /> PDF
              </a>
              <a
                className="ghost-action"
                href={api.downloadReport(report.company, report.year, "md")}
                download
              >
                <FileText size={16} /> Markdown
              </a>
              <a
                className="ghost-action"
                href={api.downloadReport(report.company, report.year, "html")}
                download
              >
                <FileText size={16} /> HTML
              </a>
            </div>
          </section>

          <section className="panel">
            <h2>摘要与关键发现</h2>
            <div className="stats-grid">
              <div className="data-card">
                <span>指标数量</span>
                <strong>{report.summary.metric_count}</strong>
              </div>
              <div className="data-card">
                <span>有效数值</span>
                <strong>{report.summary.available_value_count}</strong>
              </div>
              <div className="data-card">
                <span>覆盖公司</span>
                <strong>{report.data_coverage?.company_count ?? 0}</strong>
              </div>
              <div className="data-card">
                <span>业务口径</span>
                <strong>{report.company_basic.business_scope ?? "未披露"}</strong>
              </div>
            </div>
            <div className="findings-list">
              {(report.summary.key_findings ?? []).map((finding) => (
                <div key={finding}>
                  <span>关键发现</span>
                  <b>{finding}</b>
                </div>
              ))}
            </div>
          </section>

          <div className="report-grid">
            {report.sections.map((section) => (
              <section className="panel" key={section.category}>
                <h2>{section.category}</h2>
                <div className="report-list">
                  {section.indicators.map((indicator) => (
                    <IndicatorRow key={indicator.indicator_id} indicator={indicator} />
                  ))}
                </div>
                {section.charts.map((chart) => (
                  <div className="report-chart" key={chart.name}>
                    <img src={chart.data} alt={chart.name} />
                  </div>
                ))}
              </section>
            ))}
          </div>

          <section className="panel">
            <h2>分析结论</h2>
            <div className="narrative-list">
              {report.narratives.map((narrative) => (
                <div key={narrative.section}>
                  <strong>{narrative.section}</strong>
                  <p>{narrative.content}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>风险与复核提示</h2>
            <div className="risk-list">
              {report.risks.map((risk) => (
                <div key={`${risk.type}-${risk.indicator}`}>
                  <strong>{risk.indicator}</strong>
                  <span>{risk.message}</span>
                </div>
              ))}
              {report.risks.length === 0 && <p className="muted">当前暂无风险提示。</p>}
            </div>
          </section>
        </>
      )}
    </section>
  );
}
