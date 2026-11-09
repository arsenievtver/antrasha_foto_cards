import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  bindStaffFeedbackClient,
  fetchAClients,
  fetchStaffFeedback,
  fetchStaffFeedbackStats,
  mergeStaffFeedback,
  splitStaffFeedback,
} from "../api.js";

const LIMIT = 500;

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return String(iso);
  }
}

function authorKey(row) {
  return row.author_user_id || `label:${row.author_label}`;
}

function toMarkdown(items, { dateFrom, dateTo }) {
  const period = dateFrom || dateTo ? ` (${dateFrom || "…"} — ${dateTo || "…"})` : "";
  const lines = [`# Спрос от продавцов${period}`, ""];
  for (const row of [...items].reverse()) {
    const who = row.client_name ? `${row.author_label} → ${row.client_name}` : row.author_label;
    lines.push(`## ${fmtDate(row.created_at)} — ${who}`, "", row.text, "");
  }
  return lines.join("\n");
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function groupItems(items) {
  const groups = [];
  const seen = new Map();
  for (const row of items) {
    const key = row.thread_id || row.id;
    if (!seen.has(key)) {
      const group = { key, thread_id: row.thread_id, rows: [] };
      seen.set(key, group);
      groups.push(group);
    }
    seen.get(key).rows.push(row);
  }
  for (const group of groups) {
    group.rows.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
  }
  return groups;
}

export default function StaffFeedback() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [author, setAuthor] = useState("");
  const [stats, setStats] = useState([]);
  const [items, setItems] = useState([]);
  const [clients, setClients] = useState([]);
  const [total, setTotal] = useState(0);
  const [picked, setPicked] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    const period = { date_from: dateFrom, date_to: dateTo };
    try {
      const [st, list, people] = await Promise.all([
        fetchStaffFeedbackStats(period),
        fetchStaffFeedback({ ...period, author_user_id: author, limit: LIMIT }),
        fetchAClients({}),
      ]);
      setStats(st.items || []);
      setItems(list.items || []);
      setTotal(list.total || 0);
      setClients(people.items || []);
      setPicked([]);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, author]);

  useEffect(() => {
    load();
  }, [load]);

  const authors = stats.filter((s) => s.author_user_id);
  const groups = useMemo(() => groupItems(items), [items]);
  const pickedRows = items.filter((row) => picked.includes(row.id));
  const sameAuthor = pickedRows.length >= 2 && new Set(pickedRows.map(authorKey)).size === 1;

  function toggle(id) {
    setPicked((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  }

  async function onMerge() {
    setErr("");
    try {
      await mergeStaffFeedback(picked);
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onSplit(threadId) {
    setErr("");
    try {
      await splitStaffFeedback(threadId);
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onBind(row, clientId) {
    setErr("");
    try {
      await bindStaffFeedbackClient(row.id, clientId || null);
      await load();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <section>
      <h2 style={{ marginTop: 0, marginBottom: "0.35rem" }}>Спрос от продавцов</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "0.85rem", maxWidth: 720 }}>
        Сообщения из раздела «Спрос» в рабочем PWA. Если одну мысль разбили на несколько сообщений,
        их можно склеить — тогда текст читается целиком. Привязка к клиенту А живёт в{" "}
        <Link to="/a-clients">«Клиентах А»</Link>.
      </p>

      <div className="flex-gap" style={{ flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <label>
          С{" "}
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          По <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <select value={author} onChange={(e) => setAuthor(e.target.value)}>
          <option value="">Все сотрудники</option>
          {authors.map((s) => (
            <option key={s.author_user_id} value={s.author_user_id}>
              {s.author_label}
            </option>
          ))}
        </select>
        <button type="button" className="secondary" onClick={load} disabled={loading}>
          {loading ? "…" : "Обновить"}
        </button>
        <button
          type="button"
          className="secondary"
          disabled={!items.length}
          onClick={() =>
            downloadText(
              `demand-${dateFrom || "all"}-${dateTo || "now"}.md`,
              toMarkdown(items, { dateFrom, dateTo }),
            )
          }
        >
          Скачать .md
        </button>
        <button type="button" disabled={!sameAuthor} onClick={onMerge}>
          Объединить выбранные
        </button>
      </div>

      {err ? <p className="error">{err}</p> : null}
      {picked.length && !sameAuthor ? (
        <p style={{ color: "var(--muted)" }}>Для склейки отметьте два или больше сообщений одного сотрудника.</p>
      ) : null}

      <h3>Активность</h3>
      {!stats.length ? (
        <p style={{ color: "var(--muted)" }}>{loading ? "Загрузка…" : "Сообщений нет."}</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: "1.25rem" }}>
          <table>
            <thead>
              <tr>
                <th>Сотрудник</th>
                <th>Сообщений</th>
                <th>Дней с сообщениями</th>
                <th>Символов</th>
                <th>Последнее</th>
              </tr>
            </thead>
            <tbody>
              {stats.map((s) => (
                <tr key={authorKey(s)}>
                  <td>{s.author_label}</td>
                  <td>{s.messages}</td>
                  <td>{s.active_days}</td>
                  <td>{s.total_chars}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{fmtDate(s.last_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>
        Сообщения{total ? ` (${total}${total > items.length ? `, показаны ${items.length}` : ""})` : ""}
      </h3>
      {!items.length ? (
        <p style={{ color: "var(--muted)" }}>{loading ? "Загрузка…" : "Список пуст."}</p>
      ) : (
        <div style={{ display: "grid", gap: "0.75rem" }}>
          {groups.map((group) => {
            const head = group.rows[0];
            const merged = group.rows.length > 1;
            return (
              <article
                key={group.key}
                style={{
                  borderLeft: merged ? "3px solid var(--accent, #888)" : "3px solid transparent",
                  paddingLeft: "0.75rem",
                }}
              >
                <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "center" }}>
                  <strong>{head.author_label}</strong>
                  <span style={{ color: "var(--muted)" }}>{fmtDate(head.created_at)}</span>
                  {merged ? <span>одна мысль, склеено {group.rows.length}</span> : null}
                  {merged ? (
                    <button type="button" className="secondary" onClick={() => onSplit(group.thread_id)}>
                      Разделить
                    </button>
                  ) : null}
                  <select
                    value={head.client_id || ""}
                    onChange={(e) => onBind(head, e.target.value)}
                    style={{ marginLeft: "auto", maxWidth: 320 }}
                  >
                    <option value="">Клиент не выбран</option>
                    {clients.map((client) => (
                      <option key={client.id} value={client.id}>
                        {client.name}
                      </option>
                    ))}
                  </select>
                </div>
                {group.rows.map((row) => (
                  <label key={row.id} style={{ display: "flex", gap: "0.5rem", marginTop: "0.45rem" }}>
                    <input
                      type="checkbox"
                      checked={picked.includes(row.id)}
                      onChange={() => toggle(row.id)}
                    />
                    <span style={{ whiteSpace: "pre-wrap" }}>
                      {row.text}
                      {row.updated_at ? (
                        <span style={{ color: "var(--muted)" }}> · изменено</span>
                      ) : null}
                    </span>
                  </label>
                ))}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
