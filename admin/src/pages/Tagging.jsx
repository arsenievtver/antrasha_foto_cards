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
import { catalogGroups } from "../utils/tagCatalog.js";

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

function groupSelectionOk(selected, group) {
  return countSelectedInGroup(selected, group) <= group.max_tags;
}

function allCatalogGroupsComplete(catalog, selected) {
  const groups = catalogGroups(catalog);
  if (!groups.length) return false;
  for (const g of groups) {
    if (!groupSelectionOk(selected, g)) return false;
  }
  return true;
}

function allTagsInGroup(group) {
  const out = [];
  for (const sg of group.subgroups || []) {
    for (const t of sg.tags || []) out.push(t);
  }
  return out;
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
  const [newTagByGroup, setNewTagByGroup] = useState({});
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
        if (!c) setCatalog(data);
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

  const catalogGroupList = useMemo(() => catalogGroups(catalog), [catalog]);

  function initFromPhoto(photo) {
    const m = {};
    for (const pt of photo.tags || []) {
      m[pt.tag_id] = true;
    }
    setSelected(m);
    setNewTagByGroup({});
    setSignalLove(!!photo.worker_signal_love);
    setSignalHit(!!photo.worker_signal_hit);
    setSignalHard(!!photo.worker_signal_hard);
    setEditorBrandId(photo.brand_id || "");
    setEditorMoySkladId(
      photo.moy_sklad_id != null && photo.moy_sklad_id !== ""
        ? String(photo.moy_sklad_id)
        : "",
    );
    setQuickBrandName("");
  }

  function toggleTagInGroup(tagId, group) {
    setSelected((s) => {
      if (s[tagId]) {
        return { ...s, [tagId]: false };
      }
      if (countSelectedInGroup(s, group) >= group.max_tags) {
        return s;
      }
      return { ...s, [tagId]: true };
    });
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
      setNewTagByGroup({});
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
    setNewTagByGroup({});
    await loadQueue();
  }

  async function handleAddCustomTag(group) {
    const name = (newTagByGroup[group.id] || "").trim();
    if (!name || busy) return;
    setBusy(true);
    setErr("");
    try {
      const created = await createTagInGroup(group.id, name);
      setNewTagByGroup((prev) => ({ ...prev, [group.id]: "" }));
      await reloadCatalog();
      setSelected((s) => ({ ...s, [created.id]: true }));
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
        Пролистайте группы ниже, нажимайте теги (повторное нажатие снимает выбор). Сохраните, когда
        готово — пустые группы допустимы, но в одной группе нельзя выбрать больше лимита.
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
          onClick={() => !busy && handleCancelEditor()}
        >
          <div
            className="tagging-editor tagging-editor-wide"
            role="dialog"
            aria-label="Разметка фото"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="tagging-editor-img-wrap">
              <img src={editorPhoto.url} alt="" className="tagging-editor-img" />
            </div>
            {editorPhoto?.claim_expires_at && !editorPhoto?.claim_is_mine ? (
              <p className="tagging-claim-hint">
                Фото сейчас у другого сотрудника (активная бронь). Можно продолжать; при конфликте
                версии форма обновится с сервера.
              </p>
            ) : null}
            <div className="tagging-editor-meta-row">
              <label className="tagging-brand-label">
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
                className="tagging-quick-brand-input"
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
            <label className="tagging-moysklad-label">
              <span>
                ID в «МойСклад»{" "}
                <span className="muted tagging-moysklad-hint">(вручную; далее — из ERP)</span>
              </span>
              <input
                type="text"
                value={editorMoySkladId}
                onChange={(e) => setEditorMoySkladId(e.target.value)}
                placeholder="uuid / id в МойСклад"
                maxLength={128}
                autoComplete="off"
                disabled={busy}
              />
            </label>
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

            <div className="tagging-catalog-scroll">
              {catalogGroupList.map((g) => {
                const n = countSelectedInGroup(selected, g);
                const overLimit = n > g.max_tags;
                const atMax = n >= g.max_tags;
                const tags = allTagsInGroup(g);
                const showSubgroupLabels = (g.subgroups || []).length > 1;

                return (
                  <section
                    key={g.id}
                    className={`tagging-catalog-group ${overLimit ? "tagging-catalog-group--over" : ""}`}
                  >
                    <div className="tagging-catalog-group-head">
                      <h3 className="tagging-catalog-group-title">{g.title}</h3>
                      <span className="tagging-catalog-group-meta muted">
                        {n} / до {g.max_tags}
                      </span>
                    </div>
                    {overLimit ? (
                      <p className="tagging-catalog-group-warn">
                        Слишком много тегов — снимите {n - g.max_tags} лишних
                      </p>
                    ) : null}
                    {tags.length === 0 ? (
                      <p className="muted tagging-catalog-empty">В группе пока нет тегов</p>
                    ) : showSubgroupLabels ? (
                      (g.subgroups || []).map((sg, sgIdx) => (
                        <div
                          key={`${g.id}-${sg.key ?? "x"}-${sgIdx}`}
                          className="tagging-catalog-subgroup"
                        >
                          {sg.label && sg.label !== "Теги" ? (
                            <p className="tagging-catalog-subgroup-label">{sg.label}</p>
                          ) : null}
                          <div className="tag-pill-wrap">
                            {(sg.tags || []).map((t) => {
                              const blocked = !selected[t.id] && atMax;
                              return (
                                <button
                                  key={t.id}
                                  type="button"
                                  className={`tag-pill ${selected[t.id] ? "on" : ""} ${blocked ? "tag-pill--blocked" : ""}`}
                                  title={
                                    blocked
                                      ? `Лимит ${g.max_tags} — снимите другой тег в «${g.title}»`
                                      : undefined
                                  }
                                  onClick={() => toggleTagInGroup(t.id, g)}
                                >
                                  {t.name}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="tag-pill-wrap">
                        {tags.map((t) => {
                          const blocked = !selected[t.id] && atMax;
                          return (
                            <button
                              key={t.id}
                              type="button"
                              className={`tag-pill ${selected[t.id] ? "on" : ""} ${blocked ? "tag-pill--blocked" : ""}`}
                              title={
                                blocked
                                  ? `Лимит ${g.max_tags} — снимите другой тег в «${g.title}»`
                                  : undefined
                              }
                              onClick={() => toggleTagInGroup(t.id, g)}
                            >
                              {t.name}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    <div className="tagging-add-custom tagging-add-custom--inline">
                      <input
                        value={newTagByGroup[g.id] || ""}
                        onChange={(e) =>
                          setNewTagByGroup((prev) => ({
                            ...prev,
                            [g.id]: e.target.value,
                          }))
                        }
                        placeholder="Новый тег"
                        maxLength={100}
                        disabled={busy}
                      />
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy || !(newTagByGroup[g.id] || "").trim()}
                        onClick={() => handleAddCustomTag(g)}
                      >
                        +
                      </button>
                    </div>
                  </section>
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
        </div>
      )}
    </div>
  );
}
