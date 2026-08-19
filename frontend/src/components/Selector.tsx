import { Indicator } from "../api/request";

export function AnalysisSelector({
  companies,
  years,
  quarters,
  indicators,
  company,
  year,
  quarter,
  indicator,
  mode = "indicator",
  onCompanyChange,
  onYearChange,
  onQuarterChange,
  onIndicatorChange
}: {
  companies: string[];
  years: number[];
  quarters?: string[];
  indicators?: Indicator[];
  company: string;
  year?: number;
  quarter?: string;
  indicator?: string;
  mode?: "indicator" | "period";
  onCompanyChange: (value: string) => void;
  onYearChange: (value: number) => void;
  onQuarterChange?: (value: string) => void;
  onIndicatorChange?: (value: string) => void;
}) {
  return (
    <div className="toolbar">
      <label>
        公司
        <select value={company} onChange={(event) => onCompanyChange(event.target.value)}>
          {companies.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      <label>
        年份
        <select value={year ?? ""} onChange={(event) => onYearChange(Number(event.target.value))}>
          {years.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      {mode === "period" && (
        <label>
          报告期
          <select value={quarter ?? ""} onChange={(event) => onQuarterChange?.(event.target.value)}>
            {(quarters ?? []).map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      )}
      {indicator !== undefined && onIndicatorChange && (
        <label>
          指标
          <select value={indicator} onChange={(event) => onIndicatorChange(event.target.value)}>
            {(indicators ?? []).map((item) => (
              <option key={`${item.indicator_id}-${item.indicator_name}`} value={item.indicator_name}>
                {item.indicator_name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
