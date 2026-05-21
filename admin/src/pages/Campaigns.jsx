import { useCallback, useEffect, useState } from "react";
import QRCode from "qrcode";
import { createCampaign, fetchCampaigns } from "../api.js";

function QrPreview({ url }) {
  const [src, setSrc] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!url) {
      setSrc("");
      return undefined;
    }
    QRCode.toDataURL(url, { width: 200, margin: 1 })
      .then((dataUrl) => {
        if (!cancelled) setSrc(dataUrl);
      })
      .catch(() => {
        if (!cancelled) setSrc("");
      });
    return () => {
      cancelled = true;
    };
  }, [url]);

  if (!src) return null;
  return (
    <img
      src={src}
      alt="QR-код ссылки"
      width={200}
      height={200}
      style={{ display: "block", marginTop: "0.75rem", borderRadius: 8 }}
    />
  );
}

export default function Campaigns() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [path, setPath] = useState("/");
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [copiedId, setCopiedId] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const res = await fetchCampaigns();
      setData(res);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const created = await createCampaign({
        name: name.trim(),
        slug: slug.trim() || undefined,
        path: path.trim() || "/",
      });
      setPreviewUrl(created.tracking_url);
      setName("");
      setSlug("");
      setPath("/");
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function copyUrl(url, id) {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(id);
      setTimeout(() => setCopiedId(""), 2000);
    } catch {
      setErr("Не удалось скопировать в буфер");
    }
  }

  if (loading && !data) {
    return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Рекламные ссылки</h2>
      <p style={{ color: "var(--muted)", maxWidth: 640 }}>
        Каждая ссылка добавляет параметр <code>?ref=slug</code>. При первом заходе
        гостя ref привязывается к сессии и учитывается в статистике.
        {data?.public_app_url ? (
          <>
            {" "}
            Базовый URL: <strong>{data.public_app_url}</strong> (задаётся{" "}
            <code>PUBLIC_APP_URL</code> на бэкенде).
          </>
        ) : null}
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ maxWidth: 520, marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новая кампания</h3>
        <form className="form-stack" onSubmit={onCreate}>
          <label>
            Название
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="VK май 2026"
              required
            />
          </label>
          <label>
            Slug (ref), необязательно
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="vk_may26 — из названия, если пусто"
            />
          </label>
          <label>
            Путь на сайте
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/ или /swipe/female"
            />
          </label>
          <button type="submit" disabled={busy || !name.trim()}>
            {busy ? "Создание…" : "Создать ссылку"}
          </button>
        </form>
        {previewUrl ? (
          <div style={{ marginTop: "1.25rem", paddingTop: "1rem", borderTop: "1px solid var(--border)" }}>
            <div style={{ fontSize: "0.85rem", color: "var(--muted)" }}>Последняя созданная ссылка</div>
            <a href={previewUrl} target="_blank" rel="noreferrer">
              {previewUrl}
            </a>
            <QrPreview url={previewUrl} />
          </div>
        ) : null}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Кампании</h3>
        {!data?.items?.length ? (
          <p style={{ color: "var(--muted)" }}>Пока нет кампаний.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>ref</th>
                <th>Заходы</th>
                <th>Ссылка / QR</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>
                    <code>{row.slug}</code>
                  </td>
                  <td>{row.visits}</td>
                  <td>
                    <div className="campaign-link-cell">
                      <a href={row.tracking_url} target="_blank" rel="noreferrer">
                        {row.tracking_url}
                      </a>
                      <button
                        type="button"
                        className="secondary"
                        style={{ marginTop: "0.35rem" }}
                        onClick={() => copyUrl(row.tracking_url, row.id)}
                      >
                        {copiedId === row.id ? "Скопировано" : "Копировать"}
                      </button>
                      <details style={{ marginTop: "0.5rem" }}>
                        <summary>QR-код</summary>
                        <QrPreview url={row.tracking_url} />
                      </details>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
