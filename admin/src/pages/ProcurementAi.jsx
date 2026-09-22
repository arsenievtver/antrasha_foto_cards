import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  fetchProcurementAiPresets,
  fetchProcurementAiStatus,
  postProcurementAiChat,
} from "../api.js";
import ChatComposer from "../components/ChatComposer.jsx";
import { eur, kgShort, rub } from "../utils/money.js";

const CHART_COLORS = [
  "#6c9eff",
  "#7fd99a",
  "#e7c27a",
  "#f07178",
  "#c4b5fd",
  "#67e8f9",
  "#fb923c",
  "#f9a8d4",
];

function formatChartValue(value, unit) {
  if (unit === "€") return eur(value);
  if (unit === "₽") return rub(value);
  if (unit === "кг") return kgShort(value);
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
}

function parseChart(raw) {
  try {
    const data = JSON.parse(raw);
    const items = Array.isArray(data?.items) ? data.items : [];
    const parsed = items
      .map((item) => ({
        label: String(item?.label ?? "").trim(),
        value: Number(item?.value),
      }))
      .filter((item) => item.label && Number.isFinite(item.value));
    if (!parsed.length) return null;
    return {
      type: data.type === "donut" ? "donut" : "bar",
      title: String(data.title || "").trim(),
      unit: String(data.unit || ""),
      items: parsed.slice(0, 12),
    };
  } catch {
    return null;
  }
}

function splitReply(text) {
  const parts = [];
  const re = /```chart\s*([\s\S]*?)```/gi;
  let last = 0;
  for (const match of text.matchAll(re)) {
    if (match.index > last) {
      parts.push({ type: "md", text: text.slice(last, match.index) });
    }
    parts.push({ type: "chart", raw: match[1] });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ type: "md", text: text.slice(last) });
  if (!parts.length) parts.push({ type: "md", text });
  return parts;
}

function BarChart({ chart }) {
  const max = Math.max(...chart.items.map((item) => Math.abs(item.value)), 0);
  return (
    <div className="pai-chart">
      {chart.title ? <div className="pai-chart__title">{chart.title}</div> : null}
      {chart.items.map((item, index) => {
        const width = max > 0 ? Math.max(2, (Math.abs(item.value) / max) * 100) : 0;
        return (
          <div className="pai-bar" key={`${item.label}-${index}`}>
            <div className="pai-bar__label" title={item.label}>
              {item.label}
            </div>
            <div className="pai-bar__track">
              <div
                className="pai-bar__fill"
                style={{
                  width: `${width}%`,
                  background: CHART_COLORS[index % CHART_COLORS.length],
                }}
              />
            </div>
            <div className="pai-bar__value">{formatChartValue(item.value, chart.unit)}</div>
          </div>
        );
      })}
    </div>
  );
}

function DonutChart({ chart }) {
  const total = chart.items.reduce((sum, item) => sum + Math.max(item.value, 0), 0);
  const size = 148;
  const stroke = 22;
  const radius = (size - stroke) / 2;
  const circ = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <div className="pai-chart pai-chart--donut">
      {chart.title ? <div className="pai-chart__title">{chart.title}</div> : null}
      <div className="pai-donut">
        <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden>
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#2a2f3a"
            strokeWidth={stroke}
          />
          {total > 0
            ? chart.items.map((item, index) => {
                const len = (Math.max(item.value, 0) / total) * circ;
                const el = (
                  <circle
                    key={`${item.label}-${index}`}
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={CHART_COLORS[index % CHART_COLORS.length]}
                    strokeWidth={stroke}
                    strokeDasharray={`${len} ${circ - len}`}
                    strokeDashoffset={-offset}
                    transform={`rotate(-90 ${size / 2} ${size / 2})`}
                  />
                );
                offset += len;
                return el;
              })
            : null}
        </svg>
        <ul className="pai-donut__legend">
          {chart.items.map((item, index) => (
            <li key={`${item.label}-${index}`}>
              <span
                className="pai-donut__swatch"
                style={{ background: CHART_COLORS[index % CHART_COLORS.length] }}
              />
              <span>{item.label}</span>
              <strong>{formatChartValue(item.value, chart.unit)}</strong>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ReplyBody({ content }) {
  return splitReply(content || "").map((part, index) => {
    if (part.type === "chart") {
      const chart = parseChart(part.raw);
      if (!chart) {
        return (
          <pre key={index} className="pai-chart__raw">
            {part.raw}
          </pre>
        );
      }
      return chart.type === "donut" ? (
        <DonutChart key={index} chart={chart} />
      ) : (
        <BarChart key={index} chart={chart} />
      );
    }
    if (!part.text.trim()) return null;
    return (
      <div key={index} className="wh-ai-msg__md">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{part.text}</ReactMarkdown>
      </div>
    );
  });
}

function MessageBubble({ role, content, meta }) {
  const isUser = role === "user";
  return (
    <div className={`wh-ai-msg ${isUser ? "wh-ai-msg--user" : "wh-ai-msg--bot"}`}>
      <div className="wh-ai-msg__role">{isUser ? "Вы" : "Закупки"}</div>
      {isUser ? (
        <div className="wh-ai-msg__body wh-ai-msg__body--plain">{content}</div>
      ) : (
        <div className="wh-ai-msg__body">
          <ReplyBody content={content} />
        </div>
      )}
      {meta ? <div className="wh-ai-msg__meta muted">{meta}</div> : null}
    </div>
  );
}

export default function ProcurementAi() {
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
      fetchProcurementAiStatus(),
      fetchProcurementAiPresets(),
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

  async function sendChat(userText, { displayText = null, presetId = null } = {}) {
    const text = (userText || "").trim();
    if (!text || busy) return;
    setErr("");
    const visible = (displayText || text).trim();
    const userMsg = { role: "user", content: text, display: visible };
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput("");
    setActivePresetId(presetId);
    setBusy(true);
    try {
      const data = await postProcurementAiChat({
        messages: nextMessages.map((m) => ({ role: m.role, content: m.content })),
      });
      const ops = data.tools_used?.length ? `tools: ${data.tools_used.join(", ")}` : null;
      const usage =
        data.usage?.input_tokens != null
          ? `tokens in/out: ${data.usage.input_tokens}/${data.usage.output_tokens ?? "—"}`
          : null;
      const access = data.can_write ? "ключ: запись" : "ключ: чтение";
      const meta = [data.model, access, ops, usage].filter(Boolean).join(" · ");
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

  function clearChat() {
    if (busy) return;
    setMessages([]);
    setErr("");
    setActivePresetId(null);
  }

  if (loading) return <p>Загрузка…</p>;

  const accessText = status?.can_write
    ? "Ключ с правом записи: агент может создавать и менять записи. Перед записью он спросит недостающие поля. Удалять не может."
    : status?.key_present
      ? "Ключ только на чтение: агент смотрит данные и строит сводки, но не записывает."
      : "Ключ MCP не выпущен: агент только читает. Чтобы он мог записывать, выпустите ключ с галочкой на странице «Ключ MCP».";

  return (
    <div className="wh-ai">
      <div className="wh-ai__header">
        <div>
          <h1>AI закупки</h1>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>
            Отдельный агент сезонов, брендов, заказов, оплат, поставок и курса EUR.
            Склад и МойСклад он не видит.
          </p>
        </div>
        <button type="button" className="secondary" disabled={busy || !messages.length} onClick={clearChat}>
          Очистить чат
        </button>
      </div>

      {err ? (
        <p className="error" style={{ marginTop: "1rem" }}>
          {err}
        </p>
      ) : null}

      <section className="card" style={{ marginTop: "1.25rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1.05rem" }}>Доступ</h2>
        {!status?.configured ? (
          <p className="error" style={{ marginBottom: 0 }}>
            Не настроено. Нужен <code>ANTHROPIC_API_KEY</code>.
          </p>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            {accessText} Инструментов: {status.tools_count}. Модель: {status.model || "—"}.{" "}
            <Link to="/mcp-key">Ключ MCP</Link>
          </p>
        )}
      </section>

      <section style={{ marginTop: "1.25rem" }}>
        <div className="tabs wh-ai__presets" role="tablist">
          {presets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              role="tab"
              className={activePresetId === preset.id ? "active" : ""}
              title={preset.description}
              disabled={busy || !status?.configured}
              onClick={() =>
                sendChat(preset.prompt, { displayText: preset.title, presetId: preset.id })
              }
            >
              {preset.title}
            </button>
          ))}
        </div>
      </section>

      <section className="card wh-ai__chat" style={{ marginTop: "1rem" }}>
        {messages.length === 0 && !busy ? (
          <p className="muted" style={{ margin: 0 }}>
            Спросите про поставки, остаток, предоплату или курс. Если данных для записи
            не хватит, агент сначала уточнит их.
          </p>
        ) : null}

        <ChatComposer
          value={input}
          onChange={setInput}
          onSubmit={onSubmit}
          disabled={busy || !status?.configured}
          busy={busy}
          placeholder="Например: что с поставками на осень-зиму 2026/2027?"
        />

        {messages.length > 0 || busy ? (
          <div className="wh-ai__thread">
            {messages.map((message, index) => (
              <MessageBubble
                key={`${index}-${message.role}`}
                role={message.role}
                content={message.display || message.content}
                meta={message.meta}
              />
            ))}
            {busy ? (
              <div className="wh-ai-msg wh-ai-msg--bot">
                <div className="wh-ai-msg__role">Закупки</div>
                <div className="wh-ai-msg__body muted">Смотрю закупки…</div>
              </div>
            ) : null}
            <div ref={bottomRef} />
          </div>
        ) : null}
      </section>
    </div>
  );
}
