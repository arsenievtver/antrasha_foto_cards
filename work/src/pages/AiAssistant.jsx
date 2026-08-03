import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  fetchWarehouseAiPresets,
  fetchWarehouseAiStatus,
  postWarehouseAiChat,
} from "../api.js";

function MessageBubble({ role, content, meta }) {
  const isUser = role === "user";
  return (
    <div className={`wh-ai-msg ${isUser ? "wh-ai-msg--user" : "wh-ai-msg--bot"}`}>
      <div className="wh-ai-msg__role">{isUser ? "Вы" : "Claude"}</div>
      {isUser ? (
        <div className="wh-ai-msg__body wh-ai-msg__body--plain">{content}</div>
      ) : (
        <div className="wh-ai-msg__body wh-ai-msg__md">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </div>
      )}
      {meta ? <div className="wh-ai-msg__meta muted">{meta}</div> : null}
    </div>
  );
}

export default function AiAssistant() {
  const [status, setStatus] = useState(null);
  const [presets, setPresets] = useState([]);
  const [activePresetId, setActivePresetId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const bottomRef = useRef(null);

  const reloadMeta = useCallback(async () => {
    const [st, pr] = await Promise.all([
      fetchWarehouseAiStatus(),
      fetchWarehouseAiPresets(),
    ]);
    setStatus(st);
    setPresets(pr.items || []);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reloadMeta();
      } catch (e) {
        if (!cancelled) setErr(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadMeta]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  async function sendChat(userText, { presetId = null, displayText = null } = {}) {
    const text = (userText || "").trim();
    if (!text || busy) return;
    setErr("");
    const visible = (displayText || text).trim();
    const userMsg = {
      role: "user",
      content: text,
      display: visible,
    };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    try {
      const payload = nextMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const data = await postWarehouseAiChat({
        messages: payload,
        preset_id: presetId || undefined,
      });
      const tools =
        data.tools_used?.length > 0 ? `tools: ${data.tools_used.join(", ")}` : null;
      const usage =
        data.usage?.input_tokens != null
          ? `tokens ${data.usage.input_tokens}/${data.usage.output_tokens ?? "—"}`
          : null;
      const meta = [data.model, tools, usage].filter(Boolean).join(" · ");
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, display: data.reply, meta },
      ]);
    } catch (ex) {
      setErr(ex.message);
      setMessages((prev) => prev.slice(0, -1));
      if (!presetId) setInput(visible);
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(e) {
    e.preventDefault();
    sendChat(input);
  }

  function onPresetClick(preset) {
    setActivePresetId(preset.id);
    if (busy) return;
    sendChat(preset.prompt, {
      presetId: preset.id,
      displayText: preset.title,
    });
  }

  function clearChat() {
    if (busy) return;
    setMessages([]);
    setErr("");
    setActivePresetId(null);
  }

  if (loading) return <p className="muted">Загрузка…</p>;

  return (
    <div className="wh-ai">
      <div className="wh-ai__toolbar">
        <p className="muted small" style={{ margin: 0, flex: 1 }}>
          Claude + МойСклад. Табы — готовые вопросы.
        </p>
        <button
          type="button"
          className="secondary"
          disabled={busy || !messages.length}
          onClick={clearChat}
        >
          Очистить
        </button>
      </div>

      {err ? <p className="error">{err}</p> : null}

      {!status?.configured ? (
        <div className="outlet-card">
          <p className="error" style={{ margin: 0 }}>
            ИИ не настроен на сервере (ANTHROPIC_API_KEY / MOYSKLAD_MCP_URL).
          </p>
        </div>
      ) : null}

      <div className="wh-ai__presets" role="tablist">
        {presets.map((p) => (
          <button
            key={p.id}
            type="button"
            role="tab"
            className={activePresetId === p.id ? undefined : "secondary"}
            title={p.description}
            disabled={busy || !status?.configured}
            onClick={() => onPresetClick(p)}
          >
            {p.title}
          </button>
        ))}
      </div>

      <section className="outlet-card wh-ai__chat">
        <div className="wh-ai__thread">
          {messages.length === 0 ? (
            <p className="muted" style={{ margin: 0 }}>
              Выберите таб или напишите вопрос про остатки, продажи, заказы.
            </p>
          ) : (
            messages.map((m, i) => (
              <MessageBubble
                key={`${i}-${m.role}`}
                role={m.role}
                content={m.display || m.content}
                meta={m.meta}
              />
            ))
          )}
          {busy ? (
            <div className="wh-ai-msg wh-ai-msg--bot">
              <div className="wh-ai-msg__role">Claude</div>
              <div className="wh-ai-msg__body muted">Думаю и смотрю склад…</div>
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>

        <form className="wh-ai__composer" onSubmit={onSubmit}>
          <textarea
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Свой вопрос…"
            disabled={busy || !status?.configured}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSubmit(e);
              }
            }}
          />
          <button type="submit" disabled={busy || !status?.configured || !input.trim()}>
            {busy ? "…" : "Отправить"}
          </button>
        </form>
      </section>
    </div>
  );
}
