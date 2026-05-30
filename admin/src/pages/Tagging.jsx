import { useCallback, useEffect, useMemo, useState } from "react";
import {
  acquireNextTaggingPhoto,
  claimTaggingPhoto,
  createBrand,
  createTagInGroup,
  fetchAdminPhoto,
  fetchBrands,
  fetchTagCatalog,
  fetchTaggingQueue,
  getRole,
  putPhotoTags,
  releaseTaggingPhoto,
} from "../api.js";

const SECTION_LABELS = {
  basic: "Базовые",
  style_visual: "Стиль и визуал",
  formality: "Формальность",
  behavioral: "Поведенческие",
};

function countSelectedInGroup(selected, group) {
  const ids = new Set();
  for (const sg of group.subgroups || []) {
    for (const t of sg.tags || []) {
      ids.add(t.id);
    }
  }
  let n = 0;
  for (const id of ids) {
    if (selected[id]) n += 1;
  }
  return n;
}

/** В пределах нормы — можно сохранять по этой группе (лимит max, минимум не требуется). */
function groupSelectionOk(selected, group) {
  const n = countSelectedInGroup(selected, group);
  return n <= group.max_tags;
}

/** Галочка: в норме или при превышении max (чтобы было видно, что группа «заполнена», даже если нужно убрать лишнее). */
function groupShowsGreenCheck(selected, group) {
  const n = countSelectedInGroup(selected, group);
  if (n > group.max_tags) return true;
  return groupSelectionOk(selected, group);
}

function allCatalogGroupsComplete(catalog, selected) {
  if (!catalog?.sections?.length) return false;
  for (const sec of catalog.sections) {
    for (const g of sec.groups || []) {
      if (!groupSelectionOk(selected, g)) return false;
    }
  }
  return true;
}

function groupHintText(g) {
  return `до ${g.max_tags} тег(ов)`;
}

export default function Tagging() {
  const role = getRole();
  const [queue, setQueue] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 24;
  const [catalog, setCatalog] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [editorPhoto, setEditorPhoto] = useState(null);
  const [selected, setSelected] = useState({});
  const [sectionKey, setSectionKey] = useState("");
  const [groupModal, setGroupModal] = useState(null);
  const [subgroupIdx, setSubgroupIdx] = useState(0);
  const [newTagName, setNewTagName] = useState("");
  const [signalLove, setSignalLove] = useState(false);
  const [signalHit, setSignalHit] = useState(false);
  const [signalHard, setSignalHard] = useState(false);
  const [brands, setBrands] = useState([]);
  const [editorBrandId, setEditorBrandId] = useState("");
  const [quickBrandName, setQuickBrandName] = useState("");
  const [quickBrandBusy, setQuickBrandBusy] = useState(false);
  const [editorMoySkladId, setEditorMoySkladId] = useState("");
  const [clock, setClock] = useState(Date.now());

  const canSave = useMemo(
    () => allCatalogGroupsComplete(catalog, selected),
    [catalog, selected],
  );

  /** Не даём странице под модалкой скроллиться (в т.ч. iOS Safari). */
  useEffect(() => {
    if (!editorPhoto) return undefined;
    const scrollY = window.scrollY;
    const html = document.documentElement;
    const body = document.body;
    html.style.overflow = "hidden";
    body.style.overflow = "hidden";
    body.style.position = "fixed";
    body.style.top = `-${scrollY}px`;
    body.style.left = "0";
    body.style.right = "0";
    body.style.width = "100%";

    return () => {
      html.style.overflow = "";
      body.style.overflow = "";
      body.style.position = "";
      body.style.top = "";
      body.style.left = "";
      body.style.right = "";
      body.style.width = "";
      window.scrollTo(0, scrollY);
    };
  }, [editorPhoto]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const data = await fetchTagCatalog();
        if (!c) {
          setCatalog(data);
          if (data.sections?.length) setSectionKey(data.sections[0].key);
        }
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
      try {
        const data = await fetchBrands();
        if (!c) setBrands(data.items || []);
      } catch (e) {
        if (!c) setErr(e.message);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    if (!editorPhoto?.claim_expires_at || role !== "worker") return undefined;
    const id = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(id);
  }, [editorPhoto, role]);

  const displaySeconds =
    editorPhoto?.claim_expires_at && role === "worker"
      ? Math.max(
          0,
          Math.floor(
            (new Date(editorPhoto.claim_expires_at).getTime() - clock) / 1000,
          ),
        )
      : null;

  /** Лимит выбора в открытой модалке группы — блокируем лишние теги до сохранения. */
  const modalPickStats = useMemo(() => {
    if (!groupModal) return { n: 0, atMax: false };
    const n = countSelectedInGroup(selected, groupModal);
    return { n, atMax: n >= groupModal.max_tags };
  }, [groupModal, selected]);

  const loadQueue = useCallback(
    async (opts) => {
      setErr("");
      const s = opts?.skip !== undefined ? opts.skip : skip;
      const data = await fetchTaggingQueue({ skip: s, limit });
      setQueue(data.items || []);
      setTotal(data.total ?? 0);
    },
    [skip, limit],
  );

  useEffect(() => {
    let c = false;
    (async () => {
      setLoading(true);
      try {
        await loadQueue();
      } catch (e) {
        if (!c) setErr(e.message);
      } finally {
        if (!c) setLoading(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [loadQueue]);

  const currentSection = useMemo(() => {
    if (!catalog?.sections?.length) return null;
    return catalog.sections.find((s) => s.key === sectionKey) || catalog.sections[0];
  }, [catalog, sectionKey]);

  function initFromPhoto(photo) {
    const m = {};
    for (const pt of photo.tags || []) {
      m[pt.tag_id] = true;
    }
    setSelected(m);
    setSignalLove(!!photo.worker_signal_love);
    setSignalHit(!!photo.worker_signal_hit);
    setSignalHard(!!photo.worker_signal_hard);
    setEditorBrandId(photo.brand_id || "");
    setEditorMoySkladId(photo.moy_sklad_id != null && photo.moy_sklad_id !== "" ? String(photo.moy_sklad_id) : "");
    setQuickBrandName("");
  }

  async function onQuickAddBrandEditor(e) {
    e.preventDefault();
    const name = quickBrandName.trim();
    if (!name || quickBrandBusy) return;
    setQuickBrandBusy(true);
    setErr("");
    try {
      const created = await createBrand(name);
      setBrands((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name, "ru")));
      setEditorBrandId(created.id);
      setQuickBrandName("");
    } catch (ex) {
      setErr(ex.message ?? String(ex));
    } finally {
      setQuickBrandBusy(false);
    }
  }

  async function reloadCatalog() {
    const data = await fetchTagCatalog();
    setCatalog(data);
  }

  async function openEditor(photo, { claimFirst } = { claimFirst: false }) {
    setErr("");
    setGroupModal(null);
    setNewTagName("");
    if (!claimFirst || role !== "worker") {
      setEditorPhoto(photo);
      initFromPhoto(photo);
      return;
    }
    setBusy(true);
    try {
      const p = await claimTaggingPhoto(photo.id);
      setEditorPhoto(p);
      initFromPhoto(p);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleAcquireNext() {
    setErr("");
    setBusy(true);
    setGroupModal(null);
    try {
      const p = await acquireNextTaggingPhoto();
      setEditorPhoto(p);
      initFromPhoto(p);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  function toggleTag(id) {
    setSelected((s) => ({ ...s, [id]: !s[id] }));
  }

  async function handleSave() {
    if (!editorPhoto || !canSave) return;
    const tags = Object.entries(selected)
      .filter(([, v]) => v)
      .map(([id]) => ({ tag_id: id, weight: 1 }));
    const photoId = editorPhoto.id;
    setBusy(true);
    setErr("");
    try {
      await putPhotoTags(String(photoId), {
        tags,
        worker_signal_love: signalLove || null,
        worker_signal_hit: signalHit || null,
        worker_signal_hard: signalHard || null,
        apply_brand: true,
        brand_id: editorBrandId || null,
        moy_sklad_id: editorMoySkladId.trim() || null,
        expected_tags_version: editorPhoto.tags_version ?? 0,
      });
      setEditorPhoto(null);
      setSelected({});
      setGroupModal(null);
      setSkip(0);
    } catch (e) {
      if (e.status === 409) {
        try {
          const fresh = await fetchAdminPhoto(photoId);
          setEditorPhoto(fresh);
          initFromPhoto(fresh);
          setErr(
            "На сервере уже другая версия разметки — форма обновлена. Проверьте теги и сохраните снова.",
          );
        } catch {
          setErr(e.message ?? String(e));
        }
      } else {
        setErr(e.message ?? String(e));
      }
    } finally {
      setBusy(false);
    }
    try {
      await loadQueue({ skip: 0 });
      await reloadCatalog();
    } catch (e) {
      setErr((prev) => prev || e.message || "Не удалось обновить очередь");
    }
  }

  async function handleCancelEditor() {
    if (!editorPhoto) return;
    setErr("");
    try {
      if (role === "worker" && editorPhoto.claim_is_mine) {
        await releaseTaggingPhoto(editorPhoto.id);
      }
    } catch (e) {
      setErr(e.message);
    }
    setEditorPhoto(null);
    setSelected({});
    setGroupModal(null);
    await loadQueue();
  }

  async function handleAddCustomTag() {
    if (!groupModal || !newTagName.trim()) return;
    setBusy(true);
    setErr("");
    try {
      await createTagInGroup(groupModal.id, newTagName.trim());
      setNewTagName("");
      await reloadCatalog();
      const fresh = await fetchTagCatalog();
      const gid = groupModal.id;
      let nextGroup = null;
      for (const sec of fresh.sections || []) {
        const g = (sec.groups || []).find((x) => x.id === gid);
        if (g) {
          nextGroup = g;
          break;
        }
      }
      if (nextGroup) setGroupModal(nextGroup);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const canMore = skip + queue.length < total;

  return (
    <div className="tagging-page">
      <h2 className="tagging-title">Разметка тегов</h2>
      <p className="tagging-lead">
        Отмечайте теги по группам в пределах лимита. Группы можно оставить пустыми — сохранение
        доступно, если нигде не превышен максимум.
      </p>

      {err && <p className="error">{err}</p>}

      <div className="tagging-actions">
        <button type="button" disabled={busy} onClick={handleAcquireNext}>
          {busy ? "…" : role === "worker" ? "Следующее фото" : "Взять фото из очереди"}
        </button>
      </div>

      {loading ? (
        <p className="muted">Загрузка очереди…</p>
      ) : (
        <>
          <p className="muted tagging-meta">
            В очереди: {total} · показано {queue.length}
          </p>
          <div className="tagging-grid">
            {queue.map((p) => (
              <div key={p.id}>
                <button
                  type="button"
                  className="tagging-thumb"
                  onClick={() => openEditor(p, { claimFirst: role === "worker" })}
                  disabled={busy}
                >
                  <img src={p.url} alt="" loading="lazy" />
                  {p.claim_expires_at && !p.claim_is_mine && (
                    <span className="tagging-thumb-busy">занято</span>
                  )}
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

      {editorPhoto && !catalog && (
        <div className="tagging-editor-backdrop" role="alert">
          <div className="tagging-editor tagging-editor-wide">
            <p className="muted">Загрузка каталога тегов…</p>
          </div>
        </div>
      )}

      {editorPhoto && catalog && (
        <div
          className="tagging-editor-backdrop"
          role="presentation"
          onClick={() => !busy && !groupModal && handleCancelEditor()}
        >
          <div
            className="tagging-editor tagging-editor-wide"
            role="dialog"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="tagging-editor-img-wrap">
              <img src={editorPhoto.url} alt="" className="tagging-editor-img" />
            </div>
            {editorPhoto?.claim_expires_at && !editorPhoto?.claim_is_mine ? (
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
                Фото сейчас у другого сотрудника (активная бронь). Можно продолжать; при конфликте
                версии форма обновится с сервера.
              </p>
            ) : null}
            <div
              style={{
                marginBottom: "0.65rem",
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
                  value={editorBrandId}
                  onChange={(e) => setEditorBrandId(e.target.value)}
                >
                  <option value="">— не указан —</option>
                  {brands.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              </label>
              <span className="muted">или</span>
              <input
                type="text"
                placeholder="Новый бренд"
                value={quickBrandName}
                onChange={(e) => setQuickBrandName(e.target.value)}
                style={{ maxWidth: 180 }}
                disabled={quickBrandBusy || busy}
              />
              <button
                type="button"
                className="secondary"
                disabled={quickBrandBusy || busy}
                onClick={onQuickAddBrandEditor}
              >
                {quickBrandBusy ? "…" : "+ В базу"}
              </button>
            </div>
            <div style={{ marginBottom: "0.65rem" }}>
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
                  <span className="muted" style={{ fontWeight: 400, fontSize: "0.82rem" }}>
                    (вручную; далее — из ERP)
                  </span>
                </span>
                <input
                  type="text"
                  value={editorMoySkladId}
                  onChange={(e) => setEditorMoySkladId(e.target.value)}
                  placeholder="uuid / id в МойСклад"
                  maxLength={128}
                  autoComplete="off"
                  disabled={busy}
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
            {displaySeconds != null && (
              <p className="tagging-timer">
                Бронь: {Math.floor(displaySeconds / 60)}:
                {String(displaySeconds % 60).padStart(2, "0")}
              </p>
            )}

            <p className="muted tagging-signals-label">Быстрая оценка</p>
            <div className="tagging-signals">
              <button
                type="button"
                className={`tagging-signal ${signalLove ? "on" : ""}`}
                onClick={() => setSignalLove((x) => !x)}
              >
                👍 своё
              </button>
              <button
                type="button"
                className={`tagging-signal ${signalHit ? "on" : ""}`}
                onClick={() => setSignalHit((x) => !x)}
              >
                🔥 хит
              </button>
              <button
                type="button"
                className={`tagging-signal ${signalHard ? "on" : ""}`}
                onClick={() => setSignalHard((x) => !x)}
              >
                ❗ сложная вещь
              </button>
            </div>

            <div className="tagging-section-tabs" role="tablist">
              {(catalog.sections || []).map((sec) => (
                <button
                  key={sec.key}
                  type="button"
                  role="tab"
                  className={`tag-type-tab ${sectionKey === sec.key ? "active" : ""}`}
                  onClick={() => setSectionKey(sec.key)}
                >
                  {SECTION_LABELS[sec.key] || sec.key}
                </button>
              ))}
            </div>

            <div className="tagging-group-grid">
              {(currentSection?.groups || []).map((g) => {
                const n = countSelectedInGroup(selected, g);
                const ok = groupSelectionOk(selected, g);
                const overLimit = n > g.max_tags;
                const showCheck = groupShowsGreenCheck(selected, g);
                return (
                  <button
                    key={g.id}
                    type="button"
                    className={`tagging-group-card ${ok ? "tagging-group-card--ok" : ""} ${overLimit ? "tagging-group-card--over" : ""}`}
                    onClick={() => {
                      setGroupModal(g);
                      setSubgroupIdx(0);
                      setNewTagName("");
                    }}
                  >
                    <span className="tagging-group-card-head">
                      <span className="tagging-group-card-title">{g.title}</span>
                      {showCheck ? (
                        <span className="tagging-group-check" aria-hidden>
                          ✓
                        </span>
                      ) : null}
                    </span>
                    <span className="tagging-group-card-meta">
                      {n} выбрано · {groupHintText(g)}
                      {overLimit ? " · сверх нормы" : ""}
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="tagging-editor-actions">
              <button
                type="button"
                disabled={busy || !canSave}
                onClick={handleSave}
                title={
                  !canSave
                    ? "Уберите лишние теги в группах, где превышен максимум"
                    : undefined
                }
              >
                {busy ? "…" : "Сохранить"}
              </button>
              <button
                type="button"
                className="secondary"
                disabled={busy}
                onClick={handleCancelEditor}
              >
                {role === "worker" ? "Отказаться" : "Закрыть"}
              </button>
            </div>
          </div>

          {groupModal && (
            <div
              className="tagging-group-modal-overlay"
              role="presentation"
              onClick={(e) => {
                e.stopPropagation();
                setGroupModal(null);
              }}
            >
              <div
                className="tagging-group-modal"
                role="dialog"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 className="tagging-group-modal-title">{groupModal.title}</h3>
                <p className="muted">Не больше {groupModal.max_tags} тег(ов) в этой группе</p>
                {(groupModal.subgroups || []).length > 1 && (
                  <div className="tag-type-tabs" role="tablist">
                    {(groupModal.subgroups || []).map((sg, i) => (
                      <button
                        key={sg.key ?? "flat"}
                        type="button"
                        className={`tag-type-tab ${subgroupIdx === i ? "active" : ""}`}
                        onClick={() => setSubgroupIdx(i)}
                      >
                        {sg.label}
                      </button>
                    ))}
                  </div>
                )}
                <div className="tag-pill-wrap">
                  {((groupModal.subgroups || [])[subgroupIdx]?.tags || []).map((t) => {
                    const blocked = !selected[t.id] && modalPickStats.atMax;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        className={`tag-pill ${selected[t.id] ? "on" : ""} ${blocked ? "tag-pill--blocked" : ""}`}
                        title={
                          blocked
                            ? "Лимит тегов для этой группы — снимите выделение с другого тега"
                            : undefined
                        }
                        onClick={() => {
                          if (selected[t.id]) {
                            toggleTag(t.id);
                            return;
                          }
                          if (modalPickStats.atMax) return;
                          toggleTag(t.id);
                        }}
                      >
                        {t.name}
                      </button>
                    );
                  })}
                </div>
                {modalPickStats.atMax ? (
                  <p className="muted" style={{ fontSize: "0.82rem", marginBottom: "0.65rem" }}>
                    Выбрано максимум ({groupModal.max_tags}) для «{groupModal.title}». Снимите отметку с
                    тега, чтобы выбрать другой.
                  </p>
                ) : null}
                <div className="tagging-add-custom">
                  <input
                    value={newTagName}
                    onChange={(e) => setNewTagName(e.target.value)}
                    placeholder="Новый тег для группы"
                    maxLength={100}
                  />
                  <button
                    type="button"
                    className="secondary"
                    disabled={busy || !newTagName.trim()}
                    onClick={handleAddCustomTag}
                  >
                    + Добавить
                  </button>
                </div>
                <button
                  type="button"
                  className="secondary tagging-group-modal-close"
                  onClick={() => setGroupModal(null)}
                >
                  Готово
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
