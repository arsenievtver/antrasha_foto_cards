import { useCallback, useEffect, useState } from "react";
import {
  fetchOutletPhotoUploads,
  setOutletPhotoUploadTransferred,
} from "../api.js";

const FILTERS = [
  { value: "pending", label: "Не перенесённые" },
  { value: "transferred", label: "Перенесённые" },
  { value: "all", label: "Все" },
];

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return String(iso);
  }
}

function genderLabel(g) {
  if (g === "female") return "жен";
  if (g === "male") return "муж";
  return "—";
}

async function copyText(text) {
  if (!text) return false;
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

export default function OutletUploadsPanel({ refreshKey = 0 }) {
  const [filter, setFilter] = useState("pending");
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [copiedId, setCopiedId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const data = await fetchOutletPhotoUploads({ filter, limit: 100 });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function onToggle(row) {
    const next = !row.transferred;
    setBusyId(row.id);
    setErr("");
    try {
      const updated = await setOutletPhotoUploadTransferred(row.id, next);
      if (filter === "pending" && next) {
        setItems((prev) => prev.filter((x) => x.id !== row.id));
        setTotal((t) => Math.max(0, t - 1));
      } else if (filter === "transferred" && !next) {
        setItems((prev) => prev.filter((x) => x.id !== row.id));
        setTotal((t) => Math.max(0, t - 1));
      } else {
        setItems((prev) => prev.map((x) => (x.id === row.id ? { ...x, ...updated } : x)));
      }
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function onCopyArticle(row) {
    const text = (row.article || "").trim();
    if (!text) {
      setErr("У позиции нет артикула в МойСклад");
      return;
    }
    const ok = await copyText(text);
    if (ok) {
      setCopiedId(row.id);
      window.setTimeout(() => setCopiedId((cur) => (cur === row.id ? null : cur)), 1500);
    } else {
      setErr("Не удалось скопировать артикул");
    }
  }

  return (
    <section className="outlet-uploads">
      <h2 style={{ marginTop: 0, marginBottom: "0.35rem" }}>Аутлет: перенос</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "0.85rem", maxWidth: 720 }}>
        Отфотканные модели. Перенесите позицию в раздел аутлета в МойСклад, снизьте цену и отметьте
        «Перенесено». Кнопка копирует именно артикул (не код МС и не штрихкод).
      </p>

      <div className="flex-gap" style={{ flexWrap: "wrap", marginBottom: "0.75rem", gap: "0.5rem" }}>
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            className={filter === f.value ? undefined : "secondary"}
            onClick={() => setFilter(f.value)}
            disabled={loading && filter === f.value}
          >
            {f.label}
            {filter === f.value && !loading ? ` (${total})` : ""}
          </button>
        ))}
        <button type="button" className="secondary" onClick={load} disabled={loading}>
          {loading ? "…" : "Обновить"}
        </button>
      </div>

      {err ? <p className="error">{err}</p> : null}

      {loading && !items.length ? (
        <p style={{ color: "var(--muted)" }}>Загрузка…</p>
      ) : !items.length ? (
        <p style={{ color: "var(--muted)" }}>
          {filter === "pending" ? "Нет позиций к переносу." : "Список пуст."}
        </p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Когда</th>
                <th>Сотрудник</th>
                <th>Артикул</th>
                <th>Штрихкод</th>
                <th>Код МС</th>
                <th>Товар</th>
                <th>Пол</th>
                <th>Папка</th>
                <th>Перенесено</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const article = (row.article || "").trim();
                return (
                  <tr key={row.id}>
                    <td style={{ whiteSpace: "nowrap" }}>{fmtDate(row.created_at)}</td>
                    <td>{row.uploaded_by_label || "—"}</td>
                    <td>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <code style={{ fontSize: "0.9rem" }}>{article || "—"}</code>
                        {article ? (
                          <button
                            type="button"
                            className="secondary"
                            style={{ padding: "0.15rem 0.45rem", fontSize: "0.8rem" }}
                            title="Скопировать артикул"
                            onClick={() => onCopyArticle(row)}
                          >
                            {copiedId === row.id ? "✓" : "Копировать"}
                          </button>
                        ) : (
                          <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>
                            нет артикула
                          </span>
                        )}
                      </span>
                    </td>
                    <td>
                      <code style={{ fontSize: "0.85rem" }}>{row.barcode || "—"}</code>
                    </td>
                    <td>
                      <code style={{ fontSize: "0.85rem" }}>{row.code || "—"}</code>
                    </td>
                    <td>{row.product_name || "—"}</td>
                    <td>{genderLabel(row.gender)}</td>
                    <td style={{ maxWidth: 220, fontSize: "0.85rem", color: "var(--muted)" }}>
                      {row.path_name || "—"}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="switch-toggle"
                        role="switch"
                        aria-checked={row.transferred}
                        aria-label="Перенесено"
                        disabled={busyId === row.id}
                        onClick={() => onToggle(row)}
                      >
                        <span className="switch-thumb" aria-hidden />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
