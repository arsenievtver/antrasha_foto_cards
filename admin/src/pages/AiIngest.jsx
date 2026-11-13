import { useCallback, useEffect, useRef, useState } from "react";
import {
  createBrand,
  deleteAiIngestJob,
  enqueueAiIngestInbox,
  fetchAiIngestJobSource,
  fetchAiIngestJobs,
  fetchAiIngestLimits,
  fetchAiIngestReleaseDraft,
  fetchAiIngestStats,
  fetchBrands,
  fetchFeedSettings,
  publishAiIngestRelease,
  retryAiIngestJob,
  retryAiIngestMoySklad,
  uploadAiIngestBatch,
} from "../api.js";

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

const STAGE_LABELS = {
  upload: "Отправка исходника",
  submit: "Заказ в Fashn",
  generating: "Fashn генерирует",
  download: "Скачивание результата",
  save: "Сохранение",
};

const statusLabel = (s, stage) => {
  if (s === "pending") return "В очереди";
  if (s === "processing") return STAGE_LABELS[stage] || "Обработка";
  if (s === "completed") return "Готово";
  if (s === "failed") return "Ошибка";
  return s;
};

const sourceModeLabel = (m) => {
  if (m === "look" || m === "on_model") return "Образ в сборе";
  if (m === "single" || m === "flatlay") return "Одна вещь";
  return m || "—";
};

function productLinesLabel(j) {
  const lines = [];
  const main = j.article || j.product_name;
  if (main || j.barcode) {
    lines.push([main, j.barcode].filter(Boolean).join(" · "));
  }
  for (const lp of j.linked_products || []) {
    const bit = [lp.article, lp.name, lp.barcode].filter(Boolean).join(" · ");
    if (bit) lines.push(bit);
  }
  if (lines.length > 1) return `Комплект (${lines.length}): ${lines.join("; ")}`;
  return lines[0] || j.product_name || j.original_filename || "—";
}

export default function AiIngest() {
  const [limits, setLimits] = useState(null);
  const [stats, setStats] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 40;
  const [gender, setGender] = useState("male");
  const [sourceMode, setSourceMode] = useState("single");
  const [brands, setBrands] = useState([]);
  const [brandId, setBrandId] = useState("");
  const [showBadge, setShowBadge] = useState(false);
  const [badgeLabel, setBadgeLabel] = useState("");
  const [quickBrandName, setQuickBrandName] = useState("");
  const [quickBrandBusy, setQuickBrandBusy] = useState(false);
  const [files, setFiles] = useState([]);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [releaseDraft, setReleaseDraft] = useState(null);
  const [publishBusy, setPublishBusy] = useState(false);
  const [inbox, setInbox] = useState([]);
  const [inboxMode, setInboxMode] = useState("single");
  const [inboxBadge, setInboxBadge] = useState(false);
  const [picked, setPicked] = useState({});
  const [selected, setSelected] = useState(() => new Set());
  const [enqueueBusy, setEnqueueBusy] = useState(false);
  const [thumbs, setThumbs] = useState({});
  const thumbsRef = useRef({});
  const fileInputRef = useRef(null);

  const loadJobs = useCallback(async () => {
    setErr("");
    const data = await fetchAiIngestJobs({ skip, limit, queue: "fashn" });
    setItems(data.items || []);
    setTotal(data.total ?? 0);
  }, [skip, limit]);

  /** Тихое обновление списка и счётчиков без сброса ошибки (для опроса в фоне). */
  const loadReleaseDraft = useCallback(async () => {
    try {
      const d = await fetchAiIngestReleaseDraft(gender);
      setReleaseDraft(d);
    } catch {
      setReleaseDraft(null);
    }
  }, [gender]);

  const pollQueue = useCallback(async () => {
    try {
      const [st, data, lim, draft, phone] = await Promise.all([
        fetchAiIngestStats(),
        fetchAiIngestJobs({ skip, limit, queue: "fashn" }),
        fetchAiIngestLimits(),
        fetchAiIngestReleaseDraft(gender),
        fetchAiIngestJobs({ skip: 0, limit: 200, queue: "inbox" }),
      ]);
      setStats(st);
      setItems(data.items || []);
      setTotal(data.total ?? 0);
      setLimits(lim);
      setReleaseDraft(draft);
      setInbox(phone.items || []);
    } catch {
      /* сеть / сессия — не показываем при каждом тике */
    }
  }, [skip, limit, gender]);

  const loadBrands = useCallback(async () => {
    const data = await fetchBrands();
    setBrands(data.items || []);
  }, []);

  const refreshMeta = useCallback(async () => {
    try {
      const [lim, st] = await Promise.all([fetchAiIngestLimits(), fetchAiIngestStats()]);
      setLimits(lim);
      setStats(st);
    } catch (e) {
      setErr(e.message);
    }
  }, []);

  useEffect(() => {
    let c = false;
    (async () => {
      setLoading(true);
      try {
        if (skip === 0) {
          await Promise.all([refreshMeta(), loadBrands()]);
        }
        await Promise.all([
          loadJobs(),
          fetchAiIngestJobs({ skip: 0, limit: 200, queue: "inbox" }).then((phone) => {
            if (!c) setInbox(phone.items || []);
          }),
        ]);
      } catch (e) {
        if (!c) setErr(e.message);
      } finally {
        if (!c) setLoading(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [loadBrands, loadJobs, refreshMeta, skip]);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const fs = await fetchFeedSettings();
        if (!c) {
          const t =
            fs?.card_badge_label != null && String(fs.card_badge_label).trim()
              ? String(fs.card_badge_label).trim()
              : "";
          setBadgeLabel(t);
        }
      } catch {
        if (!c) setBadgeLabel("");
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  useEffect(() => {
    const t = setInterval(() => {
      void pollQueue();
    }, 3000);
    return () => clearInterval(t);
  }, [pollQueue]);

  useEffect(() => {
    let stop = false;
    const missing = inbox.filter((j) => !thumbsRef.current[j.id]);
    if (!missing.length) return undefined;
    (async () => {
      for (const j of missing) {
        try {
          const blob = await fetchAiIngestJobSource(j.id);
          if (stop) return;
          thumbsRef.current[j.id] = URL.createObjectURL(blob);
        } catch {
          thumbsRef.current[j.id] = "";
        }
      }
      if (!stop) setThumbs({ ...thumbsRef.current });
    })();
    return () => {
      stop = true;
    };
  }, [inbox]);

  function brandValue(j) {
    if (Object.prototype.hasOwnProperty.call(picked, j.id)) return picked[j.id];
    if (j.brand_match === "linked" && j.suggested_brand_id) return j.suggested_brand_id;
    return j.brand_id || j.suggested_brand_id || "";
  }

  function toggleInbox(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectInboxGender(g) {
    setSelected(new Set(inbox.filter((j) => j.gender === g).map((j) => j.id)));
  }

  async function onEnqueue() {
    const rows = inbox.filter((j) => selected.has(j.id));
    if (!rows.length) {
      setErr("Отметьте кадры");
      return;
    }
    const missing = rows.filter((j) => !brandValue(j));
    if (missing.length) {
      setErr("У отмеченных кадров выберите бренд");
      return;
    }
    setEnqueueBusy(true);
    setErr("");
    try {
      await enqueueAiIngestInbox({
        sourceMode: inboxMode,
        showBadge: inboxBadge,
        items: rows.map((j) => ({ job_id: j.id, brand_id: brandValue(j) })),
      });
      setSelected(new Set());
      setPicked({});
      await pollQueue();
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setEnqueueBusy(false);
    }
  }

  async function onMoySklad(id) {
    setErr("");
    try {
      await retryAiIngestMoySklad(id);
      await pollQueue();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  function onPick(e) {
    const list = e.target.files ? Array.from(e.target.files) : [];
    setFiles(list);
    setErr("");
  }

  function onDrop(e) {
    e.preventDefault();
    setDrag(false);
    const list = e.dataTransfer.files ? Array.from(e.dataTransfer.files) : [];
    setFiles(list);
    setErr("");
  }

  async function onUpload(e) {
    e.preventDefault();
    const fromInput =
      fileInputRef.current?.files?.length > 0 ? Array.from(fileInputRef.current.files) : [];
    const toSend = fromInput.length > 0 ? fromInput : files;
    if (!toSend.length) {
      setErr("Выберите файлы");
      return;
    }
    if (!brandId) {
      setErr("Выберите бренд или добавьте новый");
      return;
    }
    setUploading(true);
    setErr("");
    try {
      await uploadAiIngestBatch(gender, brandId, toSend, { showBadge, sourceMode });
      if (fileInputRef.current) fileInputRef.current.value = "";
      setFiles([]);
      await Promise.all([refreshMeta(), loadJobs()]);
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setUploading(false);
    }
  }

  async function onQuickAddBrand(e) {
    e.preventDefault();
    const name = quickBrandName.trim();
    if (!name || quickBrandBusy) return;
    setQuickBrandBusy(true);
    setErr("");
    try {
      const created = await createBrand(name);
      setBrands((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name, "ru")));
      setBrandId(created.id);
      setQuickBrandName("");
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setQuickBrandBusy(false);
    }
  }

  async function onRetry(id) {
    setErr("");
    try {
      await retryAiIngestJob(id);
      await Promise.all([refreshMeta(), loadJobs()]);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  async function onPublishRelease() {
    if (!releaseDraft?.can_publish) return;
    if (
      !confirm(
        `Выпустить ${releaseDraft.photo_count} фото в ленту? После успеха черновик закроется.`,
      )
    ) {
      return;
    }
    setPublishBusy(true);
    setErr("");
    try {
      const result = await publishAiIngestRelease(gender);
      if (!result.ok) {
        setErr(result.message || "Выпуск не прошёл — см. детали ниже");
      }
      await Promise.all([refreshMeta(), loadJobs(), loadReleaseDraft()]);
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setPublishBusy(false);
    }
  }

  async function onDelete(id) {
    if (!confirm("Удалить задачу и локальный исходник (если есть)?")) return;
    setErr("");
    try {
      await deleteAiIngestJob(id);
      setSelected((prev) => {
        if (!prev.has(id)) return prev;
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      const phone = await fetchAiIngestJobs({ skip: 0, limit: 200, queue: "inbox" });
      setInbox(phone.items || []);
      await Promise.all([refreshMeta(), loadJobs()]);
    } catch (ex) {
      setErr(ex.message);
    }
  }

  const maxPage = Math.max(0, Math.ceil(total / limit) - 1);
  const page = Math.min(skip / limit, maxPage);

  if (loading && !limits) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>ИИ: телефон → каталог</h2>

      {limits && (
        <div
          style={{
            marginBottom: "1rem",
            padding: "0.75rem 1rem",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--surface)",
            fontSize: "0.9rem",
            color: "var(--muted)",
          }}
        >
          <strong style={{ color: "var(--text)" }}>Лимиты партии: </strong>
          до {limits.max_files_per_upload} файлов за один запрос, до{" "}
          {(limits.max_file_bytes / (1024 * 1024)).toFixed(0)} МиБ на файл, очередь не более{" "}
          {limits.max_pending_jobs} задач в статусе «В очереди», параллельно воркеров:{" "}
          {limits.worker_concurrency}.
          <div style={{ marginTop: "0.5rem" }}>
            Ключи:{" "}
            <strong style={{ color: limits.pipeline_ready ? "var(--accent)" : "var(--danger)" }}>
              {limits.pipeline_ready ? "заданы" : "не заданы"}
            </strong>
            {limits.pipeline_ready
              ? ""
              : " — upload вернёт 503, пока не настроите env на бэкенде"}
          </div>
        </div>
      )}

      {stats && (
        <div style={{ marginBottom: "1rem" }}>
          <div style={{ display: "flex", gap: "1.25rem", flexWrap: "wrap", alignItems: "center" }}>
            <span>
              В очереди: <strong style={{ color: "var(--accent)" }}>{stats.pending}</strong>
            </span>
            <span>
              Обработка: <strong>{stats.processing}</strong>
            </span>
            <span>
              Ошибки (всего записей): <strong style={{ color: "var(--danger)" }}>{stats.failed}</strong>
            </span>
            <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Обновление каждые 3 с</span>
          </div>
          {(stats.processing > 0 || stats.pending > 0) && (
            <p style={{ margin: "0.45rem 0 0", color: "var(--muted)", fontSize: "0.88rem" }}>
              {stats.pending > 0 && stats.processing === 0
                ? "Задачи в «В очереди», но обработка 0 — скорее всего не запущен воркер (см. подсказку выше). Запустите python -m jobs.ai_ingest_worker или перезапустите dev-up / docker compose."
                : "Идёт очередь или запрос к ИИ — дождитесь статуса «Готово» или текста ошибки в таблице."}
            </p>
          )}
        </div>
      )}

      {err ? <p className="error">{err}</p> : null}

      <div
        style={{
          marginBottom: "1.5rem",
          padding: "0.85rem 1rem",
          borderRadius: 8,
          border: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: "0.35rem" }}>
          С телефона ({inbox.length})
        </div>
        <p style={{ margin: "0 0 0.75rem", color: "var(--muted)", fontSize: "0.9rem" }}>
          Пол и бренд уже с ценника. Отметьте кадры, выберите способ и поставьте в Fashn.
          Совпадение бренда по имени — только подсказка: id поставщика запишется в справочник,
          когда отправите.
        </p>
        {inbox.length ? (
          <>
            <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", alignItems: "center" }}>
              <button type="button" className="secondary" onClick={() => selectInboxGender("male")}>
                Все мужские
              </button>
              <button type="button" className="secondary" onClick={() => selectInboxGender("female")}>
                Все женские
              </button>
              <button type="button" className="secondary" onClick={() => setSelected(new Set())}>
                Снять выбор
              </button>
              <label style={{ display: "flex", gap: "0.45rem", alignItems: "center" }}>
                <span>Что на фото</span>
                <select value={inboxMode} onChange={(e) => setInboxMode(e.target.value)}>
                  <option value="single">Одна вещь</option>
                  <option value="look">Образ в сборе</option>
                </select>
              </label>
              <label style={{ display: "flex", gap: "0.45rem", alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={inboxBadge}
                  onChange={(e) => setInboxBadge(e.target.checked)}
                />
                Бейдж
              </label>
              <button type="button" disabled={enqueueBusy || selected.size === 0} onClick={onEnqueue}>
                {enqueueBusy ? "Отправка…" : `В Fashn (${selected.size})`}
              </button>
            </div>
            <div style={{ overflowX: "auto", marginTop: "0.75rem" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
                    <th style={{ padding: "0.45rem 0.35rem" }} />
                    <th style={{ padding: "0.45rem 0.35rem" }}>Кадр</th>
                    <th style={{ padding: "0.45rem 0.35rem" }}>Товар</th>
                    <th style={{ padding: "0.45rem 0.35rem" }}>Пол</th>
                    <th style={{ padding: "0.45rem 0.35rem" }}>Бренд</th>
                    <th style={{ padding: "0.45rem 0.35rem" }} />
                  </tr>
                </thead>
                <tbody>
                  {inbox.map((j) => (
                    <tr key={j.id} style={{ borderBottom: "1px solid var(--border)", verticalAlign: "top" }}>
                      <td style={{ padding: "0.45rem 0.35rem" }}>
                        <input
                          type="checkbox"
                          checked={selected.has(j.id)}
                          onChange={() => toggleInbox(j.id)}
                        />
                      </td>
                      <td style={{ padding: "0.45rem 0.35rem" }}>
                        {thumbs[j.id] ? (
                          <img
                            src={thumbs[j.id]}
                            alt=""
                            style={{ width: 72, height: 90, objectFit: "cover", borderRadius: 6 }}
                          />
                        ) : (
                          <span style={{ color: "var(--muted)" }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: "0.45rem 0.35rem" }}>
                        <div>{productLinesLabel(j)}</div>
                        <div style={{ color: "var(--muted)", fontSize: "0.82rem" }}>
                          {j.linked_products?.length
                            ? `После Fashn — фото на ${1 + j.linked_products.length} карточки`
                            : j.article
                              ? `Арт. ${j.article}`
                              : "без артикула"}
                          {j.supplier_name ? ` · ${j.supplier_name}` : ""}
                        </div>
                      </td>
                      <td style={{ padding: "0.45rem 0.35rem" }}>
                        {j.gender === "female" ? "женский" : "мужской"}
                      </td>
                      <td style={{ padding: "0.45rem 0.35rem", minWidth: 220 }}>
                        <select
                          value={brandValue(j)}
                          onChange={(e) => setPicked((prev) => ({ ...prev, [j.id]: e.target.value }))}
                        >
                          <option value="">— выберите —</option>
                          {brands.map((b) => (
                            <option key={b.id} value={b.id}>
                              {b.name}
                            </option>
                          ))}
                        </select>
                        {j.brand_warning ? (
                          <div style={{ color: "var(--danger)", fontSize: "0.82rem", marginTop: 4 }}>
                            {j.brand_warning}
                          </div>
                        ) : null}
                      </td>
                      <td style={{ padding: "0.45rem 0.35rem" }}>
                        <button type="button" className="danger" onClick={() => onDelete(j.id)}>
                          Удалить
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p style={{ margin: 0, color: "var(--muted)" }}>Пока пусто. Кадры появятся из приложения сотрудника.</p>
        )}
      </div>

      {releaseDraft ? (
        <div
          style={{
            marginBottom: "1.25rem",
            padding: "0.85rem 1rem",
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "var(--surface)",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: "0.35rem" }}>
            Пакет в ленту ({gender === "male" ? "мужской" : "женский"})
          </div>
          <p style={{ margin: "0 0 0.5rem", color: "var(--muted)", fontSize: "0.9rem" }}>
            После Fashn задачи остаются в таблице со статусом «Готово», пока пакет не выпущен.
            Векторы считаются сами сразу после генерации; выпуск доступен, когда они готовы у всех
            фото. После выпуска записи очереди для этого пакета удаляются.
          </p>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", alignItems: "center" }}>
            <span>
              В черновике: <strong>{releaseDraft.photo_count}</strong>
            </span>
            {releaseDraft.photo_count > 0 ? (
              <span style={{ color: releaseDraft.embed_pending > 0 ? "var(--muted)" : undefined }}>
                Векторы: <strong>{releaseDraft.embedded_count}</strong> из {releaseDraft.photo_count}
                {releaseDraft.embed_pending > 0 ? " — считаются" : ""}
              </span>
            ) : null}
            {releaseDraft.fashn_pending > 0 ? (
              <span style={{ color: "var(--muted)" }}>
                Fashn в работе: <strong>{releaseDraft.fashn_pending}</strong>
              </span>
            ) : null}
            {releaseDraft.moysklad_pending > 0 ? (
              <span style={{ color: "var(--danger)" }}>
                МойСклад: <strong>{releaseDraft.moysklad_pending}</strong> — выпуск ждёт повтор
              </span>
            ) : null}
            {releaseDraft.fashn_failed > 0 ? (
              <span style={{ color: "var(--danger)" }}>
                Ошибки Fashn в пакете: <strong>{releaseDraft.fashn_failed}</strong> — выпуск
                заблокирован
              </span>
            ) : null}
            {releaseDraft.embed_error_count > 0 ? (
              <span style={{ color: "var(--danger)" }}>
                Ошибки векторов: <strong>{releaseDraft.embed_error_count}</strong>
              </span>
            ) : null}
          </div>
          {releaseDraft.last_embed_error ? (
            <p style={{ margin: "0.5rem 0 0", color: "var(--danger)", fontSize: "0.88rem" }}>
              {releaseDraft.last_embed_error}
            </p>
          ) : null}
          <button
            type="button"
            style={{ marginTop: "0.65rem" }}
            disabled={!releaseDraft.can_publish || publishBusy}
            onClick={onPublishRelease}
          >
            {publishBusy ? "Выпуск…" : "Выпустить в ленту"}
          </button>
        </div>
      ) : null}

      <form onSubmit={onUpload} style={{ marginBottom: "2rem" }}>
        <div
          style={{
            marginBottom: "0.65rem",
            display: "flex",
            gap: "1rem",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <span>Пол каталога</span>
            <select value={gender} onChange={(e) => setGender(e.target.value)}>
              <option value="male">Мужской</option>
              <option value="female">Женский</option>
            </select>
          </label>
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <span>Что на фото</span>
            <select value={sourceMode} onChange={(e) => setSourceMode(e.target.value)}>
              <option value="single">Одна вещь — остальное подберёт AI</option>
              <option value="look">Образ в сборе — сохранить всё</option>
            </select>
          </label>
        </div>

        <div
          style={{
            marginBottom: "0.75rem",
            display: "flex",
            gap: "1rem",
            flexWrap: "wrap",
            alignItems: "center",
          }}
        >
          <label style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <span>Бренд</span>
            <select value={brandId} onChange={(e) => setBrandId(e.target.value)}>
              <option value="">— выберите —</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}>или</span>
          <input
            type="text"
            placeholder="Новый бренд"
            value={quickBrandName}
            onChange={(e) => setQuickBrandName(e.target.value)}
            style={{ maxWidth: 220 }}
            disabled={quickBrandBusy}
          />
          <button type="button" className="secondary" disabled={quickBrandBusy} onClick={onQuickAddBrand}>
            {quickBrandBusy ? "…" : "+ В базу"}
          </button>
          <label
            style={{
              display: "flex",
              gap: "0.45rem",
              alignItems: "center",
              cursor: "pointer",
              userSelect: "none",
            }}
          >
            <input
              type="checkbox"
              checked={showBadge}
              onChange={(e) => setShowBadge(e.target.checked)}
            />
            <span>
              Бейдж
              {badgeLabel ? (
                <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}> («{badgeLabel}»)</span>
              ) : (
                <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                  {" "}
                  (текст на «Фото и теги»)
                </span>
              )}
            </span>
          </label>
        </div>

        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          style={{
            border: `2px dashed ${drag ? "var(--accent)" : "var(--border)"}`,
            borderRadius: 10,
            padding: "1.25rem",
            marginBottom: "0.75rem",
            background: drag ? "rgba(108, 158, 255, 0.06)" : "transparent",
          }}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp,.heic,.heif"
            onChange={onPick}
          />
          <div style={{ marginTop: "0.5rem", color: "var(--muted)", fontSize: "0.85rem" }}>
            Перетащите файлы сюда или выберите через поле выше. Выбрано: {files.length}
          </div>
        </div>

        <p style={{ margin: "0 0 0.75rem", color: "var(--muted)", fontSize: "0.85rem" }}>
          Тип исходника выбирает промпт Fashn: «вешалка» — сохранить вещь и дорисовать образ;
          «на человеке» — максимально точно перенести весь готовый look. В обоих режимах модель
          всегда в обуви на full-body.
        </p>

        <button type="submit" disabled={uploading || !files.length || !brandId}>
          {uploading ? "Загрузка…" : "Поставить в очередь"}
        </button>
      </form>

      <h3 style={{ fontSize: "1rem" }}>Очередь Fashn (ошибки и в работе)</h3>
      <p style={{ margin: "0 0 0.75rem", color: "var(--muted)", fontSize: "0.85rem" }}>
        «Готово» — Fashn прошёл, фото в черновике; строки исчезнут после «Записать вектора и
        выпустить».
      </p>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: "0.5rem 0.35rem" }}>Файл</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Пол</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Исходник</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Бренд</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Бейдж</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Статус</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Создано</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Результат / ошибка</th>
              <th style={{ padding: "0.5rem 0.35rem" }} />
            </tr>
          </thead>
          <tbody>
            {items.map((j) => (
              <tr key={j.id} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "0.45rem 0.35rem", maxWidth: 200 }}>{j.original_filename}</td>
                <td style={{ padding: "0.45rem 0.35rem" }}>{j.gender}</td>
                <td style={{ padding: "0.45rem 0.35rem" }}>{sourceModeLabel(j.source_mode)}</td>
                <td style={{ padding: "0.45rem 0.35rem" }}>{j.brand_name || "—"}</td>
                <td style={{ padding: "0.45rem 0.35rem" }}>{j.show_badge ? "да" : "—"}</td>
                <td style={{ padding: "0.45rem 0.35rem" }}>{statusLabel(j.status, j.stage)}
                  {j.stale ? <div style={{ color: "var(--danger)", fontSize: "0.82rem" }}>зависла</div> : null}
                  {j.status === "failed" && j.fashn_ordered ? (
                    <div style={{ color: "var(--muted)", fontSize: "0.82rem" }}>заказ оплачен</div>
                  ) : null}
                </td>
                <td style={{ padding: "0.45rem 0.35rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
                  {fmtDate(j.created_at)}
                </td>
                <td style={{ padding: "0.45rem 0.35rem", wordBreak: "break-word" }}>
                  {j.result_url ? (
                    <a href={j.result_url} target="_blank" rel="noreferrer">
                      открыть
                    </a>
                  ) : (
                    j.error_message || "—"
                  )}
                  {j.moysklad_product_id && j.moysklad_upload_status === "uploaded" ? (
                    <div style={{ color: "var(--muted)", fontSize: "0.82rem" }}>в МойСклад</div>
                  ) : null}
                  {j.moysklad_product_id && j.status === "completed" && j.moysklad_upload_status !== "uploaded" ? (
                    <div style={{ marginTop: 4 }}>
                      <div style={{ color: "var(--danger)", fontSize: "0.82rem" }}>
                        {j.moysklad_upload_error || "Не ушло в МойСклад"}
                      </div>
                      <button type="button" className="secondary" onClick={() => onMoySklad(j.id)}>
                        Повторить МойСклад
                      </button>
                    </div>
                  ) : null}
                </td>
                <td style={{ padding: "0.45rem 0.35rem", whiteSpace: "nowrap" }}>
                  {j.status === "failed" ? (
                    <button type="button" className="secondary" style={{ marginRight: 6 }} onClick={() => onRetry(j.id)}>
                      Повтор
                    </button>
                  ) : null}
                  {j.status !== "processing" || j.stale ? (
                    <button type="button" className="danger" onClick={() => onDelete(j.id)}>
                      Удалить
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > limit ? (
        <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem", alignItems: "center" }}>
          <button type="button" className="secondary" disabled={skip <= 0} onClick={() => setSkip((s) => Math.max(0, s - limit))}>
            Назад
          </button>
          <span style={{ color: "var(--muted)" }}>
            Стр. {page + 1} / {maxPage + 1} · всего {total}
          </span>
          <button
            type="button"
            className="secondary"
            disabled={skip + limit >= total}
            onClick={() => setSkip((s) => s + limit)}
          >
            Вперёд
          </button>
        </div>
      ) : null}
    </div>
  );
}
