import { useCallback, useEffect, useMemo, useState } from "react";
import { bulkDeletePhotos, fetchBrands, fetchPhotos } from "../api.js";
import { useHoverPreview } from "../utils/usePhotoHover.jsx";

/**
 * Рейтинг фотографий по реакциям.
 *
 * Источник истины — Photo.likes_count / Photo.dislikes_count (см.
 * backend/app/models/photo.py). Счётчики считают уникальные «идентичности»:
 * для зарегистрированного — user_id, для анонимного — session_id.
 * Повторные свайпы той же идентичности не учитываются; переключение
 * (лайк → дизлайк и обратно) меняет сторону.
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
  const [noReactionsOnly, setNoReactionsOnly] = useState(false);
  const [sort, setSort] = useState("top_rating");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [previewPhoto, setPreviewPhoto] = useState(null);
  const [selected, setSelected] = useState({});
  const [deleting, setDeleting] = useState(false);
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
      noReactionsOnly,
      sort,
    });
    setItems(data.items || []);
    setTotal(data.total ?? 0);
  }, [skip, gender, activeOnly, taggingDoneOnly, brandFilter, noReactionsOnly, sort]);

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

  const selectedCount = useMemo(
    () => Object.values(selected).filter(Boolean).length,
    [selected],
  );

  const allOnPageSelected =
    items.length > 0 && items.every((p) => selected[p.id]);

  function togglePick(id, e) {
    e.stopPropagation();
    setSelected((s) => ({ ...s, [id]: !s[id] }));
  }

  function toggleSelectAllPage() {
    if (allOnPageSelected) {
      setSelected((s) => {
        const n = { ...s };
        for (const p of items) {
          delete n[p.id];
        }
        return n;
      });
    } else {
      setSelected((s) => {
        const n = { ...s };
        for (const p of items) {
          n[p.id] = true;
        }
        return n;
      });
    }
  }

  async function doBulkDelete() {
    const ids = Object.entries(selected)
      .filter(([, v]) => v)
      .map(([id]) => id);
    if (ids.length === 0) return;
    if (
      !confirm(
        `Удалить ${ids.length} фото? Записи в БД будут удалены; файлы в Object Storage — если URL относится к вашим бакетам и заданы ключи S3.`,
      )
    ) {
      return;
    }
    setDeleting(true);
    setErr("");
    const batchSize = 50;
    try {
      const allResults = [];
      for (let i = 0; i < ids.length; i += batchSize) {
        const chunk = ids.slice(i, i + batchSize);
        const data = await bulkDeletePhotos(chunk);
        allResults.push(...(data.results || []));
      }
      const failed = allResults.filter((r) => !r.ok);
      setSelected((s) => {
        const n = { ...s };
        for (const r of allResults) {
          if (r.ok) delete n[r.id];
        }
        return n;
      });
      if (previewPhoto && allResults.some((r) => r.ok && r.id === previewPhoto.id)) {
        setPreviewPhoto(null);
      }
      if (failed.length) {
        setErr(
          failed.map((f) => `${f.id}: ${f.detail || "ошибка"}`).join("\n"),
        );
      }
    } catch (e) {
      setSelected((s) => {
        const n = { ...s };
        for (const id of ids) delete n[id];
        return n;
      });
      setPreviewPhoto(null);
      setErr(
        `Не удалось дождаться ответа сервера: ${e.message || e}. ` +
          "Часть фото могла быть уже удалена — список обновлён.",
      );
    } finally {
      try {
        await loadList();
      } catch (e2) {
        setErr((prev) => prev || e2.message || String(e2));
      }
      setDeleting(false);
    }
  }

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
        (лайк ⇄ дизлайк) меняет сторону. Можно отмечать фото и удалять пакетом
        (как на «Фото и теги»); фильтр «Без реакций» — для нерейтинговых
        карточек. Разметка тегов — на странице «Фото и теги».
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
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
          <input
            type="checkbox"
            checked={noReactionsOnly}
            onChange={(e) => {
              setSkip(0);
              setNoReactionsOnly(e.target.checked);
            }}
          />
          Без реакций
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
          <input
            type="checkbox"
            checked={allOnPageSelected}
            onChange={toggleSelectAllPage}
            disabled={items.length === 0 || deleting || loading}
          />
          Выбрать все на странице
        </label>
        <button
          type="button"
          className="danger"
          disabled={selectedCount === 0 || deleting || loading}
          onClick={doBulkDelete}
        >
          {deleting
            ? "Удаление…"
            : `Удалить выбранные (${selectedCount})`}
        </button>
      </div>
      {err && <p className="error">{err}</p>}
      {loading ? (
        <p style={{ color: "var(--muted)" }}>Загрузка…</p>
      ) : (
        <>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
            Показано {items.length} из {total}
            {selectedCount > 0 ? ` · выбрано ${selectedCount}` : ""}
          </p>
          <div className="photo-grid">
            {items.map((p) => {
              const likes = p.likes_count ?? 0;
              const dislikes = p.dislikes_count ?? 0;
              const rating = likes - dislikes;
              return (
                <div
                  key={p.id}
                  className={`photo-cell ${selected[p.id] ? "selected" : ""}`}
                  style={{ position: "relative" }}
                  {...photoHover.hoverProps(p.url)}
                >
                  <input
                    type="checkbox"
                    className="pick"
                    checked={!!selected[p.id]}
                    onChange={(e) => togglePick(p.id, e)}
                    onClick={(e) => e.stopPropagation()}
                    title="Выбрать для удаления"
                    aria-label="Выбрать фото"
                  />
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
