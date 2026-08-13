import { useCallback, useEffect, useState } from "react";
import {
  createHeroBanner,
  deleteHeroBanner,
  fetchHeroBanners,
  updateHeroBanner,
  uploadHeroBannerImage,
} from "../api.js";
import ImageCropModal from "../components/ImageCropModal.jsx";

/**
 * Mobile hero на /v2 — не портрет 3:4: зона баннера шире высоты
 * (остаток экрана после MEN/WOMEN + бренды + акценты + низ) ≈ 6:5.
 */
const MOBILE_ASPECT = 6 / 5;
/** Desktop-вариант — широкий кадр */
const DESKTOP_ASPECT = 16 / 9;

function toDatetimeLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(value) {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

/** Файл на диске всегда {id}.jpg — без ?v= браузер показывает старое превью */
function mediaPreviewUrl(url, updatedAt) {
  if (!url) return "";
  if (url.startsWith("blob:") || url.startsWith("data:")) return url;
  const t = updatedAt ? new Date(updatedAt).getTime() : Date.now();
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${Number.isFinite(t) ? t : Date.now()}`;
}

const emptyForm = () => ({
  title: "",
  subtitle: "",
  body: "",
  link_url: "",
  link_label: "",
  starts_at: "",
  ends_at: "",
  is_active: true,
  priority: "0",
});

export default function HeroBanners() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [editingId, setEditingId] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState("");
  const [desktopFile, setDesktopFile] = useState(null);
  const [desktopPreview, setDesktopPreview] = useState("");
  const [busy, setBusy] = useState(false);
  const [crop, setCrop] = useState(null); // { kind, src }

  const reload = useCallback(async () => {
    const data = await fetchHeroBanners();
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
    setImageFile(null);
    setImagePreview("");
    setDesktopFile(null);
    setDesktopPreview("");
    setErr("");
  }

  function startEdit(row) {
    setEditingId(row.id);
    setForm({
      title: row.title || "",
      subtitle: row.subtitle || "",
      body: row.body || "",
      link_url: row.link_url || "",
      link_label: row.link_label || "",
      starts_at: toDatetimeLocal(row.starts_at),
      ends_at: toDatetimeLocal(row.ends_at),
      is_active: row.is_active !== false,
      priority: String(row.priority ?? 0),
    });
    setImageFile(null);
    setImagePreview(mediaPreviewUrl(row.image_url, row.updated_at));
    setDesktopFile(null);
    setDesktopPreview(mediaPreviewUrl(row.image_url_desktop, row.updated_at));
    setErr("");
  }

  function onPickImage(e, kind) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const src = URL.createObjectURL(file);
    setCrop({ kind, src });
  }

  function onCropCancel() {
    if (crop?.src) URL.revokeObjectURL(crop.src);
    setCrop(null);
  }

  function onCropConfirm(file, previewUrl) {
    if (crop?.src) URL.revokeObjectURL(crop.src);
    if (crop?.kind === "desktop") {
      setDesktopFile(file);
      setDesktopPreview(previewUrl);
    } else {
      setImageFile(file);
      setImagePreview(previewUrl);
    }
    setCrop(null);
  }

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    const title = form.title.trim();
    if (!title) {
      setErr("Укажите заголовок");
      return;
    }
    const payload = {
      title,
      subtitle: form.subtitle.trim() || null,
      body: form.body.trim() || null,
      link_url: form.link_url.trim() || null,
      link_label: form.link_label.trim() || null,
      starts_at: fromDatetimeLocal(form.starts_at),
      ends_at: fromDatetimeLocal(form.ends_at),
      is_active: form.is_active,
      priority: Number.parseInt(form.priority, 10) || 0,
    };
    setBusy(true);
    try {
      let row;
      if (editingId) {
        row = await updateHeroBanner(editingId, payload);
      } else {
        row = await createHeroBanner(payload);
        setEditingId(row.id);
      }
      if (imageFile) {
        if (imagePreview.startsWith("blob:")) URL.revokeObjectURL(imagePreview);
        const up = await uploadHeroBannerImage(row.id, imageFile, "mobile");
        row = {
          ...row,
          image_url: up.image_url,
          image_url_desktop: up.image_url_desktop ?? row.image_url_desktop,
        };
      }
      if (desktopFile) {
        if (desktopPreview.startsWith("blob:")) URL.revokeObjectURL(desktopPreview);
        const up = await uploadHeroBannerImage(row.id, desktopFile, "desktop");
        row = {
          ...row,
          image_url: up.image_url ?? row.image_url,
          image_url_desktop: up.image_url_desktop,
        };
      }
      const list = await fetchHeroBanners();
      const fresh = (list.items || []).find((i) => i.id === row.id) || row;
      setItems(list.items || []);
      startEdit(fresh);
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id) {
    if (!confirm("Удалить hero-баннер?")) return;
    setErr("");
    setBusy(true);
    try {
      await deleteHeroBanner(id);
      if (editingId === id) startCreate();
      await reload();
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function onClearImage(kind) {
    if (!editingId) return;
    setErr("");
    setBusy(true);
    try {
      const body =
        kind === "desktop" ? { clear_image_desktop: true } : { clear_image: true };
      await updateHeroBanner(editingId, body);
      if (kind === "desktop") {
        setDesktopPreview("");
        setDesktopFile(null);
      } else {
        setImagePreview("");
        setImageFile(null);
      }
      await reload();
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Hero-баннеры (главная /v2)</h2>
      <p style={{ color: "var(--muted)", maxWidth: 640 }}>
        Баннер на /v2 занимает верх экрана (не весь viewport). Несколько активных
        сменяются по очереди: от большего приоритета к меньшему, плавный crossfade.
        Кадрируйте mobile под рамку 6:5 — как реальная зона на телефоне; desktop — 16:9.
        Видео в модалке: CTA-ссылка <code>/watch/slug</code> из раздела «Видео».
      </p>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="flex-gap" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, flex: 1 }}>
            {editingId ? "Редактирование" : "Новый hero-баннер"}
          </h3>
          {editingId ? (
            <button type="button" className="secondary" onClick={startCreate}>
              Создать другой
            </button>
          ) : null}
        </div>
        <form className="form-stack" onSubmit={onSubmit}>
          <div>
            <label>Заголовок *</label>
            <input
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
              maxLength={200}
              placeholder="NEW ARRIVALS"
            />
          </div>
          <div>
            <label>Подзаголовок</label>
            <input
              value={form.subtitle}
              onChange={(e) => setForm((f) => ({ ...f, subtitle: e.target.value }))}
              maxLength={120}
              placeholder="FROM ITALY"
            />
          </div>
          <div>
            <label>Текст</label>
            <textarea
              value={form.body}
              onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
              rows={3}
              style={{ width: "100%", resize: "vertical" }}
              placeholder="17 НОВЫХ МОДЕЛЕЙ УЖЕ В БУТИКЕ"
            />
          </div>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Ссылка CTA</label>
              <input
                value={form.link_url}
                onChange={(e) => setForm((f) => ({ ...f, link_url: e.target.value }))}
                placeholder="/watch/about, /swipe/female или https://…"
              />
            </div>
            <div style={{ flex: 1 }}>
              <label>Текст кнопки</label>
              <input
                value={form.link_label}
                onChange={(e) => setForm((f) => ({ ...f, link_label: e.target.value }))}
                placeholder="СМОТРЕТЬ НОВИНКИ"
              />
            </div>
          </div>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Показ с</label>
              <input
                type="datetime-local"
                value={form.starts_at}
                onChange={(e) => setForm((f) => ({ ...f, starts_at: e.target.value }))}
              />
            </div>
            <div style={{ flex: 1 }}>
              <label>Показ по</label>
              <input
                type="datetime-local"
                value={form.ends_at}
                onChange={(e) => setForm((f) => ({ ...f, ends_at: e.target.value }))}
              />
            </div>
          </div>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Приоритет (больше — раньше в карусели)</label>
              <input
                type="number"
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              />
            </div>
            <label className="flex-gap" style={{ alignItems: "center", width: "auto", flex: 1 }}>
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
              />
              Активен
            </label>
          </div>

          <div>
            <label>Картинка mobile (6:5 — зона баннера) *</label>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif,image/avif"
              onChange={(e) => onPickImage(e, "mobile")}
            />
            <p style={{ fontSize: "0.85rem", color: "var(--muted)", margin: "0.35rem 0 0" }}>
              Без этого кадра баннер не попадёт в карусель на главной. После выбора
              откроется кадрирование. Акцент лучше держать справа — слева затемнение и текст.
            </p>
            {imagePreview ? (
              <div className="promo-banner-admin-preview hero-crop-preview hero-crop-preview--mobile">
                <img src={imagePreview} alt="" />
              </div>
            ) : null}
            {editingId && imagePreview ? (
              <button
                type="button"
                className="secondary danger"
                style={{ marginTop: "0.5rem" }}
                disabled={busy}
                onClick={() => onClearImage("mobile")}
              >
                Убрать mobile
              </button>
            ) : null}
          </div>

          <div>
            <label>Картинка desktop (16:9)</label>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif,image/avif"
              onChange={(e) => onPickImage(e, "desktop")}
            />
            <p style={{ fontSize: "0.85rem", color: "var(--muted)", margin: "0.35rem 0 0" }}>
              Если не задана — на десктопе используется mobile.
            </p>
            {desktopPreview ? (
              <div className="promo-banner-admin-preview hero-crop-preview hero-crop-preview--desktop">
                <img src={desktopPreview} alt="" />
              </div>
            ) : null}
            {editingId && desktopPreview ? (
              <button
                type="button"
                className="secondary danger"
                style={{ marginTop: "0.5rem" }}
                disabled={busy}
                onClick={() => onClearImage("desktop")}
              >
                Убрать desktop
              </button>
            ) : null}
          </div>

          {err ? <p className="error">{err}</p> : null}
          <button type="submit" disabled={busy}>
            {busy ? "Сохранение…" : editingId ? "Сохранить" : "Создать"}
          </button>
        </form>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Заголовок</th>
              <th>Период</th>
              <th>Приор.</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ color: "var(--muted)" }}>
                  Hero-баннеров пока нет — на /v2 текстовая заглушка
                </td>
              </tr>
            ) : (
              items.map((row) => (
                <tr key={row.id}>
                  <td>
                    {row.is_active ? null : (
                      <span style={{ color: "var(--muted)" }}>[выкл] </span>
                    )}
                    {row.title}
                    {row.image_url ? " 📱" : ""}
                    {row.image_url_desktop ? " 🖥" : ""}
                    {!row.image_url && !row.image_url_desktop ? (
                      <span style={{ color: "var(--muted)" }}>
                        {" "}
                        — нет фото, на главной не будет
                      </span>
                    ) : null}
                  </td>
                  <td style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                    {row.starts_at
                      ? new Date(row.starts_at).toLocaleString("ru-RU")
                      : "—"}
                    {" → "}
                    {row.ends_at
                      ? new Date(row.ends_at).toLocaleString("ru-RU")
                      : "—"}
                  </td>
                  <td>{row.priority}</td>
                  <td className="table-actions">
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

      {crop ? (
        <ImageCropModal
          imageSrc={crop.src}
          aspect={crop.kind === "desktop" ? DESKTOP_ASPECT : MOBILE_ASPECT}
          title={
            crop.kind === "desktop"
              ? "Кадр desktop 16:9"
              : "Кадр mobile 6:5"
          }
          hint={
            crop.kind === "desktop"
              ? "Перетащите фото и масштаб — рамка = то, что увидят на широком экране."
              : "Рамка = реальная зона баннера на /v2 (шире, чем 3:4). Лица/акцент — справа, в овале света."
          }
          onCancel={onCropCancel}
          onConfirm={onCropConfirm}
        />
      ) : null}
    </div>
  );
}
