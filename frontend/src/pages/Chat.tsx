import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { Bot, Loader2, Send, User } from "lucide-react";
import { api, ChatResponse } from "../api/request";

const SUGGESTIONS = [
  "2025年人保财险的业务结构有什么变化？",
  "2024年中国太保综合成本率是多少？",
  "中国太保盈利能力如何？",
  "中国太保偿付能力充足率是多少？"
];

function renderInline(text: string): ReactNode[] {
  return text.split(/\*\*(.+?)\*\*/g).map((part, index) =>
    index % 2 === 1 ? <strong key={index}>{part}</strong> : part
  );
}

function renderContent(content: string): ReactNode[] {
  const blocks: ReactNode[] = [];
  const lines = content.split("\n");
  let listItems: string[] = [];
  let listIndex = 0;
  let blockIndex = 0;

  const flushList = () => {
    if (listItems.length === 0) return;
    const items = listItems;
    listItems = [];
    blocks.push(
      <ul key={`list-${listIndex++}`}>
        {items.map((item, index) => (
          <li key={index}>{renderInline(item)}</li>
        ))}
      </ul>
    );
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }
    const bullet = line.match(/^[-*•]\s+(.+)$/);
    if (bullet) {
      listItems.push(bullet[1]);
      continue;
    }
    const numbered = line.match(/^(\d+)[.、]\s*(.+)$/);
    if (numbered) {
      flushList();
      blocks.push(
        <p className="chat-line" key={`line-${blockIndex++}`}>
          <strong>{numbered[1]}.</strong> {renderInline(numbered[2])}
        </p>
      );
      continue;
    }
    flushList();
    blocks.push(
      <p className="chat-line" key={`line-${blockIndex++}`}>
        {renderInline(line)}
      </p>
    );
  }
  flushList();
  return blocks;
}

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: ChatResponse["source"];
};

export function Chat({ active = true }: { active?: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const submit = (text?: string) => {
    const content = (text ?? question).trim();
    if (!content || loading) return;
    setMessages((current) => [...current, { role: "user", content }]);
    setQuestion("");
    setLoading(true);
    setError(null);
    api
      .chat(content)
      .then((response) => {
        setMessages((current) => [
          ...current,
          { role: "assistant", content: response.answer, sources: response.source }
        ]);
      })
      .catch(() => {
        setError("问答服务暂不可用，请稍后重试。");
      })
      .finally(() => setLoading(false));
  };

  const onFormSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  return (
    <section
      className="page chat-page"
      style={active ? undefined : { display: "none" }}
    >
      <header>
        <p>智能问答</p>
        <h1>上市财险年报智能问答助手</h1>
      </header>

      <div className="chat-shell">
        <div className="chat-list">
          {messages.length === 0 && (
            <div className="chat-empty">
              <Bot size={34} />
              <p>输入业务问题，Agent 将从结构化指标库中检索数据并回答。</p>
              <div className="suggestion-row">
                {SUGGESTIONS.map((suggestion) => (
                  <button key={suggestion} onClick={() => submit(suggestion)}>
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={index} className={`chat-message ${message.role}`}>
              <div className="chat-avatar">
                {message.role === "user" ? <User size={16} /> : <Bot size={16} />}
              </div>
              <div className="chat-bubble">
                {renderContent(message.content)}
                {message.sources && message.sources.length > 0 && (
                  <details className="chat-sources">
                    <summary>查看数据来源（{message.sources.length}）</summary>
                    <ul>
                      {message.sources.map((source, sourceIndex) => (
                        <li key={`${source.company}-${source.indicator}-${sourceIndex}`}>
                          {source.company} {source.year ?? ""}年 {source.indicator}：{" "}
                          {source.value === null
                            ? "暂无数据"
                            : `${source.value}${source.unit ?? ""}`}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-message assistant">
              <div className="chat-avatar">
                <Bot size={16} />
              </div>
              <div className="chat-bubble">
                <Loader2 className="spin" size={18} />
                <span className="muted">正在检索指标库并生成回答...</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form className="chat-input-row" onSubmit={onFormSubmit}>
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="例如：中国太保综合成本率是多少？"
            rows={2}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
          />
          <button type="submit" disabled={loading || !question.trim()}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </section>
  );
}
