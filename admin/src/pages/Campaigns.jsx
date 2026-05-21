import { useCallback, useEffect, useMemo, useState } from "react";
import { createCampaign, fetchAttributionDebug, fetchCampaigns } from "../api.js";
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
        <img
          src={src}
          alt="QR-код"
          width={200}
          height={200}
          className="qr-block__preview"
        />
      ) : null}
      <p className="qr-block__hint">
        Скачайте файл и вставьте в макет: SVG — для сайтов и векторной графики;
        PNG 2048 — для сторис, постов и видео; PNG прозрачный — поверх баннера или
        ролика.
      </p>
      <div className="qr-block__actions">
        <button
          type="button"
          className="secondary"
          disabled={!!busy}
          onClick={() =>
            runDownload(() => downloadQrSvg(url, { slug: fileSlug }))
          }
        >
          SVG{busy === "…" ? "…" : ""}
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
        <button
          type="button"
          className="secondary"
          disabled={!!busy}
          onClick={() =>
            runDownload(() => downloadQrPng(url, { slug: fileSlug, sizePx: 1024 }))
          }
        >
          PNG 1024
        </button>
        <button
          type="button"
          className="secondary"
          disabled={!!busy}
          onClick={() =>
            runDownload(() =>
              downloadQrPngTransparent(url, { slug: fileSlug, sizePx: 2048 }),
            )
          }
        >
          PNG прозрачный
        </button>
      </div>
    </div>
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
      setDebug(await fetchAttributionDebug());
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
      <h2 style={{ marginTop: 0 }}>Рекламные ссылки</h2>
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Ссылка для рекламы = адрес сайта + путь +{" "}
        <code>?ref=код_кампании</code>. По <code>ref</code> считаются заходы в
        статистике.
        {data?.public_app_url ? (
          <>
            {" "}
            Базовый домен: <strong>{data.public_app_url}</strong> (
            <code>PUBLIC_APP_URL</code>).
          </>
        ) : null}
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Проверка заходов</h3>
        <p className="field-hint" style={{ marginTop: 0 }}>
          Регистрация не нужна: считается создание сессии с <code>?ref=</code> при
          открытии сайта. Для чистого теста — режим инкогнито или очистка данных
          сайта на телефоне/в браузере.
        </p>
        <button
          type="button"
          className="secondary"
          disabled={debugBusy}
          onClick={loadDebug}
        >
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
                  <th>Заходов в статистике</th>
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
              Последние зафиксированные сессии с ref
            </h4>
            {!debug.recent_attributed_sessions?.length ? (
              <p style={{ color: "var(--muted)", margin: 0 }}>
                Пока нет — откройте ссылку в инкогнито и нажмите «Обновить».
              </p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Время (UTC)</th>
                    <th>ref</th>
                    <th>Кампания</th>
                  </tr>
                </thead>
                <tbody>
                  {debug.recent_attributed_sessions.map((row) => (
                    <tr key={row.session_id}>
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
            Название (только для вас в админке)
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="VK — май 2026, баннер A"
              required
            />
            <span className="field-hint">
              В ссылку не попадает. Нужно, чтобы в списке и статистике было понятно,
              что за кампания.
            </span>
          </label>

          <label>
            Код в ссылке (ref / slug)
            <input
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              placeholder="vk_may26"
            />
            <span className="field-hint">
              Часть ссылки после <code>?ref=</code>. Латиница, цифры, <code>_</code> и{" "}
              <code>-</code>. Если оставить пустым — соберётся из названия (пробелы →
              подчёркивания, кириллица убирается). Для русского названия код лучше
              вписать вручную, например <code>vk_may26</code>.
            </span>
            {name.trim() && !slug.trim() ? (
              <span className={`field-preview${slugPreviewValid ? "" : " field-preview--warn"}`}>
                {slugPreviewValid ? (
                  <>
                    Будет в ссылке: <code>?ref={slugPreview}</code>
                  </>
                ) : (
                  <>
                    Из названия код не получился — укажите ref вручную (латиницей).
                  </>
                )}
              </span>
            ) : null}
            {slug.trim() && slugPreview ? (
              <span className="field-preview">
                В ссылке: <code>?ref={slugPreview}</code>
              </span>
            ) : null}
          </label>

          <label>
            Страница входа (путь)
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/"
            />
            <span className="field-hint">
              Куда попадёт человек по ссылке: <code>/</code> — главная с выбором
              коллекции; <code>/swipe/female</code> или <code>/swipe/male</code> — сразу
              свайп; <code>/about</code> — страница о бренде. Параметр{" "}
              <code>?ref=…</code> добавится автоматически.
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
            <div className="field-hint">Последняя созданная ссылка</div>
            <a href={previewUrl} target="_blank" rel="noreferrer">
              {previewUrl}
            </a>
            <QrBlock url={previewUrl} slug={previewSlug} />
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
                <th>Ссылка и QR</th>
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
                        {copiedId === row.id ? "Скопировано" : "Копировать ссылку"}
                      </button>
                      <details style={{ marginTop: "0.5rem" }}>
                        <summary>QR — скачать</summary>
                        <QrBlock url={row.tracking_url} slug={row.slug} />
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
