import { useCallback, useEffect, useMemo, useState } from "react";
import {
  bulkDeletePhotos,
  createBrand,
  fetchAdminPhoto,
  fetchBrands,
  fetchFeedSettings,
  fetchPhotos,
  getRole,
  patchFeedSettings,
  syncPhotosFromObjectStorage,
  fetchTagCatalog,
  putPhotoTags,
  suggestXimilarTags,
} from "../api.js";
import { useHoverPreview } from "../utils/usePhotoHover.jsx";

/** Подписи секций каталога — как на странице «Разметка тегов». */
const SECTION_LABELS = {
  basic: "Базовые",
  style_visual: "Стиль и визуал",
  formality: "Формальность",
  behavioral: "Поведенческие",
};

export default function Photos() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 48;
  const [gender, setGender] = useState("");
  const [brandFilter, setBrandFilter] = useState("");
  const [brands, setBrands] = useState([]);
  const [activeOnly, setActiveOnly] = useState(false);
  const [taggingDoneOnly, setTaggingDoneOnly] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [tagCatalog, setTagCatalog] = useState(null);
  const [modalPhoto, setModalPhoto] = useState(null);
  const [modalErr, setModalErr] = useState("");
  const [modalBrandId, setModalBrandId] = useState("");
  const [quickBrandName, setQuickBrandName] = useState("");
  const [quickBrandBusy, setQuickBrandBusy] = useState(false);
  const [modalMoySkladId, setModalMoySkladId] = useState("");
  const [tagChecked, setTagChecked] = useState({});
  /** Версия тегов на момент открытия модалки — optimistic locking при сохранении. */
  const [modalTagsVersion, setModalTagsVersion] = useState(0);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState({});
  const [deleting, setDeleting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  // Сводка по последнему синку с бакетом (показывается коротким уведомлением
  // под тулбаром, чтобы админ видел: добавилось/удалилось/пропуск по safety).
  const [syncSummary, setSyncSummary] = useState(null);
  const [feedSettings, setFeedSettings] = useState(null);
  const [feedSettingsLoading, setFeedSettingsLoading] = useState(true);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiMessage, setAiMessage] = useState("");
  const [aiDebug, setAiDebug] = useState(null);
  const [aiCopied, setAiCopied] = useState(false);
  /** Ответ Ximilar: варианты по объектам и слияние (tag_ids с бэка). */
  const [ximilarObjects, setXimilarObjects] = useState([]);
  const [ximilarMergedTagIds, setXimilarMergedTagIds] = useState([]);
  const [selectedXimilarIndex, setSelectedXimilarIndex] = useState(0);
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
    });
    setItems(data.items || []);
    setTotal(data.total ?? 0);
  }, [skip, gender, activeOnly, taggingDoneOnly, brandFilter]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const catalog = await fetchTagCatalog();
        if (!c) setTagCatalog(catalog);
      } catch (e) {
        if (!c) setErr(e.message);
      }
      try {
        const br = await fetchBrands();
        if (!c) setBrands(br.items || []);
      } catch (e) {
        /* бренды не должны блокировать каталог тегов */
        if (!c) setErr((prev) => prev || e.message);
      }
      try {
        const fs = await fetchFeedSettings();
        if (!c) setFeedSettings(fs);
      } catch {
        if (!c) setFeedSettings({ require_tagging_review_for_feed: false });
      } finally {
        if (!c) setFeedSettingsLoading(false);
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

  function openModal(p) {
    const m = {};
    for (const pt of p.tags || []) {
      m[pt.tag_id] = true;
    }
    setTagChecked(m);
    setModalBrandId(p.brand_id || "");
    setModalMoySkladId(p.moy_sklad_id != null && p.moy_sklad_id !== "" ? String(p.moy_sklad_id) : "");
    setQuickBrandName("");
    setModalPhoto(p);
    setModalTagsVersion(p.tags_version ?? 0);
    setAiMessage("");
    setAiDebug(null);
    setAiCopied(false);
    setXimilarObjects([]);
    setXimilarMergedTagIds([]);
    setSelectedXimilarIndex(0);
    setModalErr("");
  }

  async function onQuickAddBrandModal(e) {
    e.preventDefault();
    const name = quickBrandName.trim();
    if (!name || quickBrandBusy) return;
    setQuickBrandBusy(true);
    setModalErr("");
    try {
      const created = await createBrand(name);
      setBrands((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name, "ru")));
      setModalBrandId(created.id);
      setQuickBrandName("");
    } catch (ex) {
      setModalErr(ex.message || String(ex));
    } finally {
      setQuickBrandBusy(false);
    }
  }

  async function runXimilarSuggest() {
    if (!modalPhoto || aiBusy) return;
    setAiBusy(true);
    setModalErr("");
    setAiMessage("");
    setAiDebug(null);
    setAiCopied(false);
    try {
      const data = await suggestXimilarTags(modalPhoto.id);
      const objs = data.objects || [];
      setXimilarObjects(objs);
      setXimilarMergedTagIds(data.tag_ids || []);
      setSelectedXimilarIndex(objs[0] ? objs[0].index : 0);

      if (objs.length > 0) {
        setAiMessage(
          `Объектов: ${objs.length}. Выберите нужный и нажмите «Подставить выбранный объект», либо «Подставить слиянием всех».`,
        );
      } else {
        const n = (data.matched || []).length;
        const u = (data.unmapped || []).length;
        setAiMessage(
          n
            ? `Отдельных объектов в ответе нет; слияние даёт ${n} тег(ов) в каталоге` +
                (u ? ` · не сопоставлено полей: ${u}` : "") +
                ". Нажмите «Подставить слиянием всех», если подходит."
            : "Ximilar не сопоставил теги с каталогом (см. JSON ниже).",
        );
      }
      if (data.ximilar && typeof data.ximilar === "object")
        setAiDebug(data.ximilar);
    } catch (e) {
      setModalErr(e.message || String(e));
    } finally {
      setAiBusy(false);
    }
  }

  function applyXimilarSelectedObjectTags() {
    if (!ximilarObjects.length) return;
    const o = ximilarObjects.find((x) => x.index === selectedXimilarIndex);
    if (!o) return;
    const ids = o.tag_ids || [];
    setTagChecked((prev) => {
      const next = { ...prev };
      for (const id of ids) next[id] = true;
      return next;
    });
    setAiMessage(
      `Подставлено по объекту #${o.index + 1} (${o.summary}): ${ids.length} тег(ов) — при необходимости поправьте и «Сохранить».`,
    );
  }

  function applyXimilarMergedTags() {
    const ids = ximilarMergedTagIds || [];
    if (!ids.length) {
      setAiMessage("Нечего подставлять: слияние не дало тегов каталога.");
      return;
    }
    setTagChecked((prev) => {
      const next = { ...prev };
      for (const id of ids) next[id] = true;
      return next;
    });
    setAiMessage(
      `Подставлено слиянием всех объектов: ${ids.length} тег(ов) — при необходимости поправьте и «Сохранить».`,
    );
  }

  async function copyXimilarJson() {
    if (aiDebug == null) return;
    const text = JSON.stringify(aiDebug, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      setAiCopied(true);
      window.setTimeout(() => setAiCopied(false), 2000);
    } catch (e) {
      setModalErr(e.message || String(e));
    }
  }

  async function saveModal() {
    if (!modalPhoto) return;
    setSaving(true);
    setModalErr("");
    try {
      const tags = Object.entries(tagChecked)
        .filter(([, v]) => v)
        .map(([id]) => ({ tag_id: id, weight: 1 }));
      const updated = await putPhotoTags(modalPhoto.id, {
        tags,
        apply_brand: true,
        brand_id: modalBrandId || null,
        moy_sklad_id: modalMoySkladId.trim() || null,
        expected_tags_version: modalTagsVersion,
      });
      setItems((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
      setModalPhoto(null);
    } catch (e) {
      if (e.status === 409) {
        try {
          const fresh = await fetchAdminPhoto(modalPhoto.id);
          const m = {};
          for (const pt of fresh.tags || []) {
            m[pt.tag_id] = true;
          }
          setTagChecked(m);
          setModalPhoto(fresh);
          setModalTagsVersion(fresh.tags_version ?? 0);
          setModalBrandId(fresh.brand_id || "");
          setModalMoySkladId(
            fresh.moy_sklad_id != null && fresh.moy_sklad_id !== ""
              ? String(fresh.moy_sklad_id)
              : "",
          );
          setModalErr(
            "На сервере уже другая версия разметки — форма обновлена актуальными данными. Проверьте теги и сохраните снова.",
          );
        } catch {
          setModalErr(e.message || String(e));
        }
      } else {
        setModalErr(e.message || String(e));
      }
    } finally {
      setSaving(false);
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
    // Бэкенд делает один S3 delete_objects на бакет, но nginx proxy_read_timeout
    // даёт ограниченный бюджет — батчим консервативно, чтобы каждый запрос
    // укладывался в считанные секунды даже на медленной сети до Yandex Cloud.
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
      if (failed.length) {
        setErr(
          failed.map((f) => `${f.id}: ${f.detail || "ошибка"}`).join("\n"),
        );
      }
    } catch (e) {
      // Самый частый кейс — таймаут nginx (HTML 504 → parseResponseJson бросает):
      // на сервере удаление, вероятно, уже идёт/прошло. Чистим выделение оптимистично
      // и обязательно перезагружаем список ниже (в finally), чтобы UI пришёл в порядок.
      setSelected((s) => {
        const n = { ...s };
        for (const id of ids) delete n[id];
        return n;
      });
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

  async function handleSync() {
    if (syncing) return;
    setSyncing(true);
    setErr("");
    setSyncSummary(null);
    try {
      // purge=true: фотки, отсутствующие в бакете, удаляются из БД полностью
      // (а не просто деактивируются), чтобы битые карточки не оставались
      // в списке после ручного удаления объекта из Object Storage.
      const stats = await syncPhotosFromObjectStorage({ purge: true });
      setSkip(0);
      await loadList();
      const m = stats?.male || {};
      const f = stats?.female || {};
      setSyncSummary({
        added: (m.rows_added || 0) + (f.rows_added || 0),
        purged: (m.rows_purged || 0) + (f.rows_purged || 0),
        deactivated: (m.rows_deactivated || 0) + (f.rows_deactivated || 0),
        safetySkip: Boolean(m.safety_skip || f.safety_skip),
        male: m,
        female: f,
      });
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setSyncing(false);
    }
  }

  async function onFeedPolicyChange(checked) {
    if (getRole() !== "superuser") return;
    setErr("");
    try {
      const data = await patchFeedSettings({ require_tagging_review_for_feed: checked });
      setFeedSettings(data);
    } catch (e) {
      setErr(e.message || String(e));
    }
  }

  const canMore = skip + items.length < total;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Фото и теги</h2>
      <div className="feed-policy-card">
        <div className="feed-policy-row">
          <div className="feed-policy-text">
            <strong style={{ color: "var(--text)" }}>В ленту только после разметки.</strong> Если
            выключено — после «Обновить» (синк с бакетом) активные фото попадают в свайпы и без тегов.
            Режим приоритетно для срочных показов; включите обратно, когда нужна только полностью
            размеченная выдача.
            {getRole() !== "superuser" && (
              <span style={{ display: "block", marginTop: "0.25rem" }}>
                Переключает только суперпользователь.
              </span>
            )}
          </div>
          <button
            type="button"
            className="switch-toggle"
            role="switch"
            aria-checked={feedSettings?.require_tagging_review_for_feed ?? false}
            aria-label="В ленту только после разметки"
            disabled={feedSettingsLoading || getRole() !== "superuser"}
            onClick={() => {
              const v = feedSettings?.require_tagging_review_for_feed ?? false;
              onFeedPolicyChange(!v);
            }}
          >
            <span className="switch-thumb" aria-hidden />
          </button>
        </div>
      </div>
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
            checked={allOnPageSelected}
            onChange={toggleSelectAllPage}
          />
          Выбрать все на странице
        </label>
        <button
          type="button"
          className="secondary"
          disabled={syncing || deleting || loading}
          onClick={handleSync}
        >
          {syncing ? "Обновление…" : "Обновить"}
        </button>
        <button
          type="button"
          className="danger"
          disabled={selectedCount === 0 || deleting || syncing}
          onClick={doBulkDelete}
        >
          {deleting
            ? "Удаление…"
            : `Удалить выбранные (${selectedCount})`}
        </button>
      </div>
      {!modalPhoto && err && <p className="error">{err}</p>}
      {!modalPhoto && syncSummary && (
        <p
          style={{
            color: syncSummary.safetySkip ? "#cc3a3a" : "var(--muted)",
            fontSize: "0.9rem",
            margin: "0.25rem 0 0",
          }}
        >
          {syncSummary.safetySkip ? (
            <>
              Sync с бакетом: один из бакетов вернул 0 ключей при наличии записей
              в БД — БД не меняли (предохранитель). Проверь ключи/префиксы YC и
              нажми «Обновить» ещё раз.
            </>
          ) : (
            <>
              Sync с бакетом: добавлено {syncSummary.added}
              {", удалено осиротевших "}{syncSummary.purged}
              {syncSummary.deactivated > 0
                ? `, деактивировано ${syncSummary.deactivated}`
                : ""}
              .
            </>
          )}
        </p>
      )}
      {loading ? (
        <p style={{ color: "var(--muted)" }}>Загрузка…</p>
      ) : (
        <>
          <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
            Показано {items.length} из {total}
            {selectedCount > 0 ? ` · выбрано ${selectedCount}` : ""}
          </p>
          <div className="photo-grid">
            {items.map((p) => (
              <div
                key={p.id}
                className={`photo-cell ${selected[p.id] ? "selected" : ""}`}
                style={{ position: "relative" }}
                {...photoHover.hoverProps(p.url)}
              >
                <span
                  style={{
                    position: "absolute",
                    left: 6,
                    bottom: 6,
                    zIndex: 2,
                    fontSize: "0.7rem",
                    lineHeight: 1.2,
                    padding: "0.2rem 0.35rem",
                    borderRadius: 6,
                    background: p.tagging_review_done
                      ? "rgba(37, 135, 70, 0.9)"
                      : "rgba(176, 131, 31, 0.92)",
                    color: "#fff",
                  }}
                  title={
                    p.tagging_review_done
                      ? "Разметка завершена: фото может участвовать в ленте"
                      : "Разметка не завершена: фото не попадёт в ленту"
                  }
                >
                  {p.tagging_review_done ? "Размечено" : "Без тегов"}
                </span>
                <input
                  type="checkbox"
                  className="pick"
                  checked={!!selected[p.id]}
                  onChange={(e) => togglePick(p.id, e)}
                  onClick={(e) => e.stopPropagation()}
                  title="Выбрать для удаления"
                  aria-label="Выбрать фото"
                />
                <button
                  type="button"
                  className="photo-thumb"
                  onClick={() => openModal(p)}
                  title="Редактировать теги"
                >
                  <img src={p.url} alt="" loading="lazy" />
                </button>
              </div>
            ))}
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

      {modalPhoto && (
        <div className="modal-backdrop" role="presentation" onClick={() => setModalPhoto(null)}>
          <div
            className="modal"
            role="dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ marginTop: 0 }}>Теги для фото</h3>
            {modalPhoto?.claim_expires_at && !modalPhoto?.claim_is_mine ? (
              <p
                style={{
                  margin: "0 0 0.75rem",
                  padding: "0.5rem 0.65rem",
                  borderRadius: 8,
                  borderLeft: "3px solid #b8860b",
                  background: "rgba(184, 134, 11, 0.12)",
                  fontSize: "0.88rem",
                  lineHeight: 1.45,
                }}
              >
                Фото сейчас у другого сотрудника (активная бронь). Вы можете править; при
                одновременном сохранении сработает проверка версии — откроется актуальная разметка с
                сервера.
              </p>
            ) : null}
            <div className="flex-gap" style={{ marginBottom: "0.65rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="secondary"
                disabled={aiBusy || saving}
                onClick={runXimilarSuggest}
                title="Эксперимент: подставить теги через Ximilar (не сохраняет автоматически)"
              >
                {aiBusy ? "AI…" : "AI (Ximilar)"}
              </button>
              {aiMessage ? (
                <span style={{ fontSize: "0.85rem", color: "var(--muted)", alignSelf: "center" }}>
                  {aiMessage}
                </span>
              ) : null}
            </div>
            {ximilarObjects.length > 0 ? (
              <div style={{ marginBottom: "0.75rem", fontSize: "0.88rem" }}>
                <div style={{ fontWeight: 600, marginBottom: "0.35rem" }}>Объекты Ximilar</div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "0.35rem",
                  }}
                >
                  {ximilarObjects.map((o) => (
                    <label
                      key={o.index}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "0.5rem",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="radio"
                        name="ximilar-obj"
                        checked={selectedXimilarIndex === o.index}
                        onChange={() => setSelectedXimilarIndex(o.index)}
                      />
                      <span>
                        <strong>#{o.index + 1}</strong> {o.summary}
                        {typeof o.prob === "number" ? (
                          <span style={{ color: "var(--muted)" }}> · p≈{o.prob.toFixed(2)}</span>
                        ) : null}
                        {Array.isArray(o.matched) ? (
                          <span style={{ color: "var(--muted)" }}> · в каталоге: {o.matched.length}</span>
                        ) : null}
                      </span>
                    </label>
                  ))}
                </div>
                <div className="flex-gap" style={{ marginTop: "0.5rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="secondary"
                    onClick={applyXimilarSelectedObjectTags}
                  >
                    Подставить выбранный объект
                  </button>
                  <button type="button" className="secondary" onClick={applyXimilarMergedTags}>
                    Подставить слиянием всех
                  </button>
                </div>
              </div>
            ) : ximilarMergedTagIds.length > 0 ? (
              <div style={{ marginBottom: "0.75rem" }}>
                <button type="button" className="secondary" onClick={applyXimilarMergedTags}>
                  Подставить слиянием всех
                </button>
              </div>
            ) : null}
            <div style={{ maxHeight: 220, overflow: "auto" }}>
              <img
                src={modalPhoto.url}
                alt=""
                style={{ maxWidth: "100%", maxHeight: 200, objectFit: "contain" }}
              />
            </div>
            {aiDebug != null ? (
              <details
                open
                style={{ marginBottom: "0.75rem", fontSize: "0.78rem", color: "var(--muted)" }}
              >
                <summary style={{ cursor: "pointer" }}>Ответ Ximilar (полный JSON)</summary>
                <div
                  style={{
                    display: "flex",
                    gap: "0.5rem",
                    marginTop: "0.35rem",
                    alignItems: "center",
                    flexWrap: "wrap",
                  }}
                >
                  <button type="button" className="secondary" onClick={copyXimilarJson}>
                    {aiCopied ? "Скопировано" : "Скопировать JSON"}
                  </button>
                </div>
                <pre
                  style={{
                    maxHeight: 360,
                    overflow: "auto",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-all",
                    margin: "0.35rem 0 0",
                    fontSize: "0.72rem",
                  }}
                >
                  {JSON.stringify(aiDebug, null, 2)}
                </pre>
              </details>
            ) : null}
            <div
              style={{
                marginBottom: "0.75rem",
                display: "flex",
                flexWrap: "wrap",
                gap: "0.5rem",
                alignItems: "center",
                fontSize: "0.9rem",
              }}
            >
              <label style={{ display: "flex", gap: "0.35rem", alignItems: "center" }}>
                <span>Бренд</span>
                <select
                  value={modalBrandId}
                  onChange={(e) => setModalBrandId(e.target.value)}
                >
                  <option value="">— не указан —</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
              <span style={{ color: "var(--muted)" }}>или</span>
              <input
                type="text"
                placeholder="Новый бренд"
                value={quickBrandName}
                onChange={(e) => setQuickBrandName(e.target.value)}
                style={{ maxWidth: 180 }}
                disabled={quickBrandBusy}
              />
              <button
                type="button"
                className="secondary"
                disabled={quickBrandBusy}
                onClick={onQuickAddBrandModal}
              >
                {quickBrandBusy ? "…" : "+ В базу"}
              </button>
            </div>
            <div style={{ marginBottom: "0.75rem" }}>
              <label
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "0.3rem",
                  fontSize: "0.9rem",
                  maxWidth: "100%",
                }}
              >
                <span>
                  ID в «МойСклад»{" "}
                  <span style={{ color: "var(--muted)", fontWeight: 400, fontSize: "0.82rem" }}>
                    (вручную; позже можно связать с ERP)
                  </span>
                </span>
                <input
                  type="text"
                  value={modalMoySkladId}
                  onChange={(e) => setModalMoySkladId(e.target.value)}
                  placeholder="например uuid товара в МойСклад"
                  maxLength={128}
                  autoComplete="off"
                  style={{
                    maxWidth: 480,
                    width: "100%",
                    padding: "0.4rem 0.5rem",
                    borderRadius: 6,
                    border: "1px solid var(--border)",
                    background: "var(--background)",
                    color: "var(--text)",
                  }}
                />
              </label>
            </div>
            <div
              className="photos-modal-tag-catalog"
              style={{ maxHeight: "min(52vh, 420px)", overflowY: "auto", marginTop: "0.35rem" }}
            >
              {!tagCatalog?.sections?.length ? (
                <p style={{ color: "var(--muted)", fontSize: "0.88rem", margin: "0.35rem 0" }}>
                  Каталог тегов загружается или недоступен.
                </p>
              ) : (
                tagCatalog.sections.map((section) => (
                  <div key={section.key} style={{ marginBottom: "0.9rem" }}>
                    <div
                      style={{
                        fontSize: "0.68rem",
                        fontWeight: 600,
                        color: "var(--muted)",
                        marginBottom: "0.45rem",
                        textTransform: "uppercase",
                        letterSpacing: "0.06em",
                      }}
                    >
                      {SECTION_LABELS[section.key] || section.key}
                    </div>
                    {section.groups.map((group) => (
                      <div
                        key={group.id}
                        style={{
                          marginBottom: "0.5rem",
                          padding: "0.5rem 0.65rem",
                          borderRadius: 10,
                          border: "1px solid var(--border)",
                          background: "var(--surface)",
                          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.03)",
                        }}
                      >
                        <div
                          style={{
                            fontSize: "0.82rem",
                            fontWeight: 600,
                            marginBottom: "0.4rem",
                            color: "var(--text)",
                          }}
                        >
                          {group.title}
                        </div>
                        {group.subgroups.map((sg, sgIdx) => {
                          const showSubgroupTitle =
                            group.subgroups.length > 1 ||
                            (Boolean(sg.label) && sg.label !== "Теги");
                          return (
                            <div
                              key={`${group.id}-${sg.key ?? "x"}-${sg.label}-${sgIdx}`}
                              style={{ marginBottom: sgIdx < group.subgroups.length - 1 ? "0.5rem" : 0 }}
                            >
                              {showSubgroupTitle ? (
                                <div
                                  style={{
                                    fontSize: "0.72rem",
                                    color: "var(--muted)",
                                    marginBottom: "0.28rem",
                                  }}
                                >
                                  {sg.label}
                                </div>
                              ) : null}
                              <div
                                className="tag-checks"
                                style={{ margin: "0.1rem 0 0", flexWrap: "wrap", gap: "0.45rem" }}
                              >
                                {sg.tags.map((t) => (
                                  <label key={t.id}>
                                    <input
                                      type="checkbox"
                                      checked={!!tagChecked[t.id]}
                                      onChange={(e) =>
                                        setTagChecked((c) => ({
                                          ...c,
                                          [t.id]: e.target.checked,
                                        }))
                                      }
                                    />
                                    {t.name}{" "}
                                    <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
                                      ({group.slug})
                                    </span>
                                  </label>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                ))
              )}
            </div>
            <div className="flex-gap">
              {modalErr ? <p className="error">{modalErr}</p> : null}
              <button type="button" disabled={saving} onClick={saveModal}>
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
              <button type="button" className="secondary" onClick={() => setModalPhoto(null)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      )}
      {photoHover.overlay}
    </div>
  );
}
