import { useEffect, useState } from "react";
import { api, CompanyReport, Indicator } from "../api/request";
import { DataCard, formatValue } from "../components/Card";
import { AnalysisSelector } from "../components/Selector";

const BASE_YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026];

export function Report({
  companies,
  years,
  indicators
}: {
  companies: string[];
  years: number[];
  indicators: Indicator[];
}) {
  const [company, setCompany] = useState("");
  const [year, setYear] = useState<number | undefined>();
  const [indicator, setIndicator] = useState("");
  const [report, setReport] = useState<CompanyReport | null>(null);
  const yearOptions = Array.from(new Set([...years, ...BASE_YEARS])).sort((a, b) => a - b);

  useEffect(() => {
    if (!company && companies.length) setCompany(companies[0]);
    if (!year && years.length) setYear(years[0]);
    if (!indicator && indicators.length) setIndicator(indicators[0].indicator_name);
  }, [companies, years, indicators, company, year, indicator]);

  useEffect(() => {
    if (!company || !year) return;
    api.report(company, year).then(setReport);
  }, [company, year]);

  return (
    <section className="page">
      <header>
        <p>业务分析</p>
        <h1>公司经营分析结果</h1>
      </header>

      <AnalysisSelector
        companies={companies}
        years={yearOptions}
        indicators={indicators}
        company={company}
        year={year}
        indicator={indicator}
        onCompanyChange={setCompany}
        onYearChange={setYear}
        onIndicatorChange={setIndicator}
      />

      <div className="stats-grid report-stats">
        <DataCard label="公司" value={report?.company ?? "-"} />
        <DataCard label="年份" value={report?.year ?? "-"} />
        <DataCard label="指标数" value={report?.summary.metric_count ?? "-"} />
        <DataCard label="可用指标值" value={report?.summary.available_value_count ?? "-"} />
      </div>

      <div className="report-grid">
        {Object.entries(report?.sections ?? {}).map(([section, rows]) => (
          <section className="panel" key={section}>
            <h2>{section}</h2>
            <div className="report-list">
              {rows.map((row) => (
                <div key={`${section}-${row.indicator_id}`} className="report-row">
                  <div>
                    <strong>{row.indicator}</strong>
                    <span>{row.business_scope ?? "暂无业务范围"}</span>
                  </div>
                  <b>{formatValue(row.value, row.unit)}</b>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>

      <section className="panel">
        <h2>风险与复核提示</h2>
        <div className="risk-list">
          {(report?.risks ?? []).map((risk) => (
            <div key={`${risk.type}-${risk.indicator}`}>
              <strong>{risk.indicator}</strong>
              <span>{risk.message}</span>
            </div>
          ))}
          {report?.risks.length === 0 && <p className="muted">当前暂无风险提示。</p>}
        </div>
      </section>
    </section>
  );
}
