import { useCallback, useEffect, useState } from "react";
import { fetchStaffFeedback, fetchStaffFeedbackStats } from "../api.js";

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
    lines.push(`## ${fmtDate(row.created_at)} — ${row.author_label}`, "", row.text, "");
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

export default function StaffFeedback() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [author, setAuthor] = useState("");
  const [stats, setStats] = useState([]);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    const period = { date_from: dateFrom, date_to: dateTo };
    try {
      const [st, list] = await Promise.all([
        fetchStaffFeedbackStats(period),
        fetchStaffFeedback({ ...period, author_user_id: author, limit: LIMIT }),
      ]);
      setStats(st.items || []);
      setItems(list.items || []);
      setTotal(list.total || 0);
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

  return (
    <section>
      <h2 style={{ marginTop: 0, marginBottom: "0.35rem" }}>Спрос от продавцов</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "0.85rem", maxWidth: 720 }}>
        Сообщения из раздела «Спрос» в рабочем PWA. Те же данные читает MCP закупок:
        list_staff_feedback и get_staff_feedback_stats.
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
      </div>

      {err ? <p className="error">{err}</p> : null}

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
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Когда</th>
                <th>Сотрудник</th>
                <th>Текст</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id}>
                  <td style={{ whiteSpace: "nowrap", verticalAlign: "top" }}>
                    {fmtDate(row.created_at)}
                    {row.updated_at ? (
                      <div style={{ fontSize: "0.8rem", color: "var(--muted)" }}>изменено</div>
                    ) : null}
                  </td>
                  <td style={{ verticalAlign: "top" }}>{row.author_label}</td>
                  <td style={{ whiteSpace: "pre-wrap", maxWidth: 640 }}>{row.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
