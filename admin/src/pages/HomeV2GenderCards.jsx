import { useCallback, useEffect, useState } from "react";
import {
  clearHomeV2GenderImage,
  fetchHomeV2Settings,
  uploadHomeV2GenderImage,
} from "../api.js";
import ImageCropModal from "../components/ImageCropModal.jsx";

/** Карточки MEN/WOMEN на /v2 — вытянутые по вертикали (~5:6) */
const CARD_ASPECT = 5 / 6;

function mediaPreviewUrl(url, updatedAt) {
  if (!url) return "";
  if (url.startsWith("blob:") || url.startsWith("data:")) return url;
  const t = updatedAt ? new Date(updatedAt).getTime() : Date.now();
  const sep = url.includes("?") ? "&" : "?";
  return `${url}${sep}v=${Number.isFinite(t) ? t : Date.now()}`;
}

const SLOTS = [
  {
    key: "male",
    label: "MEN",
    hint: "Кнопка мужской коллекции → /swipe/male",
  },
  {
    key: "female",
    label: "WOMEN",
    hint: "Кнопка женской коллекции → /swipe/female",
  },
];

export default function HomeV2GenderCards() {
  const [settings, setSettings] = useState({
    image_url_male: null,
    image_url_female: null,
    updated_at: null,
  });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [crop, setCrop] = useState(null); // { slot, src }

  const reload = useCallback(async () => {
    const data = await fetchHomeV2Settings();
    setSettings({
      image_url_male: data.image_url_male || null,
      image_url_female: data.image_url_female || null,
      updated_at: data.updated_at || null,
    });
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

  function onPick(e, slot) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setCrop({ slot, src: URL.createObjectURL(file) });
  }

  function onCropCancel() {
    if (crop?.src) URL.revokeObjectURL(crop.src);
    setCrop(null);
  }

  async function onCropConfirm(file, previewUrl) {
    if (!crop) return;
    const slot = crop.slot;
    if (crop.src) URL.revokeObjectURL(crop.src);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setCrop(null);
    setErr("");
    setBusy(true);
    try {
      const up = await uploadHomeV2GenderImage(slot, file);
      setSettings({
        image_url_male: up.image_url_male || null,
        image_url_female: up.image_url_female || null,
        updated_at: up.updated_at || new Date().toISOString(),
      });
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function onClear(slot) {
    if (!confirm(`Убрать фото ${slot === "male" ? "MEN" : "WOMEN"}? На /v2 вернётся картинка по умолчанию.`)) {
      return;
    }
    setErr("");
    setBusy(true);
    try {
      const data = await clearHomeV2GenderImage(slot);
      setSettings({
        image_url_male: data.image_url_male || null,
        image_url_female: data.image_url_female || null,
        updated_at: data.updated_at || null,
      });
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Фото MEN / WOMEN (/v2)</h2>
      <p style={{ color: "var(--muted)", maxWidth: 640 }}>
        Карточки под hero-баннером. Кадр 5:6 — как реальная (более высокая) кнопка на телефоне.
        Без своего фото на /v2 показывается встроенная картинка.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div
        className="flex-gap"
        style={{ alignItems: "stretch", flexWrap: "wrap", gap: "1rem" }}
      >
        {SLOTS.map((slot) => {
          const url =
            slot.key === "male" ? settings.image_url_male : settings.image_url_female;
          const preview = mediaPreviewUrl(url, settings.updated_at);
          return (
            <div className="card" key={slot.key} style={{ flex: "1 1 260px", maxWidth: 360 }}>
              <h3 style={{ marginTop: 0 }}>{slot.label}</h3>
              <p style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: 0 }}>
                {slot.hint}
              </p>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif,image/avif"
                disabled={busy}
                onChange={(e) => onPick(e, slot.key)}
              />
              <p style={{ fontSize: "0.85rem", color: "var(--muted)", margin: "0.35rem 0 0" }}>
                После выбора — кадрирование. Лучше лицо/фигура сверху.
              </p>
              {preview ? (
                <div
                  className="promo-banner-admin-preview hero-crop-preview"
                  style={{ aspectRatio: "5 / 6", width: "100%", maxWidth: 220, marginTop: "0.75rem" }}
                >
                  <img src={preview} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                </div>
              ) : (
                <p style={{ color: "var(--muted)", marginTop: "0.75rem" }}>
                  Сейчас — фото по умолчанию
                </p>
              )}
              {url ? (
                <button
                  type="button"
                  className="secondary danger"
                  style={{ marginTop: "0.75rem" }}
                  disabled={busy}
                  onClick={() => onClear(slot.key)}
                >
                  Убрать — вернуть дефолт
                </button>
              ) : null}
            </div>
          );
        })}
      </div>

      {crop ? (
        <ImageCropModal
          imageSrc={crop.src}
          aspect={CARD_ASPECT}
          title={`Кадр ${crop.slot === "male" ? "MEN" : "WOMEN"} 5:6`}
          hint="Рамка = кнопка на /v2 (выше, чем раньше). Акцент сверху — object-position: center top."
          onCancel={onCropCancel}
          onConfirm={onCropConfirm}
        />
      ) : null}
    </div>
  );
}
