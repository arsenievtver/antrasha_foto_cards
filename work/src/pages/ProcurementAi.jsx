import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  fetchProcurementAiPresets,
  fetchProcurementAiStatus,
  postProcurementAiChat,
} from "../api.js";
import { eur, kg, rub } from "../utils/money.js";

const CHART_COLORS = [
  "#c4a574",
  "#7dbe9a",
  "#e8a87c",
  "#e07a7a",
  "#9bb7d4",
  "#d4b4e0",
];

function formatChartValue(value, unit) {
  if (unit === "€") return eur(value);
  if (unit === "₽") return rub(value);
  if (unit === "кг") return kg(value);
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
  const size = 132;
  const stroke = 18;
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
            stroke="#343a44"
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

function Composer({ value, onChange, onSubmit, disabled, busy }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    function fit() {
      const probe = el.cloneNode(false);
      probe.value = el.value || el.placeholder || "";
      probe.rows = 1;
      probe.style.position = "absolute";
      probe.style.visibility = "hidden";
      probe.style.height = "auto";
      probe.style.maxHeight = "none";
      probe.style.width = `${el.offsetWidth}px`;
      probe.style.overflow = "hidden";
      el.parentElement?.appendChild(probe);
      el.style.height = `${probe.scrollHeight}px`;
      probe.remove();
    }

    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [value]);

  return (
    <form className="wh-ai__composer" onSubmit={onSubmit}>
      <textarea
        ref={ref}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Например: что с поставками на осень-зиму 2026/2027?"
        disabled={disabled}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit(e);
          }
        }}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        {busy ? "…" : "Отправить"}
      </button>
    </form>
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

  const ready = Boolean(status?.configured && status?.key_present);

  async function sendChat(userText, { displayText = null, presetId = null } = {}) {
    const text = (userText || "").trim();
    if (!text || busy || !ready) return;
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
      const tools = data.tools_used?.length ? data.tools_used.join(", ") : null;
      const access = data.can_write ? "запись" : "чтение";
      const meta = [access, tools].filter(Boolean).join(" · ");
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

  if (loading) return <p className="muted">Загрузка…</p>;

  return (
    <div className="wh-ai wh-ai--procurement">
      <div className="wh-ai__toolbar">
        <p className="muted small" style={{ margin: 0, flex: 1 }}>
          Сезоны, бренды, заказы, оплаты, поставки и курс. Склад этот агент не видит.
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
            Агент не настроен на сервере.
          </p>
        </div>
      ) : !status?.key_present ? (
        <div className="outlet-card">
          <p className="error" style={{ margin: 0 }}>
            Ключ не установлен. Чтобы агент заработал, выпустите ключ в админке на странице
            «Ключ MCP».
          </p>
        </div>
      ) : (
        <>
          {!status.can_write ? (
            <p className="muted small" style={{ margin: 0 }}>
              Ключ только на чтение: агент смотрит данные и строит сводки, но не записывает.
            </p>
          ) : null}

          <div className="wh-ai__presets" role="tablist">
            {presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                role="tab"
                className={activePresetId === preset.id ? undefined : "secondary"}
                title={preset.description}
                disabled={busy}
                onClick={() =>
                  sendChat(preset.prompt, { displayText: preset.title, presetId: preset.id })
                }
              >
                {preset.title}
              </button>
            ))}
          </div>

          <section className="outlet-card wh-ai__chat">
            {messages.length === 0 && !busy ? (
              <p className="muted" style={{ margin: 0 }}>
                Спросите про поставки, остаток, предоплату или курс. Если данных для записи не
                хватит, агент сначала уточнит их.
              </p>
            ) : null}

            <Composer
              value={input}
              onChange={setInput}
              onSubmit={onSubmit}
              disabled={busy}
              busy={busy}
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
        </>
      )}
    </div>
  );
}
