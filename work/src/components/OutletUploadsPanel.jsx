import { useCallback, useEffect, useState } from "react";
import {
  fetchOutletPhotoUploads,
  setOutletPhotoUploadTransferred,
} from "../api.js";

const FILTERS = [
  { value: "pending", label: "К переносу" },
  { value: "transferred", label: "Перенесённые" },
  { value: "all", label: "Все" },
];

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return String(iso);
  }
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
    const text = row.article || row.code || "";
    if (!text) return;
    const ok = await copyText(text);
    if (ok) {
      setCopiedId(row.id);
      window.setTimeout(() => setCopiedId((cur) => (cur === row.id ? null : cur)), 1500);
    } else {
      setErr("Не удалось скопировать");
    }
  }

  return (
    <section className="outlet-uploads">
      <div className="outlet-card">
        <div className="outlet-uploads__title">Очередь переноса</div>
        <p className="muted small" style={{ marginTop: 4, marginBottom: "0.75rem" }}>
          В МойСклад → аутлет и цену → отметьте «Перенесено».
        </p>

        <div className="outlet-uploads__filters">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={filter === f.value ? undefined : "secondary"}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
              {filter === f.value && !loading ? ` (${total})` : ""}
            </button>
          ))}
        </div>

        {err ? <p className="error">{err}</p> : null}

        {loading && !items.length ? (
          <p className="muted">Загрузка…</p>
        ) : !items.length ? (
          <p className="muted">
            {filter === "pending" ? "Нет позиций к переносу." : "Список пуст."}
          </p>
        ) : (
          <ul className="outlet-uploads__list">
            {items.map((row) => {
              const article = row.article || row.code || "";
              return (
                <li key={row.id} className="outlet-uploads__item">
                  <div className="outlet-uploads__meta">
                    <span>{fmtDate(row.created_at)}</span>
                    <span className="muted">·</span>
                    <span>{row.uploaded_by_label || "—"}</span>
                  </div>
                  <div className="outlet-uploads__name">{row.product_name || "—"}</div>
                  <div className="outlet-uploads__article-row">
                    <code>{article || "—"}</code>
                    {article ? (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => onCopyArticle(row)}
                      >
                        {copiedId === row.id ? "Скопировано" : "Копировать"}
                      </button>
                    ) : null}
                  </div>
                  <div className="outlet-uploads__switch-row">
                    <span>Перенесено</span>
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
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </section>
  );
}
