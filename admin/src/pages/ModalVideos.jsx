import { useCallback, useEffect, useState } from "react";
import {
  createModalVideo,
  deleteModalVideo,
  fetchModalVideos,
  updateModalVideo,
  uploadModalVideoFile,
  uploadModalVideoPoster,
} from "../api.js";

function mediaPreviewUrl(url, updatedAt) {
  if (!url) return "";
  const t = updatedAt ? new Date(updatedAt).getTime() : Date.now();
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${Number.isFinite(t) ? t : Date.now()}`;
}

const emptyForm = () => ({
  slug: "",
  title: "",
  body: "",
  cta_mode: "lead",
  cta_label: "",
  lead_note: "",
  is_active: true,
});

export default function ModalVideos() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [editingId, setEditingId] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [videoFile, setVideoFile] = useState(null);
  const [posterFile, setPosterFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState("");

  const reload = useCallback(async () => {
    const data = await fetchModalVideos();
    setItems(data.items || []);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await reload();
      } catch (e) {
        if (!cancelled) setErr(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reload]);

  function startCreate() {
    setEditingId("");
    setForm(emptyForm());
    setVideoFile(null);
    setPosterFile(null);
    setErr("");
  }

  function startEdit(row) {
    setEditingId(row.id);
    setForm({
      slug: row.slug || "",
      title: row.title || "",
      body: row.body || "",
      cta_mode: row.cta_mode === "close" ? "close" : "lead",
      cta_label: row.cta_label || "",
      lead_note: row.lead_note || "",
      is_active: !!row.is_active,
    });
    setVideoFile(null);
    setPosterFile(null);
    setErr("");
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const payload = {
        slug: form.slug.trim(),
        title: form.title.trim(),
        body: form.body.trim() || null,
        cta_mode: form.cta_mode,
        cta_label: form.cta_label.trim() || null,
        lead_note: form.lead_note.trim() || null,
        is_active: form.is_active,
      };
      let id = editingId;
      if (editingId) {
        await updateModalVideo(editingId, payload);
      } else {
        const row = await createModalVideo(payload);
        id = row.id;
        setEditingId(row.id);
      }
      if (videoFile) {
        await uploadModalVideoFile(id, videoFile);
      }
      if (posterFile) {
        await uploadModalVideoPoster(id, posterFile);
      }
      await reload();
      setVideoFile(null);
      setPosterFile(null);
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id) {
    if (!window.confirm("Удалить это видео?")) return;
    setBusy(true);
    setErr("");
    try {
      await deleteModalVideo(id);
      if (editingId === id) startCreate();
      await reload();
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function copyLink(slug) {
    const path = `/watch/${slug}`;
    try {
      await navigator.clipboard.writeText(path);
      setCopied(slug);
      window.setTimeout(() => setCopied(""), 1600);
    } catch {
      window.prompt("Скопируйте ссылку", path);
    }
  }

  if (loading) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  const editing = items.find((x) => x.id === editingId);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Видео в модалке</h2>
      <p style={{ color: "var(--muted)", maxWidth: 680 }}>
        Загрузите ролик — получите ссылку <code>/watch/slug</code>. Её можно
        вставить в CTA hero-баннера или любую кнопку. Slug{" "}
        <code>about</code> автоматически появляется на странице «Об ANTRASHA».
        После видео: заявка (телефон + оповещение в MAX) или кнопка «Закрыть».
        Сжатие на сервере: H.264, до 1280px, быстрый старт на телефоне (до ~80
        МБ исходника, обработка 10–40 сек).
      </p>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="flex-gap" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, flex: 1 }}>
            {editingId ? "Редактирование" : "Новое видео"}
          </h3>
          {editingId ? (
            <button type="button" className="secondary" onClick={startCreate}>
              Создать другое
            </button>
          ) : null}
        </div>
        <form className="form-stack" onSubmit={onSubmit}>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Slug (латиница) *</label>
              <input
                value={form.slug}
                onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
                required
                maxLength={80}
                placeholder="about"
              />
              <p style={{ fontSize: "0.85rem", color: "var(--muted)", margin: "0.35rem 0 0" }}>
                Ссылка для кнопки: <code>/watch/{form.slug.trim() || "slug"}</code>
              </p>
            </div>
            <div style={{ flex: 1 }}>
              <label>Заголовок под видео *</label>
              <input
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                required
                maxLength={200}
                placeholder="Новая коллекция в бутике"
              />
            </div>
          </div>
          <div>
            <label>Текст после видео</label>
            <textarea
              value={form.body}
              onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
              rows={3}
              style={{ width: "100%", resize: "vertical" }}
              placeholder="Оставьте заявку — подберём образы лично"
            />
          </div>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>После ролика</label>
              <select
                value={form.cta_mode}
                onChange={(e) => setForm((f) => ({ ...f, cta_mode: e.target.value }))}
              >
                <option value="lead">Заявка (телефон + оповещение)</option>
                <option value="close">Только «Закрыть»</option>
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label>Текст кнопки</label>
              <input
                value={form.cta_label}
                onChange={(e) => setForm((f) => ({ ...f, cta_label: e.target.value }))}
                maxLength={80}
                placeholder={
                  form.cta_mode === "close" ? "Закрыть" : "Оставить заявку"
                }
              />
            </div>
          </div>
          {form.cta_mode === "lead" ? (
            <div>
              <label>Пометка в заявке (для оповещения)</label>
              <input
                value={form.lead_note}
                onChange={(e) => setForm((f) => ({ ...f, lead_note: e.target.value }))}
                maxLength={200}
                placeholder="Видео: lookbook"
              />
            </div>
          ) : null}
          <label className="flex-gap" style={{ alignItems: "center", width: "auto" }}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
            />
            Активно
          </label>

          <div>
            <label>Видео (mp4 / mov / webm, до 80 МБ)</label>
            <input
              type="file"
              accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.m4v,.webm"
              onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
            />
            {videoFile ? (
              <p style={{ fontSize: "0.85rem", color: "var(--muted)", margin: "0.35rem 0 0" }}>
                К загрузке: {videoFile.name} ({Math.round(videoFile.size / 1024 / 1024)} МБ)
              </p>
            ) : null}
            {editing?.video_url ? (
              <video
                src={mediaPreviewUrl(editing.video_url, editing.updated_at)}
                controls
                playsInline
                preload="metadata"
                style={{
                  display: "block",
                  width: "100%",
                  maxWidth: 420,
                  marginTop: 10,
                  background: "#111",
                }}
              />
            ) : null}
          </div>
          <div>
            <label>Постер (необязательно — кадр берётся сам)</label>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => setPosterFile(e.target.files?.[0] || null)}
            />
            {editing?.poster_url ? (
              <img
                src={mediaPreviewUrl(editing.poster_url, editing.updated_at)}
                alt=""
                style={{ display: "block", maxWidth: 220, marginTop: 8 }}
              />
            ) : null}
          </div>

          {err ? <p className="error">{err}</p> : null}
          <button type="submit" disabled={busy}>
            {busy
              ? videoFile
                ? "Обрабатываем видео…"
                : "Сохранение…"
              : editingId
                ? "Сохранить"
                : "Создать"}
          </button>
        </form>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Slug</th>
              <th>Заголовок</th>
              <th>После ролика</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ color: "var(--muted)" }}>
                  Видео пока нет
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.is_active ? null : (
                      <span style={{ color: "var(--muted)" }}>[выкл] </span>
                    )}
                    <code>/watch/{row.slug}</code>
                    {row.video_url ? "" : " — нет файла"}
                  </td>
                  <td>{row.title}</td>
                  <td>{row.cta_mode === "lead" ? "Заявка" : "Закрыть"}</td>
                  <td className="table-actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => copyLink(row.slug)}
                    >
                      {copied === row.slug ? "Скопировано" : "Копировать ссылку"}
                    </button>
                    <button type="button" className="secondary" onClick={() => startEdit(row)}>
                      Изменить
                    </button>
                    <button
                      type="button"
                      className="danger"
                      disabled={busy}
                      onClick={() => onDelete(row.id)}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
