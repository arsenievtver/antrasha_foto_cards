import { useEffect, useState } from "react";
import { fetchFittingRequests } from "../api.js";
import { useHoverPreview } from "../utils/usePhotoHover.jsx";

function fmtPct(rate) {
  const n = Number(rate) || 0;
  return `${Math.round(n * 100)}%`;
}

export default function FittingRequests() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const photoHover = useHoverPreview();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setErr("");
      setLoading(true);
      try {
        const data = await fetchFittingRequests({ skip: 0, limit: 100 });
        if (cancelled) return;
        setItems(data.items || []);
        setTotal(data.total ?? 0);
      } catch (e) {
        if (!cancelled) setErr(e.message || String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <p className="muted">Загрузка…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Заявки на примерку</h2>
      <p className="muted">Всего заявок: {total}</p>
      {err ? <p className="error">{err}</p> : null}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Дата</th>
              <th>Клиент</th>
              <th>Телефон</th>
              <th>Совпадение</th>
              <th>Лайки</th>
              <th>Понравившиеся фото</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString("ru-RU")}</td>
                <td>{row.display_name || "—"}</td>
                <td>{row.phone}</td>
                <td>{fmtPct(row.match_rate)}</td>
                <td>
                  {row.likes} / {row.total}
                </td>
                <td style={{ minWidth: 180 }}>
                  {Array.isArray(row.liked_photos) && row.liked_photos.length > 0 ? (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem" }}>
                      {row.liked_photos.map((url, idx) => (
                        <a
                          key={`${row.id}-${idx}`}
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          title="Открыть фото"
                          {...photoHover.hoverProps(url)}
                        >
                          <img
                            src={url}
                            alt=""
                            loading="lazy"
                            style={{
                              width: 44,
                              height: 44,
                              objectFit: "cover",
                              borderRadius: 6,
                              border: "1px solid var(--border)",
                            }}
                          />
                        </a>
                      ))}
                    </div>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>{row.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {photoHover.overlay}
    </div>
  );
}
