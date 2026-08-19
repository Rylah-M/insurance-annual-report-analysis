import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  CircleDashed,
  FileUp,
  Loader2,
  Play,
  Square,
  XCircle
} from "lucide-react";
import { api, ReportTask, ReportTaskStatus, UploadReportResponse } from "../api/request";

const PARSE_STAGES = [
  { key: "PDF 上传完成", progress: 10, label: "PDF 上传完成" },
  { key: "MinerU 解析", progress: 40, label: "MinerU 解析" },
  { key: "Markdown 生成", progress: 70, label: "Markdown 生成" },
  { key: "Chunk 切片完成", progress: 100, label: "Chunk 切片完成" }
];

const EXTRACT_STAGES = [
  "指标召回",
  "候选增强",
  "候选排序",
  "LLM 指标提取",
  "数据生成"
];

function cleanLogLine(line: string) {
  const match = line.match(
    /\{'error': \{'message': '([^']*)'[\s\S]*?'code': '([^']*)'\}/
  );
  if (match) {
    const prefix = line.slice(0, line.indexOf("{")).trim();
    return `${prefix} HTTP ${match[2]}: ${match[1]}`;
  }
  return line;
}

export function UploadReport({
  onExtractionStarted
}: {
  onExtractionStarted: (taskId: string) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [company, setCompany] = useState("");
  const [year, setYear] = useState("2024");
  const [quarter, setQuarter] = useState("Q4");
  const [market, setMarket] = useState("A股");
  const [startPage, setStartPage] = useState("1");
  const [endPage, setEndPage] = useState("0");
  const [pageMode, setPageMode] = useState<"label" | "physical">("label");
  const [outputName, setOutputName] = useState("");
  const [tasks, setTasks] = useState<ReportTask[]>([]);
  const [taskId, setTaskId] = useState("");
  const [status, setStatus] = useState<ReportTaskStatus | null>(null);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState("");
  const timerRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const refreshTasks = async () => {
    try {
      const data = await api.reportTasks();
      setTasks(data.tasks);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    refreshTasks();
  }, []);

  const defaultOutputName = [company.trim(), year, quarter, market].filter(Boolean).join("_");
  const effectiveOutputName = outputName.trim() || defaultOutputName;

  const pollStatus = (id: string) => {
    stopPolling();
    timerRef.current = window.setInterval(async () => {
      try {
        const next = await api.reportStatus(id);
        setStatus(next);
        if (["failed", "success", "cancelled"].includes(next.status)) stopPolling();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        stopPolling();
      }
    }, 1500);
  };

  const handleUpload = async () => {
    if (!file) {
      setError("请先选择 PDF 文件");
      return;
    }
    if (!company.trim()) {
      setError("请填写公司名称");
      return;
    }
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("company", company.trim());
      form.append("year", year);
      form.append("quarter", quarter);
      form.append("market", market);
      form.append("start_page", startPage);
      form.append("end_page", endPage);
      form.append("page_mode", pageMode);
      form.append("output_name", effectiveOutputName);
      const created: UploadReportResponse = await api.uploadReport(form);
      setTaskId(created.task_id);
      setStatus({
        task_id: created.task_id,
        status: "uploaded",
        progress: 10,
        stage: "PDF 上传完成",
        steps: [],
        logs: [],
        error: "",
        result_file: "",
        output_name: ""
      });
      pollStatus(created.task_id);
      refreshTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  };

  const handleExtract = async () => {
    if (!taskId) return;
    setExtracting(true);
    setError("");
    try {
      await api.startExtraction(taskId);
      onExtractionStarted(taskId);
      pollStatus(taskId);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setExtracting(false);
    }
  };

  const handleCancel = async () => {
    if (!taskId) return;
    setCancelling(true);
    setError("");
    try {
      await api.cancelReportTask(taskId);
      stopPolling();
      setStatus({
        ...(status ?? {
          task_id: taskId,
          status: "cancelled",
          progress: 0,
          stage: "已取消",
          steps: [],
          logs: [],
          error: "用户手动终止",
          result_file: "",
          output_name: ""
        }),
        status: "cancelled",
        stage: "已取消",
        progress: 0,
        error: "用户手动终止"
      });
      refreshTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setCancelling(false);
    }
  };

  const watchTask = (id: string) => {
    setTaskId(id);
    setStatus(null);
    setError("");
    pollStatus(id);
  };

  const progress = status?.progress ?? 0;
  const failed = status?.status === "failed";
  const cancelled = status?.status === "cancelled";
  const parseDone = status?.status === "success" || status?.status === "extracting";
  const currentStage = status?.stage ?? "";
  const activeTask = status?.status === "processing" || status?.status === "extracting" || status?.status === "uploaded";
  const runningTaskCount = tasks.filter((task) =>
    ["processing", "extracting", "uploaded"].includes(task.status)
  ).length;

  return (
    <section className="page">
      <header>
        <p>上传年报</p>
        <h1>上传 PDF 并自动解析生成 chunks</h1>
      </header>

      <section className="panel">
        <div className="upload-form">
          <label className="file-drop">
            <input
              type="file"
              accept="application/pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <FileUp size={24} />
            <strong>{file ? file.name : "选择年报 PDF"}</strong>
            <span>{file ? `${(file.size / 1024 / 1024).toFixed(1)} MB` : "支持 PDF 格式"}</span>
          </label>

          <div className="upload-fields">
            <label>
              公司名称
              <input
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                placeholder="例如：中国太保"
              />
            </label>
            <label>
              年份
              <select value={year} onChange={(event) => setYear(event.target.value)}>
                {["2025", "2024", "2023", "2022", "2021", "2020"].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              报告期
              <select value={quarter} onChange={(event) => setQuarter(event.target.value)}>
                {["Q1", "Q2", "Q3", "Q4"].map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              市场
              <select value={market} onChange={(event) => setMarket(event.target.value)}>
                <option value="A股">A股</option>
                <option value="H股">H股</option>
              </select>
            </label>
            <label>
              起始页
              <input
                type="number"
                min={1}
                value={startPage}
                onChange={(event) => setStartPage(event.target.value)}
              />
            </label>
            <label>
              结束页（0 = 全部）
              <input
                type="number"
                min={0}
                value={endPage}
                onChange={(event) => setEndPage(event.target.value)}
              />
            </label>
            <label>
              页码模式
              <select
                value={pageMode}
                onChange={(event) => setPageMode(event.target.value as "label" | "physical")}
              >
                <option value="label">阅读器显示页码</option>
                <option value="physical">物理页码</option>
              </select>
            </label>
            <label>
              chunks 输出命名
              <input
                value={effectiveOutputName}
                onChange={(event) => setOutputName(event.target.value)}
                placeholder="公司_年份_报告期_市场"
              />
            </label>
          </div>
          <p className="form-hint">
            默认命名：{defaultOutputName || "公司_年份_报告期_市场"}；切换左侧栏目不会中断正在进行的解析任务。
          </p>

          <button
            className="primary-action upload-submit"
            onClick={handleUpload}
            disabled={uploading || (status?.status === "processing" && !failed)}
          >
            {uploading ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
            开始解析
          </button>
        </div>
      </section>

      {error && <div className="error-banner">{error}</div>}

      {taskId && (
        <section className="panel">
          <div className="task-title">
            <h2>
              解析任务
              <span className="task-id-short" title={`完整任务编号：${taskId}`}>
                #{taskId.slice(0, 8)}
              </span>
            </h2>
            <span className={`task-badge ${status?.status ?? ""}`}>{status?.status ?? "等待开始"}</span>
            {activeTask && (
              <button className="cancel-action" onClick={handleCancel} disabled={cancelling}>
                {cancelling ? <Loader2 className="spin" size={16} /> : <Square size={16} />}
                终止任务
              </button>
            )}
          </div>

          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <p className="progress-caption">
            {failed
              ? `失败：${status?.error || status?.stage || ""}`
              : cancelled
                ? `已取消：${status?.error || "用户手动终止"}`
                : `${progress}% · ${currentStage || "等待开始"}`}
          </p>

          <div className="stage-grid">
            {PARSE_STAGES.map((stage) => {
              const done = progress >= stage.progress;
              const active = currentStage === stage.label && !done && !failed;
              return (
                <div className={`stage-item ${done ? "done" : ""} ${active ? "active" : ""}`} key={stage.key}>
                  {done ? <CheckCircle2 size={18} /> : active ? <Loader2 className="spin" size={18} /> : <CircleDashed size={18} />}
                  <span>{stage.label}</span>
                  <small>{done ? "完成" : active ? "处理中" : "等待"}</small>
                </div>
              );
            })}
          </div>

          {parseDone && (
            <div className="extract-action-row">
              <button
                className="primary-action"
                onClick={handleExtract}
                disabled={extracting || status?.status === "extracting"}
              >
                {extracting || status?.status === "extracting" ? (
                  <Loader2 className="spin" size={18} />
                ) : (
                  <Play size={18} />
                )}
                {status?.status === "extracting" ? "指标提取中..." : "启动指标提取"}
              </button>
            </div>
          )}

          {["指标召回", "候选增强", "候选排序", "LLM 指标提取", "数据生成"].some(
            (stage) => currentStage === stage
          ) && (
            <div className="extract-stages">
              {EXTRACT_STAGES.map((stage, index) => {
                const stageIndex = EXTRACT_STAGES.indexOf(currentStage);
                const done = stageIndex > index;
                const active = stageIndex === index;
                return (
                  <span className={`extract-step ${done ? "done" : ""} ${active ? "active" : ""}`} key={stage}>
                    {done ? <CheckCircle2 size={16} /> : active ? <Loader2 className="spin" size={16} /> : <CircleDashed size={16} />}
                    {index + 1}. {stage}
                  </span>
                );
              })}
            </div>
          )}

          {failed && <XCircle className="failed-icon" size={20} />}

          {status && status.logs.length > 0 && (
            <details className="log-details">
              <summary>查看运行日志</summary>
              <pre className="log-box">
                {status.logs.slice(-40).map(cleanLogLine).join("\n")}
              </pre>
            </details>
          )}
        </section>
      )}

      <section className="panel">
        <div className="task-title">
          <h2>最近解析任务</h2>
          <span className="muted">{runningTaskCount > 0 ? `${runningTaskCount} 个任务进行中` : "无进行中任务"}</span>
        </div>
        {tasks.length === 0 ? (
          <p className="placeholder">暂无历史任务。任务会在后台继续运行，切换页面不会中断。</p>
        ) : (
          <div className="compare-table-wrap">
            <table className="compare-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>文件</th>
                  <th>状态</th>
                  <th>进度</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td>
                      <strong>{task.company}</strong>
                      <small className="table-sub">
                        {task.year} {task.quarter} {task.market}
                      </small>
                    </td>
                    <td>{task.source_file}</td>
                    <td>
                      <span className={`task-badge ${task.status}`}>{task.status}</span>
                    </td>
                    <td>{task.progress}% · {task.stage}</td>
                    <td>
                      <button className="ghost-action compact" onClick={() => watchTask(task.task_id)}>
                        查看
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
