const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API 请求失败: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function requestJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error(`API 请求失败: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export type Metadata = {
  rows: number;
  columns: number;
  field_names: string[];
  field_types: Record<string, string>;
  company_count: number;
  companies: string[];
  year_count: number;
  years: number[];
  indicator_count: number;
  indicators: string[];
  units: string[];
  nulls: Record<string, number>;
  duplicate_rows: number;
  duplicate_keys: number;
  available_values: number;
};

export type Indicator = {
  id?: string;
  name?: string;
  indicator_id: string;
  indicator_name: string;
  unit: string;
};

export type IndicatorValue = {
  company: string;
  indicator: string;
  year: number;
  report_period: string | null;
  value: number | null;
  unit: string;
  business_scope: string | null;
  confidence_score: number | null;
  review_status: string | null;
};

export type ComparisonValue = {
  company: string;
  year: number;
  indicator?: string;
  value: number | null;
  unit: string;
  business_scope?: string | null;
  review_status?: string | null;
};

export type Comparison = {
  indicator: string;
  year: number | null;
  values: ComparisonValue[];
  statistics: {
    count: number;
    unit: string | null;
    max?: number | null;
    min?: number | null;
    mean?: number | null;
    median?: number | null;
    warning?: string;
  };
  ranking: Array<
    ComparisonValue & { rank: number; company_average_difference: number }
  >;
  chart: {
    type: string;
    xAxis: string[];
    series: Array<{ name: string; data: Array<number | null>; unit: string | null }>;
  };
};

export type ChartPayload = {
  title: string;
  indicator: string;
  year?: number | null;
  company?: string;
  x: Array<string | number>;
  y: Array<number | null>;
  unit: string | null;
  values?: Array<Record<string, unknown>>;
};

export type CompanyPeriodMetric = {
  company: string;
  year: number;
  quarter: string | null;
  indicator_id: string;
  indicator: string;
  value: number | null;
  unit: string;
  business_scope: string | null;
  source_text: string | null;
};

export type CompareMatrix = {
  year: number;
  quarter: string | null;
  companies: string[];
  rows: Array<Record<string, string | number | null>>;
};

export type CompanyOverview = {
  company: string;
  year: number | null;
  metric_count: number;
  available_value_count: number;
  metrics: Record<
    string,
    { value: number | null; unit: string; business_scope: string | null }
  >;
  categories: Record<
    string,
    Array<{
      indicator_id: string;
      indicator: string;
      value: number | null;
      unit: string;
      business_scope: string | null;
      confidence_score: number | null;
      review_status: string | null;
    }>
  >;
};

export type CompanyReport = {
  company: string;
  year: number;
  summary: {
    metric_count: number;
    available_value_count: number;
  };
  sections: Record<
    string,
    Array<{
      indicator_id: string;
      indicator: string;
      value: number | null;
      unit: string;
      business_scope: string | null;
      confidence_score: number | null;
      review_status: string | null;
    }>
  >;
  risks: Array<{
    type: string;
    indicator: string;
    message: string;
    confidence_score?: number;
  }>;
};

export type ReportIndicator = {
  indicator_id: string;
  indicator: string;
  value: number | null;
  unit: string | null;
  business_scope: string | null;
  confidence_score: number | null;
  review_status: string | null;
};

export type ReportSection = {
  category: string;
  indicators: ReportIndicator[];
  charts: Array<{ name: string; data: string }>;
};

export type ReportNarrative = {
  section: string;
  content: string;
};

export type GeneratedReport = {
  generated_at: string;
  company: string;
  year: number;
  report_period: string | null;
  title: string;
  summary: {
    metric_count: number;
    available_value_count: number;
    key_findings: string[];
  };
  company_basic: {
    company: string;
    year: number;
    report_period: string | null;
    market: string;
    business_scope: string | null;
  };
  data_coverage?: {
    companies: string[];
    company_count: number;
    indicator_count: number;
  };
  sections: ReportSection[];
  narratives: ReportNarrative[];
  risks: Array<{
    type: string;
    indicator: string;
    message: string;
    confidence_score?: number;
  }>;
  files: {
    json: string;
    markdown: string;
    html: string;
    pdf?: string;
  };
};

export type ChatSource = {
  company: string;
  year: number | null;
  indicator: string;
  value: number | null;
  unit: string | null;
  source_text: string | null;
  source_page: string | null;
  confidence_score: number | null;
};

export type ChatResponse = {
  question: string;
  answer: string;
  source: ChatSource[];
  context?: {
    company: string | null;
    year: number | null;
    indicator: string | null;
    category: string | null;
  };
};

export type ReportTaskStep = {
  name: string;
  progress: number;
  stage: string;
  time: string;
  status: string;
};

export type ReportTaskStatus = {
  task_id: string;
  status: string;
  progress: number;
  stage: string;
  steps: ReportTaskStep[];
  logs: string[];
  error: string;
  result_file: string;
  output_name: string;
  result_rows?: number;
  save_to_database?: boolean;
  database_imported?: boolean;
  database_path?: string;
};

export type UploadReportResponse = {
  task_id: string;
  status: string;
};

export type ReportTask = {
  task_id: string;
  company: string;
  year: string;
  quarter: string;
  market: string;
  source_file: string;
  status: string;
  progress: number;
  stage: string;
  created_at: string;
  result_rows?: number;
  save_to_database?: boolean;
  database_imported?: boolean;
  database_path?: string;
};

export type ExtractionStartResponse = {
  task_id: string;
  status: string;
  result_file?: string;
  message?: string;
};

export type ExtractionResult = {
  task_id: string;
  status: string;
  company: string;
  year: string;
  quarter: string;
  market: string;
  rows: Array<{
    company: string;
    year: string;
    quarter: string;
    market: string;
    indicator_id: string;
    indicator_name: string;
    indicator_value: string;
    unit: string;
    business_scope: string;
    source_text: string;
    confidence_score: string;
  }>;
};

export type LlmSettings = {
  configured: boolean;
  base_url: string;
  api_key_masked: string;
  updated_at: string;
};

export type LlmTestResult = {
  ok: boolean;
  reply?: string;
  error?: string;
};

export const api = {
  metadata: () => request<Metadata>("/api/metadata"),
  records: () => request<Array<Record<string, unknown>>>("/api/records"),
  databaseDownload: (params?: {
    company?: string;
    year?: string;
    report_period?: string;
    indicator?: string;
    filename?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.company) search.set("company", params.company);
    if (params?.year) search.set("year", params.year);
    if (params?.report_period) search.set("report_period", params.report_period);
    if (params?.indicator) search.set("indicator", params.indicator);
    if (params?.filename) search.set("filename", params.filename);
    const qs = search.toString();
    return `${API_BASE}/api/database/download${qs ? `?${qs}` : ""}`;
  },
  companies: () => request<string[]>("/companies"),
  years: () => request<number[]>("/api/years"),
  quarters: () => request<string[]>("/api/quarters"),
  indicators: () => request<Indicator[]>("/indicators"),
  companyPeriodData: (company: string, year: number, quarter?: string) => {
    const params = new URLSearchParams({ company, year: String(year) });
    if (quarter) params.set("quarter", quarter);
    return request<CompanyPeriodMetric[]>(`/api/data?${params}`);
  },
  compareMatrix: (year: number, quarter?: string) => {
    const params = new URLSearchParams({ year: String(year) });
    if (quarter) params.set("quarter", quarter);
    return request<CompareMatrix>(`/api/compare?${params}`);
  },
  indicatorValue: (company: string, indicator: string, year: number) => {
    const params = new URLSearchParams({ company, indicator, year: String(year) });
    return request<IndicatorValue>(`/indicator/value?${params}`);
  },
  comparison: (indicator: string, year?: number) => {
    const params = new URLSearchParams({ indicator });
    if (year) params.set("year", String(year));
    return request<Comparison>(`/api/analysis/comparison?${params}`);
  },
  barChart: (indicator: string, year?: number) => {
    const params = new URLSearchParams({ indicator });
    if (year) params.set("year", String(year));
    return request<ChartPayload>(`/chart/bar?${params}`);
  },
  trendChart: (company: string, indicator: string) => {
    const params = new URLSearchParams({ company, indicator });
    return request<ChartPayload>(`/chart/trend?${params}`);
  },
  company: (company: string, year?: number) => {
    const params = new URLSearchParams({ company });
    if (year) params.set("year", String(year));
    return request<CompanyOverview>(`/api/analysis/company?${params}`);
  },
  report: (company: string, year: number) => {
    const params = new URLSearchParams({ company, year: String(year) });
    return request<CompanyReport>(`/report/company?${params}`);
  },
  generateReport: (company: string, year: number) =>
    requestJson<GeneratedReport>("/api/report/generate", { company, year }),
  downloadReport: (company: string, year: number, format: "html" | "md" | "pdf" | "json") => {
    const params = new URLSearchParams({ company, year: String(year), format });
    return `${API_BASE}/api/report/download?${params}`;
  },
  chat: (question: string) => requestJson<ChatResponse>("/api/chat", { question }),
  reportArtifacts: () => request<{
    database: string;
    report_dir: string;
    reports: Array<{
      id: number;
      company: string;
      year: number;
      report_period: string | null;
      title: string;
      generated: boolean;
      created_at: string | null;
    }>;
  }>("/api/report/artifacts"),
  uploadReport: (formData: FormData) =>
    fetch(`${API_BASE}/api/report/upload`, {
      method: "POST",
      body: formData
    }).then(async (response) => {
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `API 请求失败: ${response.status}`);
      }
      return response.json() as Promise<UploadReportResponse>;
    }),
  reportStatus: (taskId: string) =>
    request<ReportTaskStatus>(`/api/report/status/${taskId}`),
  reportTasks: () => request<{ tasks: ReportTask[] }>("/api/report/tasks"),
  cancelReportTask: (taskId: string) =>
    requestJson<{ task_id: string; status: string }>(
      `/api/report/cancel/${taskId}`,
      {}
    ),
  startExtraction: (taskId: string, saveToDatabase = true) =>
    requestJson<ExtractionStartResponse>(`/api/indicator/extract/${taskId}`, {
      save_to_database: saveToDatabase
    }),
  importExtraction: (taskId: string) =>
    requestJson<{ task_id: string; status: string; database_path?: string }>(
      `/api/indicator/import/${taskId}`,
      {}
    ),
  extractionResult: (taskId: string) =>
    request<ExtractionResult>(`/api/indicator/result/${taskId}`),
  getLlmSettings: () => request<LlmSettings>("/api/settings/llm"),
  saveLlmSettings: (apiKey: string, baseUrl: string) =>
    requestJson<LlmSettings>("/api/settings/llm", { api_key: apiKey, base_url: baseUrl }),
  testLlmSettings: (apiKey: string, baseUrl: string) =>
    requestJson<LlmTestResult>("/api/settings/llm/test", {
      api_key: apiKey,
      base_url: baseUrl
    })
};
