import { useCallback, useEffect, useRef, useState } from "react";
import {
  createPromoBanner,
  deletePromoBanner,
  fetchPromoBanners,
  updatePromoBanner,
  uploadPromoBannerImage,
} from "../api.js";

const DISPLAY_MODES = [
  { value: "once", label: "Один раз" },
  { value: "twice", label: "Два раза" },
  { value: "every_visit", label: "Повторно, не чаще чем раз в 2 часа" },
];

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

function displayModeLabel(mode) {
  return DISPLAY_MODES.find((m) => m.value === mode)?.label ?? mode;
}

/** Обернуть выделение в textarea/input в **...**; если нет выделения — вставить ** **. */
function wrapBold(el, value, setValue) {
  if (!el) {
    setValue(`${value}****`);
    return;
  }
  const start = el.selectionStart ?? value.length;
  const end = el.selectionEnd ?? value.length;
  const selected = value.slice(start, end);
  const next =
    selected.length > 0
      ? value.slice(0, start) + `**${selected}**` + value.slice(end)
      : value.slice(0, start) + "****" + value.slice(end);
  setValue(next);
  requestAnimationFrame(() => {
    el.focus();
    const cursor = selected.length > 0 ? start + selected.length + 4 : start + 2;
    el.setSelectionRange(cursor, cursor);
  });
}

const emptyForm = () => ({
  title: "",
  body: "",
  link_url: "",
  link_label: "",
  show_gender_ctas: true,
  cta_male_label: "Мужчинам",
  cta_female_label: "Женщинам",
  image_fit: "fit",
  starts_at: "",
  ends_at: "",
  display_mode: "once",
  is_active: true,
  priority: "0",
});

export default function PromoBanners() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [editingId, setEditingId] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState("");
  const [busy, setBusy] = useState(false);
  const titleRef = useRef(null);
  const bodyRef = useRef(null);

  const reload = useCallback(async () => {
    const data = await fetchPromoBanners();
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
    setErr("");
  }

  function startEdit(row) {
    setEditingId(row.id);
    setForm({
      title: row.title || "",
      body: row.body || "",
      link_url: row.link_url || "",
      link_label: row.link_label || "",
      show_gender_ctas: !!row.show_gender_ctas,
      cta_male_label: row.cta_male_label || "Мужчинам",
      cta_female_label: row.cta_female_label || "Женщинам",
      image_fit: row.image_fit === "cover" ? "cover" : "fit",
      starts_at: toDatetimeLocal(row.starts_at),
      ends_at: toDatetimeLocal(row.ends_at),
      display_mode: row.display_mode || "once",
      is_active: row.is_active !== false,
      priority: String(row.priority ?? 0),
    });
    setImageFile(null);
    setImagePreview(row.image_url || "");
    setErr("");
  }

  function onPickImage(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    setImagePreview(URL.createObjectURL(file));
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
      body: form.body.trim() || null,
      link_url: form.link_url.trim() || null,
      link_label: form.link_label.trim() || null,
      show_gender_ctas: !!form.show_gender_ctas,
      cta_male_label: form.cta_male_label.trim() || null,
      cta_female_label: form.cta_female_label.trim() || null,
      image_fit: form.image_fit === "cover" ? "cover" : "fit",
      starts_at: fromDatetimeLocal(form.starts_at),
      ends_at: fromDatetimeLocal(form.ends_at),
      display_mode: form.display_mode,
      is_active: form.is_active,
      priority: Number.parseInt(form.priority, 10) || 0,
    };
    setBusy(true);
    try {
      let row;
      if (editingId) {
        row = await updatePromoBanner(editingId, payload);
      } else {
        row = await createPromoBanner(payload);
        setEditingId(row.id);
      }
      if (imageFile) {
        const up = await uploadPromoBannerImage(row.id, imageFile);
        row = { ...row, image_url: up.image_url };
        setImageFile(null);
        setImagePreview(up.image_url);
      }
      await reload();
      if (!editingId) startEdit(row);
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(id) {
    if (!confirm("Удалить баннер?")) return;
    setErr("");
    setBusy(true);
    try {
      await deletePromoBanner(id);
      if (editingId === id) startCreate();
      await reload();
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function onClearImage() {
    if (!editingId) return;
    setErr("");
    setBusy(true);
    try {
      await updatePromoBanner(editingId, { clear_image: true });
      setImagePreview("");
      setImageFile(null);
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
      <h2 style={{ marginTop: 0 }}>Баннеры на главной</h2>
      <p style={{ color: "var(--muted)", maxWidth: 640 }}>
        Модальное окно на стартовой странице: акции, новости. Эмодзи можно вставлять прямо в
        текст (😀 🔥). Жирный: оберните фрагмент в <code>**так**</code> или кнопкой ниже.
        При нескольких активных — выше приоритет.
      </p>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <div className="flex-gap" style={{ marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, flex: 1 }}>
            {editingId ? "Редактирование" : "Новый баннер"}
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
            <div className="flex-gap" style={{ marginBottom: "0.35rem" }}>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  wrapBold(titleRef.current, form.title, (v) =>
                    setForm((f) => ({ ...f, title: v })),
                  )
                }
              >
                Жирный **
              </button>
            </div>
            <input
              ref={titleRef}
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              required
              maxLength={200}
              placeholder="Например: **Sale** весна 🔥"
            />
          </div>
          <div>
            <label>Текст</label>
            <div className="flex-gap" style={{ marginBottom: "0.35rem" }}>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  wrapBold(bodyRef.current, form.body, (v) =>
                    setForm((f) => ({ ...f, body: v })),
                  )
                }
              >
                Жирный **
              </button>
            </div>
            <textarea
              ref={bodyRef}
              value={form.body}
              onChange={(e) => setForm((f) => ({ ...f, body: e.target.value }))}
              rows={4}
              style={{ width: "100%", resize: "vertical" }}
              placeholder={"Можно эмодзи и **жирный** фрагмент.\nПеренос строки сохраняется."}
            />
          </div>

          <fieldset
            style={{
              border: "1px solid var(--border)",
              borderRadius: 8,
              padding: "0.75rem 1rem",
              margin: 0,
            }}
          >
            <legend style={{ padding: "0 0.35rem", fontWeight: 600 }}>Кнопки коллекций</legend>
            <label className="flex-gap" style={{ alignItems: "center", width: "auto", marginBottom: "0.65rem" }}>
              <input
                type="checkbox"
                checked={form.show_gender_ctas}
                onChange={(e) =>
                  setForm((f) => ({ ...f, show_gender_ctas: e.target.checked }))
                }
              />
              Показать две кнопки: мужская / женская коллекция
            </label>
            {form.show_gender_ctas ? (
              <div className="flex-gap">
                <div style={{ flex: 1 }}>
                  <label>Текст «мужчинам»</label>
                  <input
                    value={form.cta_male_label}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, cta_male_label: e.target.value }))
                    }
                    maxLength={80}
                    placeholder="Мужчинам"
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label>Текст «женщинам»</label>
                  <input
                    value={form.cta_female_label}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, cta_female_label: e.target.value }))
                    }
                    maxLength={80}
                    placeholder="Женщинам"
                  />
                </div>
              </div>
            ) : null}
          </fieldset>

          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Доп. ссылка (внешняя, опционально)</label>
              <input
                value={form.link_url}
                onChange={(e) => setForm((f) => ({ ...f, link_url: e.target.value }))}
                placeholder="https://…"
              />
            </div>
            <div style={{ flex: 1 }}>
              <label>Текст кнопки ссылки</label>
              <input
                value={form.link_label}
                onChange={(e) => setForm((f) => ({ ...f, link_label: e.target.value }))}
                placeholder="Подробнее"
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
              <label>Частота показа</label>
              <select
                value={form.display_mode}
                onChange={(e) =>
                  setForm((f) => ({ ...f, display_mode: e.target.value }))
                }
              >
                {DISPLAY_MODES.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ flex: 1 }}>
              <label>Приоритет (больше — выше)</label>
              <input
                type="number"
                value={form.priority}
                onChange={(e) => setForm((f) => ({ ...f, priority: e.target.value }))}
              />
            </div>
          </div>
          <label className="flex-gap" style={{ alignItems: "center", width: "auto" }}>
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
            />
            Активен
          </label>

          <div>
            <label>Изображение</label>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp,image/gif,image/avif"
              onChange={onPickImage}
            />
            <p style={{ fontSize: "0.85rem", color: "var(--muted)", margin: "0.35rem 0 0" }}>
              JPG, PNG, WebP, GIF, AVIF — до 8 МБ. Квадрат, альбом, портрет — любой формат.
            </p>
            <div style={{ marginTop: "0.5rem", maxWidth: 280 }}>
              <label>Как показать картинку</label>
              <select
                value={form.image_fit}
                onChange={(e) => setForm((f) => ({ ...f, image_fit: e.target.value }))}
              >
                <option value="fit">Вписать целиком (без обрезки)</option>
                <option value="cover">Заполнить блок (обрезка краёв)</option>
              </select>
            </div>
            {imagePreview ? (
              <div className="promo-banner-admin-preview">
                <img src={imagePreview} alt="" />
              </div>
            ) : null}
            {editingId && imagePreview ? (
              <button
                type="button"
                className="secondary danger"
                style={{ marginTop: "0.5rem" }}
                disabled={busy}
                onClick={onClearImage}
              >
                Убрать картинку
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
              <th>Режим</th>
              <th>Период</th>
              <th>Приор.</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ color: "var(--muted)" }}>
                  Баннеров пока нет
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
                    {row.image_url ? " 🖼" : ""}
                    {row.show_gender_ctas ? " ♂♀" : ""}
                  </td>
                  <td>{displayModeLabel(row.display_mode)}</td>
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
    </div>
  );
}
