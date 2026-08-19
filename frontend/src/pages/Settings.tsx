import { useEffect, useState } from "react";
import {
  CheckCircle2,
  KeyRound,
  Loader2,
  Save,
  ShieldCheck,
  XCircle
} from "lucide-react";
import { api, LlmSettings } from "../api/request";

const DEFAULT_BASE_URL = "https://api.nwafu-ai.cn/v1";

export function Settings() {
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [current, setCurrent] = useState<LlmSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    api
      .getLlmSettings()
      .then((settings) => {
        setCurrent(settings);
        setBaseUrl(settings.base_url || DEFAULT_BASE_URL);
      })
      .catch((err) =>
        setMessage({ ok: false, text: err instanceof Error ? err.message : String(err) })
      );
  }, []);

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setMessage({ ok: false, text: "请输入 API Key" });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const saved = await api.saveLlmSettings(apiKey.trim(), baseUrl.trim());
      setCurrent(saved);
      setApiKey("");
      setMessage({ ok: true, text: "已保存，后续指标提取将使用该 Key" });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!apiKey.trim() && !current?.configured) {
      setMessage({ ok: false, text: "请先输入 API Key" });
      return;
    }
    setTesting(true);
    setMessage(null);
    try {
      const key = apiKey.trim() || "";
      const result = await api.testLlmSettings(key, baseUrl.trim());
      setMessage(
        result.ok
          ? { ok: true, text: "连接成功（deepseek-chat）" }
          : { ok: false, text: result.error || "连接失败" }
      );
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : String(err) });
    } finally {
      setTesting(false);
    }
  };

  return (
    <section className="page">
      <header>
        <p>模型设置</p>
        <h1>配置指标提取使用的 API Key</h1>
      </header>

      {current?.needs_reconfigure && (
        <div className="error-banner">
          <XCircle size={18} />
          <span>
            检测到当前保存的 API Key 来自其他电脑，不能直接使用；请重新输入你自己的 API Key 并点击“保存并生效”。
          </span>
        </div>
      )}

      <section className="panel">
        <div className="settings-status">
          <KeyRound size={22} />
          <div>
            <strong>
              {current?.needs_reconfigure
                ? "需要重新配置 API Key"
                : current?.configured
                  ? "已配置 API Key"
                  : "尚未配置 API Key"}
            </strong>
            <span>
              {current?.needs_reconfigure
                ? "当前保存的 Key 来自其他电脑，不能直接使用"
                : current?.configured
                ? `Key：${current.api_key_masked}`
                : "保存后，指标提取任务将自动使用该 Key"}
            </span>
            {current?.configured && !current.needs_reconfigure && (
              <span className="settings-url">接口地址：{current.base_url}</span>
            )}
          </div>
          {current?.configured && <CheckCircle2 className="settings-ok" size={20} />}
        </div>

        <div className="settings-form">
          <label>
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder={
                current?.needs_reconfigure
                  ? "请输入你自己的 API Key"
                  : current?.configured
                    ? "留空表示继续使用已保存的 Key"
                    : "请输入 API Key"
              }
              autoComplete="off"
            />
          </label>
          <label>
            LLM 接口地址
            <input
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder={DEFAULT_BASE_URL}
            />
          </label>
        </div>

        <div className="settings-actions">
          <button className="primary-action" onClick={handleSave} disabled={saving}>
            {saving ? <Loader2 className="spin" size={18} /> : <Save size={18} />}
            保存并生效
          </button>
          <button className="ghost-action" onClick={handleTest} disabled={testing}>
            {testing ? <Loader2 className="spin" size={16} /> : <CheckCircle2 size={16} />}
            测试连接
          </button>
        </div>

        {message && (
          <div className={message.ok ? "success-banner" : "error-banner"}>
            {message.ok ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
            <span>{message.text}</span>
          </div>
        )}

        <p className="settings-hint">
          <ShieldCheck size={16} />
          <span>
            Key 仅保存在本机 <code>data/llm_settings.json</code>，不会显示在网页上；
            执行指标提取时由后端读取并传给 Agent。
          </span>
        </p>
      </section>
    </section>
  );
}
