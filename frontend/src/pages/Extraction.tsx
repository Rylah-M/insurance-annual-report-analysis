import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  CircleDashed,
  Database,
  Loader2,
  Play,
  RefreshCw
} from "lucide-react";
import { api, ExtractionResult, ReportTask, ReportTaskStatus } from "../api/request";

const STAGES = ["指标召回", "候选增强", "候选排序", "LLM 指标提取", "数据生成"];
const DONE_STAGES = ["数据生成", "数据生成（未入库）"];

export function Extraction({ taskId }: { taskId: string }) {
  const [viewTaskId, setViewTaskId] = useState(taskId);
  const [status, setStatus] = useState<ReportTaskStatus | null>(null);
  const [result, setResult] = useState<ExtractionResult | null>(null);
  const [tasks, setTasks] = useState<ReportTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState("");
  const [startError, setStartError] = useState("");
  const timerRef = useRef<number | null>(null);

  const load = async (id: string = viewTaskId) => {
    setLoading(true);
    try {
      const current = await api.reportStatus(id);
      setStatus(current);
      if (current.status === "success" && DONE_STAGES.includes(current.stage)) {
        const data = await api.extractionResult(id);
        setResult(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const refreshTasks = async () => {
    try {
      const data = await api.reportTasks();
      setTasks(
        data.tasks.filter(
          (task) => task.status === "success" && (task.result_rows ?? 0) > 0
        )
      );
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    refreshTasks();
  }, []);

  useEffect(() => {
    setStatus(null);
    setResult(null);
    setStartError("");
    load(viewTaskId);
    timerRef.current = window.setInterval(() => {
      api.reportStatus(viewTaskId).then((current) => {
        setStatus(current);
        if (current.status === "success" && DONE_STAGES.includes(current.stage)) {
          api.extractionResult(viewTaskId).then(setResult);
          window.clearInterval(timerRef.current ?? undefined);
          timerRef.current = null;
        }
      });
    }, 2000);
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
    };
  }, [viewTaskId]);

  const progress = status?.progress ?? 0;
  const currentStage = status?.stage ?? "";
  const rows = result?.rows ?? [];
  const extractionDone = status?.status === "success" && DONE_STAGES.includes(currentStage);
  const parseDoneWithoutExtract =
    status?.status === "success" && !extractionDone && currentStage === "Chunk 切片完成";
  const extracting = status?.status === "extracting";
  const imported =
    status?.database_imported === true || Boolean(status?.database_path);

  const startExtraction = async () => {
    setStarting(true);
    setStartError("");
    try {
      await api.startExtraction(viewTaskId);
      await load(viewTaskId);
    } catch (err) {
      setStartError(err instanceof Error ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  };

  const handleImport = async () => {
    setImporting(true);
    setImportError("");
    try {
      await api.importExtraction(viewTaskId);
      setStatus((current) =>
        current
          ? { ...current, database_imported: true, database_path: "已写入" }
          : current
      );
      await load(viewTaskId);
      refreshTasks();
    } catch (err) {
      setImportError(err instanceof Error ? err.message : String(err));
    } finally {
      setImporting(false);
    }
  };

  return (
    <section className="page">
      <header>
        <p>指标提取</p>
        <h1>指标召回、排序与 LLM 提取</h1>
      </header>

      <section className="panel">
        <div className="task-title">
          <h2>
            任务
            <span className="task-id-short" title={`完整任务编号：${viewTaskId}`}>
              #{viewTaskId.slice(0, 8)}
            </span>
          </h2>
          <span className={`task-badge ${status?.status ?? ""}`}>{status?.status ?? "等待开始"}</span>
          <button className="ghost-action" onClick={() => load()} disabled={loading}>
            <RefreshCw className={loading ? "spin" : ""} size={16} />
            刷新
          </button>
        </div>
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
        <p className="progress-caption">
          {status?.status === "failed"
            ? `失败：${status?.error || status?.stage || ""}`
            : extractionDone
              ? `完成 · ${rows.length} 条结果 · ${imported ? "已写入数据库" : "未写入数据库"}`
              : `${progress}% · ${currentStage || "等待开始"}`}
        </p>

        {startError && <div className="error-banner">{startError}</div>}
        {importError && <div className="error-banner">{importError}</div>}

        {extractionDone && (
          <div className="extract-action-row">
            <button
              className="primary-action"
              onClick={handleImport}
              disabled={importing || imported}
            >
              {importing ? <Loader2 className="spin" size={18} /> : <Database size={18} />}
              {imported ? "已写入数据库" : "写入数据库"}
            </button>
          </div>
        )}

        {parseDoneWithoutExtract && (
          <div className="extract-action-row">
            <button className="primary-action" onClick={startExtraction} disabled={starting}>
              {starting ? <Loader2 className="spin" size={18} /> : <Play size={18} />}
              启动指标提取
            </button>
          </div>
        )}

        <div className="extract-stages">
          {STAGES.map((stage, index) => {
            const stageIndex = STAGES.indexOf(currentStage);
            const done = progress >= [20, 40, 60, 85, 100][index];
            const active = stageIndex === index && !done;
            return (
              <span className={`extract-step ${done ? "done" : ""} ${active ? "active" : ""}`} key={stage}>
                {done ? (
                  <CheckCircle2 size={16} />
                ) : active ? (
                  <Loader2 className="spin" size={16} />
                ) : (
                  <CircleDashed size={16} />
                )}
                {index + 1}. {stage}
              </span>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <div className="task-title">
          <h2>提取结果</h2>
          <span className="muted">
            {rows.length > 0 ? `${rows.length} 条记录` : "暂无结果"}
          </span>
        </div>

        {rows.length > 0 ? (
          <div className="compare-table-wrap">
            <table className="compare-table">
              <thead>
                <tr>
                  <th>指标</th>
                  <th>数值</th>
                  <th>单位</th>
                  <th>置信度</th>
                  <th>业务范围</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${row.indicator_id}-${index}`}>
                    <td>
                      <strong>{row.indicator_name}</strong>
                      <small className="table-sub">{row.indicator_id}</small>
                    </td>
                    <td>{row.indicator_value || "-"}</td>
                    <td>{row.unit || "-"}</td>
                    <td>{row.confidence_score !== "" ? row.confidence_score : "-"}</td>
                    <td>{row.business_scope || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="placeholder">提取完成后将在这里展示结构化指标数据。</p>
        )}

        {result?.rows && result.rows.length > 0 && (
          <details className="log-details">
            <summary>查看来源原文</summary>
            <div className="source-list">
              {result.rows.map((row, index) => (
                <div className="source-item" key={index}>
                  <strong>
                    {row.indicator_name}
                    <ArrowRight size={14} />
                    {row.indicator_value} {row.unit}
                  </strong>
                  <p>{row.source_text || "无来源文本"}</p>
                </div>
              ))}
            </div>
          </details>
        )}
      </section>

      <section className="panel">
        <div className="task-title">
          <h2>最近提取完成的项目</h2>
          <span className="muted">{tasks.length} 个</span>
        </div>
        {tasks.length === 0 ? (
          <p className="placeholder">暂无已完成的提取项目。</p>
        ) : (
          <div className="compare-table-wrap">
            <table className="compare-table">
              <thead>
                <tr>
                  <th>公司</th>
                  <th>年份 / 报告期</th>
                  <th>源文件</th>
                  <th>结果</th>
                  <th>入库</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td>
                      <strong>{task.company}</strong>
                      <small className="table-sub">{task.task_id.slice(0, 8)}</small>
                    </td>
                    <td>
                      {task.year} {task.quarter} {task.market}
                    </td>
                    <td>{task.source_file}</td>
                    <td>{task.result_rows} 条</td>
                    <td>
                      {task.database_imported === true || Boolean(task.database_path)
                        ? "已入库"
                        : "未入库"}
                    </td>
                    <td>
                      <button
                        className="ghost-action compact"
                        onClick={() => setViewTaskId(task.task_id)}
                      >
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
