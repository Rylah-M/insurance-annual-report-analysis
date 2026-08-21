import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import {
  AlertCircle,
  BarChart3,
  Bot,
  FileOutput,
  FileSearch,
  Home,
  KeyRound,
  MessageCircle,
  ScrollText
} from "lucide-react";
import "antd/dist/reset.css";
import "./styles.css";
import { api, Indicator, Metadata } from "./api/request";
import { Analysis } from "./pages/Analysis";
import { AutoReport } from "./pages/AutoReport";
import { Chat } from "./pages/Chat";
import { Dashboard } from "./pages/Dashboard";
import { Report } from "./pages/Report";
import { Settings } from "./pages/Settings";
import { UploadReport } from "./pages/UploadReport";

type PageKey =
  | "overview"
  | "analysis"
  | "report"
  | "autoReport"
  | "chat"
  | "extraction"
  | "settings";

const navItems = [
  { key: "overview" as const, label: "项目总览", icon: Home },
  { key: "extraction" as const, label: "指标提取", icon: FileSearch },
  { key: "analysis" as const, label: "数据分析", icon: BarChart3 },
  { key: "report" as const, label: "业务分析", icon: ScrollText },
  { key: "autoReport" as const, label: "自动报告", icon: FileOutput },
  { key: "chat" as const, label: "智能问答", icon: MessageCircle },
  { key: "settings" as const, label: "模型设置", icon: KeyRound }
];

function App() {
  const [page, setPage] = useState<PageKey>("overview");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [companies, setCompanies] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [quarters, setQuarters] = useState<string[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.metadata(), api.companies(), api.years(), api.quarters(), api.indicators()])
      .then(([meta, companyList, yearList, quarterList, indicatorList]) => {
        setMetadata(meta);
        setCompanies(companyList);
        setYears(yearList);
        setQuarters(quarterList);
        setIndicators(indicatorList);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (page === "overview") {
      api
        .metadata()
        .then(setMetadata)
        .catch(() => undefined);
    }
  }, [page]);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Bot size={26} />
          <div>
            <strong>保险公司年报分析</strong>
            <span>上市保险公司</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={page === item.key ? "active" : ""}
                key={item.key}
                onClick={() => setPage(item.key)}
                title={item.label}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="content">
        {error && (
          <div className="error-banner">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}
        <div style={page === "overview" ? undefined : { display: "none" }}>
          <Dashboard
            metadata={metadata}
            onNavigate={(target) => setPage(target as PageKey)}
            active={page === "overview"}
          />
        </div>
        <div style={page === "analysis" ? undefined : { display: "none" }}>
          <Analysis companies={companies} years={years} quarters={quarters} indicators={indicators} />
        </div>
        <div style={page === "report" ? undefined : { display: "none" }}>
          <Report companies={companies} years={years} indicators={indicators} />
        </div>
        <div style={page === "autoReport" ? undefined : { display: "none" }}>
          <AutoReport companies={companies} years={years} />
        </div>
        <Chat active={page === "chat"} />
        <div style={page === "extraction" ? undefined : { display: "none" }}>
          <UploadReport />
        </div>
        <div style={page === "settings" ? undefined : { display: "none" }}>
          <Settings />
        </div>
      </main>
    </div>
  );
}

function Placeholder({ title, text }: { title: string; text: string }) {
  return (
    <section className="page">
      <header>
        <p>{title}</p>
        <h1>{title}</h1>
      </header>
      <section className="panel placeholder">
        <p>{text}</p>
      </section>
    </section>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
