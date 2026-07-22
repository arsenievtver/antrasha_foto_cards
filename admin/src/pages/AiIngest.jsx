import { useCallback, useEffect, useRef, useState } from "react";
import {
  createBrand,
  deleteAiIngestJob,
  fetchAiIngestJobs,
  fetchAiIngestLimits,
  fetchAiIngestStats,
  fetchBrands,
  fetchFeedSettings,
  retryAiIngestJob,
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

const statusLabel = (s) => {
  if (s === "pending") return "В очереди";
  if (s === "processing") return "Обработка";
  if (s === "completed") return "Готово";
  if (s === "failed") return "Ошибка";
  return s;
};

export default function AiIngest() {
  const [limits, setLimits] = useState(null);
  const [stats, setStats] = useState(null);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 40;
  const [gender, setGender] = useState("male");
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
  const fileInputRef = useRef(null);

  const loadJobs = useCallback(async () => {
    setErr("");
    const data = await fetchAiIngestJobs({ skip, limit });
    setItems(data.items || []);
    setTotal(data.total ?? 0);
  }, [skip, limit]);

  /** Тихое обновление списка и счётчиков без сброса ошибки (для опроса в фоне). */
  const pollQueue = useCallback(async () => {
    try {
      const [st, data, lim] = await Promise.all([
        fetchAiIngestStats(),
        fetchAiIngestJobs({ skip, limit }),
        fetchAiIngestLimits(),
      ]);
      setStats(st);
      setItems(data.items || []);
      setTotal(data.total ?? 0);
      setLimits(lim);
    } catch {
      /* сеть / сессия — не показываем при каждом тике */
    }
  }, [skip, limit]);

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
        await loadJobs();
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
      await uploadAiIngestBatch(gender, brandId, toSend, { showBadge });
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

  async function onDelete(id) {
    if (!confirm("Удалить задачу и локальный исходник (если есть)?")) return;
    setErr("");
    try {
      await deleteAiIngestJob(id);
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
            Ключи Fashn + YC на API:{" "}
            <strong style={{ color: limits.pipeline_ready ? "var(--accent)" : "var(--danger)" }}>
              {limits.pipeline_ready ? "заданы" : "не заданы"}
            </strong>
            {limits.pipeline_ready
              ? ""
              : " — upload вернёт 503, пока не настроите env на бэкенде"}
            {" · "}
            Fashn …{limits.fashn_key_last4 ?? "????"}, YC …{limits.yc_access_key_id_last4 ?? "????"}
          </div>
          <div style={{ marginTop: "0.35rem", color: "var(--muted)" }}>
            Очередь обрабатывает <strong style={{ color: "var(--text)" }}>отдельный процесс</strong>{" "}
            <code style={{ fontSize: "0.82em" }}>python -m jobs.ai_ingest_worker</code> (не uvicorn).
            На dev: <code style={{ fontSize: "0.82em" }}>scripts/dev-up.sh</code> поднимает его вместе с API.
            В Docker prod — сервис <code style={{ fontSize: "0.82em" }}>ai-ingest-worker</code>.
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

      <form onSubmit={onUpload} style={{ marginBottom: "2rem" }}>
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
            <span>Пол каталога</span>
            <select value={gender} onChange={(e) => setGender(e.target.value)}>
              <option value="male">Мужской</option>
              <option value="female">Женский</option>
            </select>
          </label>
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
          <span style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            JPG, PNG, WEBP, HEIC — конвертация на сервере
          </span>
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

        <button type="submit" disabled={uploading || !files.length || !brandId}>
          {uploading ? "Загрузка…" : "Поставить в очередь"}
        </button>
      </form>

      <h3 style={{ fontSize: "1rem" }}>Задачи</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
          <thead>
            <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
              <th style={{ padding: "0.5rem 0.35rem" }}>Файл</th>
              <th style={{ padding: "0.5rem 0.35rem" }}>Пол</th>
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
                <td style={{ padding: "0.45rem 0.35rem" }}>{j.brand_name || "—"}</td>
                <td style={{ padding: "0.45rem 0.35rem" }}>{j.show_badge ? "да" : "—"}</td>
                <td style={{ padding: "0.45rem 0.35rem" }}>{statusLabel(j.status)}</td>
                <td style={{ padding: "0.45rem 0.35rem", color: "var(--muted)", whiteSpace: "nowrap" }}>
                  {fmtDate(j.created_at)}
                </td>
                <td style={{ padding: "0.45rem 0.35rem", wordBreak: "break-word" }}>
                  {j.result_url ? (
                    <a href={j.result_url} target="_blank" rel="noreferrer">
                      PNG в бакете
                    </a>
                  ) : (
                    j.error_message || "—"
                  )}
                </td>
                <td style={{ padding: "0.45rem 0.35rem", whiteSpace: "nowrap" }}>
                  {j.status === "failed" ? (
                    <button type="button" className="secondary" style={{ marginRight: 6 }} onClick={() => onRetry(j.id)}>
                      Повтор
                    </button>
                  ) : null}
                  {j.status !== "processing" ? (
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
