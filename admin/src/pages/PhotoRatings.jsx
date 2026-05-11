import { useCallback, useEffect, useState } from "react";
import { fetchBrands, fetchPhotos } from "../api.js";
import { useHoverPreview } from "../utils/usePhotoHover.jsx";

/**
 * Рейтинг фотографий по реакциям.
 *
 * Источник истины — Photo.likes_count / Photo.dislikes_count (см.
 * backend/app/models/photo.py). Счётчики считают уникальные «идентичности»:
 * для зарегистрированного — user_id, для анонимного — session_id.
 * Повторные свайпы той же идентичности не учитываются; переключение
 * (лайк → дизлайк и обратно) меняет сторону.
 *
 * Эта страница только для просмотра — управление фотографиями и тегами
 * остаётся на странице «Фото и теги».
 */

/** Значения должны совпадать с ADMIN_PHOTOS_SORTS в backend/app/routers/admin.py. */
const SORT_OPTIONS = [
  { value: "top_rating", label: "Топ рейтинга (лайки − дизлайки)" },
  { value: "top_likes", label: "Больше всего лайков" },
  { value: "top_dislikes", label: "Больше всего дизлайков" },
  { value: "bottom_rating", label: "Антирейтинг (мин. рейтинг)" },
  { value: "recent", label: "Новые сверху" },
];

export default function PhotoRatings() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 48;
  const [gender, setGender] = useState("");
  const [brandFilter, setBrandFilter] = useState("");
  const [brands, setBrands] = useState([]);
  const [activeOnly, setActiveOnly] = useState(false);
  const [taggingDoneOnly, setTaggingDoneOnly] = useState(false);
  const [sort, setSort] = useState("top_rating");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  /** Фото в модалке — только для просмотра увеличенной версии. */
  const [previewPhoto, setPreviewPhoto] = useState(null);
  const photoHover = useHoverPreview();

  const loadList = useCallback(async () => {
    setErr("");
    const data = await fetchPhotos({
      skip,
      limit,
      gender: gender || undefined,
      activeOnly,
      taggingDoneOnly,
      brandId: brandFilter || undefined,
      sort,
    });
    setItems(data.items || []);
    setTotal(data.total ?? 0);
  }, [skip, gender, activeOnly, taggingDoneOnly, brandFilter, sort]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const br = await fetchBrands();
        if (!c) setBrands(br.items || []);
      } catch (e) {
        if (!c) setErr(e.message);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    let c = false;
    (async () => {
      setLoading(true);
      try {
        await loadList();
      } catch (e) {
        if (!c) setErr(e.message);
      } finally {
        if (!c) setLoading(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [loadList]);

  const canMore = skip + items.length < total;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Рейтинг фото</h2>
      <p
        style={{
          margin: "0 0 0.85rem",
          padding: "0.6rem 0.8rem",
          borderRadius: 8,
          border: "1px solid var(--border)",
          background: "var(--surface)",
          color: "var(--muted)",
          fontSize: "0.88rem",
          lineHeight: 1.45,
          maxWidth: "48rem",
        }}
      >
        Считаются уникальные зрители: для зарегистрированных — пользователь,
        для анонимных — сессия. Повторные свайпы не учитываются; переключение
        (лайк ⇄ дизлайк) меняет сторону. Эта страница — только для оценки
        реакций; теги и удаление — на странице «Фото и теги».
      </p>
      <div className="toolbar">
        <div>
          <label>Пол</label>
          <select
            value={gender}
            onChange={(e) => {
              setSkip(0);
              setGender(e.target.value);
            }}
          >
            <option value="">Все</option>
            <option value="male">male</option>
            <option value="female">female</option>
          </select>
        </div>
        <div>
          <label>Бренд</label>
          <select
            value={brandFilter}
            onChange={(e) => {
              setSkip(0);
              setBrandFilter(e.target.value);
            }}
          >
            <option value="">Все</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>Сортировка</label>
          <select
            value={sort}
            onChange={(e) => {
              setSkip(0);
              setSort(e.target.value);
            }}
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
          <input
            type="checkbox"
            checked={activeOnly}
            onChange={(e) => {
              setSkip(0);
              setActiveOnly(e.target.checked);
            }}
          />
          Только активные
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
          <input
            type="checkbox"
            checked={taggingDoneOnly}
            onChange={(e) => {
              setSkip(0);
              setTaggingDoneOnly(e.target.checked);
            }}
          />
          Только размеченные
        </label>
      </div>
      {err && <p className="error">{err}</p>}
      {loading ? (
        <p style={{ color: "var(--muted)" }}>Загрузка…</p>
      ) : (
        <>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
            Показано {items.length} из {total}
          </p>
          <div className="photo-grid">
            {items.map((p) => {
              const likes = p.likes_count ?? 0;
              const dislikes = p.dislikes_count ?? 0;
              const rating = likes - dislikes;
              return (
                <div
                  key={p.id}
                  className="photo-cell"
                  style={{ position: "relative" }}
                  {...photoHover.hoverProps(p.url)}
                >
                  <span
                    style={{
                      position: "absolute",
                      left: 6,
                      top: 6,
                      zIndex: 2,
                      fontSize: "0.72rem",
                      lineHeight: 1.2,
                      padding: "0.22rem 0.4rem",
                      borderRadius: 6,
                      background:
                        rating > 0
                          ? "rgba(37, 135, 70, 0.92)"
                          : rating < 0
                            ? "rgba(176, 56, 56, 0.92)"
                            : "rgba(60, 64, 72, 0.92)",
                      color: "#fff",
                      fontWeight: 600,
                      fontVariantNumeric: "tabular-nums",
                    }}
                    title={`Рейтинг (лайки − дизлайки): ${rating >= 0 ? "+" : ""}${rating}`}
                  >
                    {rating > 0 ? "+" : ""}
                    {rating}
                  </span>
                  <span
                    style={{
                      position: "absolute",
                      right: 6,
                      bottom: 6,
                      zIndex: 2,
                      fontSize: "0.72rem",
                      lineHeight: 1.2,
                      padding: "0.22rem 0.45rem",
                      borderRadius: 6,
                      background: "rgba(20, 22, 28, 0.82)",
                      color: "#fff",
                      display: "inline-flex",
                      gap: "0.45rem",
                      alignItems: "center",
                      fontVariantNumeric: "tabular-nums",
                    }}
                    title={`Лайков: ${likes} · Дизлайков: ${dislikes}`}
                  >
                    <span style={{ color: "#7fdf9b" }}>+{likes}</span>
                    <span style={{ color: "#f08a8a" }}>−{dislikes}</span>
                  </span>
                  <button
                    type="button"
                    className="photo-thumb"
                    onClick={() => setPreviewPhoto(p)}
                    title="Открыть превью"
                  >
                    <img src={p.url} alt="" loading="lazy" />
                  </button>
                </div>
              );
            })}
          </div>
          <div className="flex-gap" style={{ marginTop: "1rem" }}>
            <button
              type="button"
              className="secondary"
              disabled={skip === 0}
              onClick={() => setSkip((s) => Math.max(0, s - limit))}
            >
              Назад
            </button>
            <button
              type="button"
              className="secondary"
              disabled={!canMore}
              onClick={() => setSkip((s) => s + limit)}
            >
              Дальше
            </button>
          </div>
        </>
      )}

      {previewPhoto && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => setPreviewPhoto(null)}
        >
          <div
            className="modal"
            role="dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginTop: 0 }}>Реакции на фото</h3>
            <div style={{ maxHeight: 360, overflow: "auto" }}>
              <img
                src={previewPhoto.url}
                alt=""
                style={{
                  maxWidth: "100%",
                  maxHeight: 340,
                  objectFit: "contain",
                }}
              />
            </div>
            {(() => {
              const likes = previewPhoto.likes_count ?? 0;
              const dislikes = previewPhoto.dislikes_count ?? 0;
              const rating = likes - dislikes;
              return (
                <div
                  style={{
                    display: "flex",
                    gap: "0.6rem",
                    flexWrap: "wrap",
                    alignItems: "center",
                    fontSize: "0.92rem",
                    margin: "0.6rem 0 0.4rem",
                    padding: "0.5rem 0.7rem",
                    borderRadius: 8,
                    border: "1px solid var(--border)",
                    background: "var(--surface)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  <span>
                    Лайков:{" "}
                    <strong style={{ color: "#3aa157" }}>{likes}</strong>
                  </span>
                  <span>
                    Дизлайков:{" "}
                    <strong style={{ color: "#c75252" }}>{dislikes}</strong>
                  </span>
                  <span>
                    Рейтинг:{" "}
                    <strong>
                      {rating > 0 ? "+" : ""}
                      {rating}
                    </strong>
                  </span>
                  {previewPhoto.brand ? (
                    <span style={{ color: "var(--muted)" }}>
                      Бренд: {previewPhoto.brand}
                    </span>
                  ) : null}
                  <span style={{ color: "var(--muted)" }}>
                    Пол: {previewPhoto.gender}
                  </span>
                </div>
              );
            })()}
            <div className="flex-gap">
              <button
                type="button"
                className="secondary"
                onClick={() => setPreviewPhoto(null)}
              >
                Закрыть
              </button>
            </div>
          </div>
        </div>
      )}
      {photoHover.overlay}
    </div>
  );
}
