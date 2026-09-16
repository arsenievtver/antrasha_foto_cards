import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createCampaign,
  fetchCampaigns,
  fetchXfashionAttributionDebug,
} from "../api.js";
import { isValidSlug, previewSlugFromText } from "../utils/campaignSlug.js";
import {
  downloadQrPng,
  downloadQrPngTransparent,
  downloadQrSvg,
  qrPreviewDataUrl,
} from "../utils/qrDownload.js";

function QrBlock({ url, slug }) {
  const [src, setSrc] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    let cancelled = false;
    if (!url) {
      setSrc("");
      return undefined;
    }
    qrPreviewDataUrl(url, 200)
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

  async function runDownload(fn) {
    if (!url || !slug) return;
    setBusy("…");
    try {
      await fn();
    } finally {
      setBusy("");
    }
  }

  if (!url) return null;
  const fileSlug = slug || "link";

  return (
    <div className="qr-block">
      {src ? (
        <img src={src} alt="QR-код" width={200} height={200} className="qr-block__preview" />
      ) : null}
      <div className="qr-block__actions">
        <button
          type="button"
          className="secondary"
          disabled={!!busy}
          onClick={() => runDownload(() => downloadQrSvg(url, { slug: fileSlug }))}
        >
          SVG
        </button>
        <button
          type="button"
          className="secondary"
          disabled={!!busy}
          onClick={() =>
            runDownload(() => downloadQrPng(url, { slug: fileSlug, sizePx: 2048 }))
          }
        >
          PNG 2048
        </button>
      </div>
    </div>
  );
}

export default function XfashionCampaigns() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [path, setPath] = useState("/");
  const [busy, setBusy] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");
  const [previewSlug, setPreviewSlug] = useState("");
  const [copiedId, setCopiedId] = useState("");
  const [debug, setDebug] = useState(null);
  const [debugErr, setDebugErr] = useState("");
  const [debugBusy, setDebugBusy] = useState(false);

  const slugPreview = useMemo(() => {
    const manual = slug.trim();
    if (manual) return previewSlugFromText(manual);
    return previewSlugFromText(name);
  }, [name, slug]);

  const slugPreviewValid = slugPreview && isValidSlug(slugPreview);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setData(await fetchCampaigns("xfashion"));
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
        product: "xfashion",
      });
      setPreviewUrl(created.tracking_url);
      setPreviewSlug(created.slug);
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

  async function loadDebug() {
    setDebugBusy(true);
    setDebugErr("");
    try {
      setDebug(await fetchXfashionAttributionDebug());
    } catch (e) {
      setDebugErr(e.message);
    } finally {
      setDebugBusy(false);
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
      <h2 style={{ marginTop: 0 }}>Xfashion — рекламные ссылки</h2>
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Ссылки ведут на <strong>xfashion.pro</strong> с <code>?ref=код</code>. Заход
        фиксируется при первом открытии лендинга в вкладке.
        {data?.public_xfashion_url ? (
          <>
            {" "}
            Базовый URL: <code>{data.public_xfashion_url}</code> (
            <code>PUBLIC_XFASHION_URL</code>).
          </>
        ) : null}
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Проверка заходов</h3>
        <button type="button" className="secondary" disabled={debugBusy} onClick={loadDebug}>
          {debugBusy ? "Загрузка…" : "Обновить журнал заходов"}
        </button>
        {debugErr ? <p className="error">{debugErr}</p> : null}
        {debug ? (
          <>
            <p className="field-hint" style={{ marginTop: "0.75rem" }}>
              {debug.hint}
            </p>
            <table style={{ marginTop: "0.75rem" }}>
              <thead>
                <tr>
                  <th>Кампания</th>
                  <th>ref</th>
                  <th>Заходов</th>
                </tr>
              </thead>
              <tbody>
                {debug.campaigns.map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td>
                      <code>{c.slug}</code>
                    </td>
                    <td>{c.visits}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <h4 style={{ margin: "1rem 0 0.5rem", fontSize: "0.9rem" }}>
              Последние заходы
            </h4>
            {!debug.recent_visits?.length ? (
              <p style={{ color: "var(--muted)", margin: 0 }}>Пока нет.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Время</th>
                    <th>ref</th>
                    <th>Кампания</th>
                  </tr>
                </thead>
                <tbody>
                  {debug.recent_visits.map((row) => (
                    <tr key={row.visit_id}>
                      <td>{new Date(row.created_at).toLocaleString("ru-RU")}</td>
                      <td>
                        <code>{row.campaign_slug}</code>
                      </td>
                      <td>{row.campaign_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        ) : null}
      </div>

      <div className="card" style={{ maxWidth: 560, marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новая кампания</h3>
        <form className="form-stack" onSubmit={onCreate}>
          <label>
            Название
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            ref (slug)
            <input value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="vk_fashion26" />
          </label>
          <label>
            Путь на лендинге
            <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="/" />
            <span className="field-hint">
              <code>/</code> — главная; <code>/blog/kak-sdelat-lukbuk</code> — статья.
            </span>
          </label>
          <button
            type="submit"
            disabled={busy || !name.trim() || (!slug.trim() && !slugPreviewValid)}
          >
            {busy ? "Создание…" : "Создать ссылку"}
          </button>
        </form>
        {previewUrl ? (
          <div className="campaign-created-preview">
            <a href={previewUrl} target="_blank" rel="noreferrer">
              {previewUrl}
            </a>
            <QrBlock url={previewUrl} slug={previewSlug} />
          </div>
        ) : null}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Кампании Xfashion</h3>
        {!data?.items?.length ? (
          <p style={{ color: "var(--muted)" }}>Пока нет кампаний.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>ref</th>
                <th>Заходы</th>
                <th>Ссылка</th>
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
