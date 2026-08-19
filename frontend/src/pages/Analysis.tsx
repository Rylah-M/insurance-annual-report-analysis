import { useEffect, useMemo, useState } from "react";
import {
  api,
  ChartPayload,
  CompanyPeriodMetric,
  CompareMatrix,
  Comparison,
  Indicator
} from "../api/request";
import { BarChart, LineChart, PieChart } from "../components/Chart";
import { DataCard, formatValue } from "../components/Card";
import { AnalysisSelector } from "../components/Selector";

const BUSINESS_SCALE = ["原保险保费收入", "车险保费收入", "非车险保费收入"];
const PROFITABILITY = ["综合成本率", "综合赔付率", "综合费用率", "承保利润", "净利润"];
const RISK = ["核心偿付能力充足率", "综合偿付能力充足率"];

function findMetric(rows: CompanyPeriodMetric[], name: string) {
  return rows.find((row) => row.indicator === name);
}

function metricCards(rows: CompanyPeriodMetric[], names: string[]) {
  return names.map((name) => {
    const metric = findMetric(rows, name);
    return {
      name,
      value: metric?.value ?? null,
      unit: metric?.unit ?? "",
      scope: metric?.business_scope ?? undefined
    };
  });
}

export function Analysis({
  companies,
  years,
  quarters,
  indicators
}: {
  companies: string[];
  years: number[];
  quarters: string[];
  indicators: Indicator[];
}) {
  const [company, setCompany] = useState("");
  const [year, setYear] = useState<number | undefined>();
  const [quarter, setQuarter] = useState("");
  const [indicator, setIndicator] = useState("综合成本率");
  const [metrics, setMetrics] = useState<CompanyPeriodMetric[]>([]);
  const [compareMatrix, setCompareMatrix] = useState<CompareMatrix | null>(null);
  const [premiumChart, setPremiumChart] = useState<ChartPayload | null>(null);
  const [costChart, setCostChart] = useState<ChartPayload | null>(null);
  const [trendChart, setTrendChart] = useState<ChartPayload | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!company && companies.length) setCompany(companies[0]);
    if (!year && years.length) setYear(years[0]);
    if (!quarter && quarters.length) setQuarter(quarters[0]);
    if (!indicator && indicators.length) setIndicator(indicators[0].indicator_name);
  }, [companies, years, quarters, indicators, company, year, quarter, indicator]);

  const runAnalysis = () => {
    if (!company || !year) return;
    setLoading(true);
    setError(null);
    Promise.all([
      api.companyPeriodData(company, year, quarter),
      api.compareMatrix(year, quarter),
      api.barChart("原保险保费收入", year),
      api.barChart("综合成本率", year),
      api.trendChart(company, indicator),
      api.comparison(indicator, year)
    ])
      .then(([metricRows, matrix, premium, cost, trend, comparisonData]) => {
        setMetrics(metricRows);
        setCompareMatrix(matrix);
        setPremiumChart(premium);
        setCostChart(cost);
        setTrendChart(trend);
        setComparison(comparisonData);
      })
      .catch(() => setError("服务器连接失败或当前公司暂无该报告期数据，请检查服务状态。"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    runAnalysis();
  }, [company, year, quarter, indicator]);

  const structureData = useMemo(() => {
    const car = findMetric(metrics, "车险保费收入");
    const nonCar = findMetric(metrics, "非车险保费收入");
    return [car, nonCar]
      .filter((item): item is CompanyPeriodMetric => Boolean(item?.value))
      .map((item) => ({ name: item.indicator, value: item.value ?? 0 }));
  }, [metrics]);

  return (
    <section className="page">
      <header>
        <p>数据分析</p>
        <h1>经营指标分析与公司横向比较</h1>
      </header>

      <div className="analysis-action-row">
        <AnalysisSelector
          companies={companies}
          years={years}
          quarters={quarters}
          indicators={indicators}
          company={company}
          year={year}
          quarter={quarter}
          indicator={indicator}
          mode="period"
          onCompanyChange={setCompany}
          onYearChange={setYear}
          onQuarterChange={setQuarter}
          onIndicatorChange={setIndicator}
        />
        <button className="primary-action" onClick={runAnalysis}>
          开始分析
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <p className="muted">正在读取 FastAPI 分析结果...</p>}

      <section className="panel">
        <h2>指标结果</h2>
        <h3 className="section-title">业务规模</h3>
        <div className="stats-grid">
          {metricCards(metrics, BUSINESS_SCALE).map((metric) => (
            <DataCard
              key={metric.name}
              label={metric.name}
              value={formatValue(metric.value, metric.unit)}
              note={metric.scope}
            />
          ))}
        </div>
        <h3 className="section-title">盈利能力</h3>
        <div className="stats-grid">
          {metricCards(metrics, PROFITABILITY).map((metric) => (
            <DataCard
              key={metric.name}
              label={metric.name}
              value={formatValue(metric.value, metric.unit)}
              note={metric.scope}
            />
          ))}
        </div>
        <h3 className="section-title">风险指标</h3>
        <div className="stats-grid">
          {metricCards(metrics, RISK).map((metric) => (
            <DataCard
              key={metric.name}
              label={metric.name}
              value={formatValue(metric.value, metric.unit)}
              note={metric.scope}
            />
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>公司横向比较</h2>
        <div className="compare-table-wrap">
          <table className="compare-table">
            <thead>
              <tr>
                <th>指标</th>
                {(compareMatrix?.companies ?? []).map((name) => (
                  <th key={name}>{name}</th>
                ))}
                <th>单位</th>
              </tr>
            </thead>
            <tbody>
              {(compareMatrix?.rows ?? [])
                .filter((row) =>
                  ["综合成本率", "原保险保费收入", "净利润", "综合赔付率"].includes(
                    String(row.indicator)
                  )
                )
                .map((row) => (
                  <tr key={String(row.indicator)}>
                    <td>{row.indicator}</td>
                    {(compareMatrix?.companies ?? []).map((name) => (
                      <td key={name}>{formatValue(row[name] as number | null, "")}</td>
                    ))}
                    <td>{row.unit}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="chart-grid">
        <section className="panel">
          <h2>图1：保费规模比较</h2>
          {premiumChart && (
            <BarChart title={premiumChart.title} x={premiumChart.x} y={premiumChart.y} unit={premiumChart.unit} />
          )}
        </section>
        <section className="panel">
          <h2>图2：盈利能力比较</h2>
          {costChart && (
            <BarChart title={costChart.title} x={costChart.x} y={costChart.y} unit={costChart.unit} />
          )}
        </section>
        <section className="panel">
          <h2>图3：业务结构分析</h2>
          <PieChart title={`${company}车险/非车险结构`} data={structureData} unit="百万元" />
        </section>
        <section className="panel">
          <h2>图4：趋势分析</h2>
          {trendChart && (
            <LineChart title={trendChart.title} x={trendChart.x} y={trendChart.y} unit={trendChart.unit} />
          )}
        </section>
      </div>

      <section className="panel">
        <h2>排名与统计</h2>
        <div className="rank-list">
          {(comparison?.ranking ?? []).map((item) => (
            <div key={item.company}>
              <strong>{item.rank}</strong>
              <span>{item.company}</span>
              <b>{formatValue(item.value, item.unit)}</b>
            </div>
          ))}
          {comparison?.ranking.length === 0 && <p className="muted">当前指标暂无可排名数值。</p>}
        </div>
      </section>
    </section>
  );
}
