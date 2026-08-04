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

function genderLabel(g) {
  if (g === "female") return "жен";
  if (g === "male") return "муж";
  return "";
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

function CopyArticleButton({ row, copiedId, onCopy }) {
  const article = (row.article || "").trim();
  if (!article) {
    return <span className="muted">нет артикула</span>;
  }
  return (
    <button
      type="button"
      className="secondary"
      title="Скопировать артикул"
      onClick={() => onCopy(row)}
    >
      {copiedId === row.id ? "Скопировано" : "Копировать"}
    </button>
  );
}

function TransferSwitch({ row, busyId, onToggle }) {
  return (
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
  );
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
      <div className="outlet-card">
        <div className="outlet-uploads__title">Очередь переноса</div>
        <p className="muted small" style={{ marginTop: 4, marginBottom: "0.75rem" }}>
          В МойСклад → аутлет и цену → отметьте «Перенесено». Копируется только артикул.
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
          <button type="button" className="secondary" onClick={load} disabled={loading}>
            {loading ? "…" : "Обновить"}
          </button>
        </div>

        {err ? <p className="error">{err}</p> : null}

        {loading && !items.length ? (
          <p className="muted">Загрузка…</p>
        ) : !items.length ? (
          <p className="muted">
            {filter === "pending" ? "Нет позиций к переносу." : "Список пуст."}
          </p>
        ) : (
          <>
            <ul className="outlet-uploads__list outlet-uploads__list--cards">
              {items.map((row) => {
                const article = (row.article || "").trim();
                const g = genderLabel(row.gender);
                return (
                  <li key={row.id} className="outlet-uploads__item">
                    <div className="outlet-uploads__meta">
                      <span>{fmtDate(row.created_at)}</span>
                      <span className="muted">·</span>
                      <span>{row.uploaded_by_label || "—"}</span>
                      {g ? (
                        <>
                          <span className="muted">·</span>
                          <span>{g}</span>
                        </>
                      ) : null}
                    </div>
                    <div className="outlet-uploads__name">{row.product_name || "—"}</div>
                    <div className="outlet-uploads__fields">
                      <div className="outlet-uploads__field">
                        <span className="muted">Артикул</span>
                        <div className="outlet-uploads__article-row">
                          <code>{article || "—"}</code>
                          <CopyArticleButton
                            row={row}
                            copiedId={copiedId}
                            onCopy={onCopyArticle}
                          />
                        </div>
                      </div>
                      {row.barcode ? (
                        <div className="outlet-uploads__field">
                          <span className="muted">Штрихкод</span>
                          <code>{row.barcode}</code>
                        </div>
                      ) : null}
                      {row.code ? (
                        <div className="outlet-uploads__field">
                          <span className="muted">Код МС</span>
                          <code>{row.code}</code>
                        </div>
                      ) : null}
                      {row.path_name ? (
                        <div className="outlet-uploads__field">
                          <span className="muted">Папка</span>
                          <span className="outlet-uploads__path">{row.path_name}</span>
                        </div>
                      ) : null}
                    </div>
                    <div className="outlet-uploads__switch-row">
                      <span>Перенесено</span>
                      <TransferSwitch row={row} busyId={busyId} onToggle={onToggle} />
                    </div>
                  </li>
                );
              })}
            </ul>

            <div className="outlet-uploads__table-wrap">
              <table className="outlet-uploads__table">
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
                        <td className="nowrap">{fmtDate(row.created_at)}</td>
                        <td>{row.uploaded_by_label || "—"}</td>
                        <td>
                          <div className="outlet-uploads__article-row">
                            <code>{article || "—"}</code>
                            <CopyArticleButton
                              row={row}
                              copiedId={copiedId}
                              onCopy={onCopyArticle}
                            />
                          </div>
                        </td>
                        <td>
                          <code>{row.barcode || "—"}</code>
                        </td>
                        <td>
                          <code>{row.code || "—"}</code>
                        </td>
                        <td>{row.product_name || "—"}</td>
                        <td>{genderLabel(row.gender) || "—"}</td>
                        <td className="outlet-uploads__path-cell">{row.path_name || "—"}</td>
                        <td>
                          <TransferSwitch row={row} busyId={busyId} onToggle={onToggle} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
