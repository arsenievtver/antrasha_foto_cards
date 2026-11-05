import { useCallback, useEffect, useRef, useState } from "react";
import {
  createOutletPhotoJob,
  dismissOutletPhotoJob,
  fetchCurrentOutletPhotoJob,
  fetchOutletPhotoJob,
  fetchOutletPhotoJobImage,
  fetchOutletPhotoStatus,
  lookupOutletPhotoBarcode,
  publishOutletPhotoJob,
} from "../api.js";
import ImageCropModal from "../components/ImageCropModal.jsx";

const STEPS = {
  BARCODE: "barcode",
  PRODUCT: "product",
  PREVIEW_CROP: "preview_crop",
  WAITING: "waiting",
  RESULT: "result",
  SUCCESS: "success",
};

function netMessage(error) {
  const msg = error?.message || "Ошибка сети";
  if (
    msg === "Load failed" ||
    msg === "Failed to fetch" ||
    msg === "NetworkError when attempting to fetch resource."
  ) {
    return "Нет связи с сервером. Если кадр уже ушёл, откройте страницу снова — он доделается сам.";
  }
  return msg;
}

function productFromJob(job) {
  return {
    product_id: job.product_id,
    name: job.name,
    article: job.article,
    code: job.code,
    barcode: job.barcode,
    path_name: job.path_name,
    gender: job.product_gender,
    existing_images_count: 0,
  };
}

const CROP_ASPECT = 4 / 5;

function revokeUrl(url) {
  if (url && String(url).startsWith("blob:")) {
    try {
      URL.revokeObjectURL(url);
    } catch {
      /* ignore */
    }
  }
}

export default function OutletPhoto() {
  const [status, setStatus] = useState(null);
  const [step, setStep] = useState(STEPS.BARCODE);
  const [barcode, setBarcode] = useState("");
  const [product, setProduct] = useState(null);
  const [gender, setGender] = useState("male");
  const [rawSrc, setRawSrc] = useState("");
  const [cropOpen, setCropOpen] = useState(false);
  const [croppedFile, setCroppedFile] = useState(null);
  const [croppedPreview, setCroppedPreview] = useState("");
  const [jobId, setJobId] = useState("");
  const [resultUrl, setResultUrl] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const cameraRef = useRef(null);
  const fileRef = useRef(null);
  const jobIdRef = useRef("");
  const resultUrlRef = useRef("");
  const croppedFileRef = useRef(null);
  jobIdRef.current = jobId;
  resultUrlRef.current = resultUrl;
  croppedFileRef.current = croppedFile;

  const refreshStatus = useCallback(async () => {
    const data = await fetchOutletPhotoStatus();
    setStatus(data);
    return data;
  }, []);

  useEffect(() => {
    let c = false;
    (async () => {
      setLoadingStatus(true);
      try {
        await refreshStatus();
        const job = await fetchCurrentOutletPhotoJob();
        if (c || !job) return;
        setJobId(job.id);
        setProduct(productFromJob(job));
        setBarcode(job.barcode || "");
        if (job.gender === "male" || job.gender === "female") setGender(job.gender);
        if (job.status === "pending" || job.status === "running") {
          setStep(STEPS.WAITING);
        } else if (job.status === "ready") {
          try {
            const blob = await fetchOutletPhotoJobImage(job.id);
            if (c) return;
            const url = URL.createObjectURL(blob);
            setResultUrl((prev) => {
              revokeUrl(prev);
              return url;
            });
            setStep(STEPS.RESULT);
          } catch (imgErr) {
            if (!c) {
              setErr(netMessage(imgErr));
              setStep(STEPS.WAITING);
            }
          }
        } else if (job.status === "failed") {
          setErr(job.error_message || "Fashn не смог сделать кадр");
          setStep(STEPS.PRODUCT);
        }
      } catch (e) {
        if (!c) setErr(netMessage(e));
      } finally {
        if (!c) setLoadingStatus(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [refreshStatus]);

  useEffect(() => {
    return () => {
      revokeUrl(rawSrc);
      revokeUrl(croppedPreview);
    };
  }, [rawSrc, croppedPreview]);

  useEffect(() => () => revokeUrl(resultUrlRef.current), []);

  useEffect(() => {
    if (step !== STEPS.WAITING || !jobId) return undefined;
    let stop = false;
    let loadingImage = false;
    async function tick() {
      try {
        const job = await fetchOutletPhotoJob(jobId);
        if (stop) return;
        if (job.status === "pending" || job.status === "running") {
          setErr("");
          return;
        }
        if (job.status === "ready") {
          if (loadingImage) return;
          loadingImage = true;
          const blob = await fetchOutletPhotoJobImage(job.id);
          if (stop) return;
          const url = URL.createObjectURL(blob);
          setResultUrl((prev) => {
            revokeUrl(prev);
            return url;
          });
          setStep(STEPS.RESULT);
          setErr("");
          return;
        }
        if (job.status === "failed") {
          setErr(job.error_message || "Fashn не смог сделать кадр");
          setStep(croppedFileRef.current ? STEPS.PREVIEW_CROP : STEPS.PRODUCT);
          return;
        }
      } catch (ex) {
        loadingImage = false;
        if (!stop) setErr(netMessage(ex));
      }
    }
    const timer = setInterval(() => {
      void tick();
    }, 2000);
    const onVis = () => {
      if (document.visibilityState === "visible") void tick();
    };
    document.addEventListener("visibilitychange", onVis);
    void tick();
    return () => {
      stop = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [step, jobId]);

  function resetAll() {
    const id = jobIdRef.current;
    revokeUrl(rawSrc);
    revokeUrl(croppedPreview);
    revokeUrl(resultUrlRef.current);
    setStep(STEPS.BARCODE);
    setBarcode("");
    setProduct(null);
    setRawSrc("");
    setCropOpen(false);
    setCroppedFile(null);
    setCroppedPreview("");
    setJobId("");
    setResultUrl("");
    setErr("");
    setBusy(false);
    if (id) void dismissOutletPhotoJob(id).catch(() => {});
    if (cameraRef.current) cameraRef.current.value = "";
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onLookup(e) {
    e?.preventDefault?.();
    const code = barcode.trim();
    if (!code) {
      setErr("Введите штрихкод");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const data = await lookupOutletPhotoBarcode(code);
      setProduct(data);
      if (data.gender === "male" || data.gender === "female") {
        setGender(data.gender);
      }
      setStep(STEPS.PRODUCT);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  function openSource(file) {
    if (!file) return;
    revokeUrl(rawSrc);
    const url = URL.createObjectURL(file);
    setRawSrc(url);
    setCropOpen(true);
    setErr("");
  }

  function onPickCamera(e) {
    const file = e.target.files?.[0];
    openSource(file);
  }

  function onPickFile(e) {
    const file = e.target.files?.[0];
    openSource(file);
  }

  function onCropCancel() {
    setCropOpen(false);
    revokeUrl(rawSrc);
    setRawSrc("");
    if (cameraRef.current) cameraRef.current.value = "";
    if (fileRef.current) fileRef.current.value = "";
  }

  function onCropConfirm(file, previewUrl) {
    revokeUrl(croppedPreview);
    setCroppedFile(file);
    setCroppedPreview(previewUrl);
    setCropOpen(false);
    revokeUrl(rawSrc);
    setRawSrc("");
    setStep(STEPS.PREVIEW_CROP);
  }

  async function onGenerate() {
    if (!croppedFile || !product?.product_id) {
      setErr("Сначала сделайте кадр");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const job = await createOutletPhotoJob({ gender, file: croppedFile, product });
      setJobId(job.id);
      setStep(STEPS.WAITING);
    } catch (ex) {
      setErr(netMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  function onRedo() {
    const id = jobIdRef.current;
    revokeUrl(resultUrlRef.current);
    setResultUrl("");
    setJobId("");
    setErr("");
    setStep(STEPS.PRODUCT);
    setCroppedFile(null);
    revokeUrl(croppedPreview);
    setCroppedPreview("");
    if (cameraRef.current) cameraRef.current.value = "";
    if (fileRef.current) fileRef.current.value = "";
    if (id) void dismissOutletPhotoJob(id).catch(() => {});
  }

  async function onUpload() {
    if (!jobId) {
      setErr("Нет результата для загрузки");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await publishOutletPhotoJob(jobId);
      setStep(STEPS.SUCCESS);
    } catch (ex) {
      setErr(netMessage(ex));
    } finally {
      setBusy(false);
    }
  }

  if (loadingStatus && !status) {
    return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;
  }

  return (
    <div className="outlet-photo">
      <h2 style={{ marginTop: 0 }}>Аутлет: фото</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, maxWidth: 560 }}>
        Штрихкод → товар в МойСклад → кадр уходит на сервер. Fashn считается там, страница только
        спрашивает готовность. Можно закрыть вкладку и открыть её снова.
      </p>

      {status && (
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
          МойСклад:{" "}
          <strong style={{ color: status.moysklad_configured ? "var(--ok)" : "var(--danger)" }}>
            {status.moysklad_configured ? "токен есть" : "нет MOYSKLAD_TOKEN"}
          </strong>
          {" · "}
          Fashn:{" "}
          <strong style={{ color: status.fashn_configured ? "var(--ok)" : "var(--danger)" }}>
            {status.fashn_configured ? "ключ есть" : "нет FASHN_API_KEY"}
          </strong>
        </div>
      )}

      {err ? <p className="error">{err}</p> : null}

      {step === STEPS.BARCODE && (
        <form onSubmit={onLookup} style={{ maxWidth: 420 }}>
          <label style={{ display: "block", marginBottom: "0.5rem" }}>
            Штрихкод товара
            <input
              type="text"
              inputMode="numeric"
              autoComplete="off"
              autoFocus
              value={barcode}
              onChange={(e) => setBarcode(e.target.value)}
              placeholder="Сканер или вручную"
              disabled={busy || !status?.ready}
              style={{ display: "block", width: "100%", marginTop: 6 }}
            />
          </label>
          <button type="submit" disabled={busy || !status?.ready || !barcode.trim()}>
            {busy ? "Ищем…" : "Найти"}
          </button>
        </form>
      )}

      {(step === STEPS.PRODUCT ||
        step === STEPS.PREVIEW_CROP ||
        step === STEPS.WAITING ||
        step === STEPS.RESULT ||
        step === STEPS.SUCCESS) &&
        product && (
          <div
            style={{
              marginBottom: "1rem",
              padding: "0.85rem 1rem",
              borderRadius: 8,
              border: "1px solid var(--border)",
              background: "var(--surface)",
              maxWidth: 520,
            }}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{product.name}</div>
            <div style={{ fontSize: "0.9rem", color: "var(--muted)" }}>
              {product.article ? <>Артикул: {product.article} · </> : null}
              {product.code ? <>Код: {product.code} · </> : null}
              Штрихкод: {product.barcode}
            </div>
            {product.path_name ? (
              <div style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: 4 }}>
                {product.path_name}
              </div>
            ) : null}
            <div style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: 4 }}>
              Пол:{" "}
              {product.gender === "female"
                ? "женский (из папки)"
                : product.gender === "male"
                  ? "мужской (из папки)"
                  : "не определён — выберите вручную"}
              {" · "}
              product_id: {product.product_id}
              {product.entity_type === "variant" && product.variant_id
                ? ` · модификация ${product.variant_id}`
                : ""}
            </div>
            {product.existing_images_count > 0 ? (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  marginTop: "0.65rem",
                  padding: "0.45rem 0.55rem",
                  borderRadius: 8,
                  background: "rgba(255, 193, 7, 0.08)",
                  border: "1px solid rgba(255, 193, 7, 0.25)",
                }}
              >
                {product.existing_image_preview ? (
                  <img
                    src={product.existing_image_preview}
                    alt=""
                    style={{
                      width: 48,
                      height: 48,
                      objectFit: "cover",
                      borderRadius: 6,
                      border: "1px solid var(--border)",
                      flexShrink: 0,
                    }}
                  />
                ) : null}
                <span style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                  В МойСклад уже {product.existing_images_count} фото
                </span>
              </div>
            ) : null}
            {step !== STEPS.SUCCESS && (
              <button
                type="button"
                className="secondary"
                style={{ marginTop: "0.75rem" }}
                disabled={busy}
                onClick={resetAll}
              >
                Другой штрихкод
              </button>
            )}
          </div>
        )}

      {step === STEPS.PRODUCT && (
        <div style={{ maxWidth: 420 }}>
          <label style={{ display: "block", marginBottom: "0.75rem" }}>
            Модель
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              disabled={busy}
              style={{ display: "block", width: "100%", marginTop: 6 }}
            >
              <option value="male">Мужская</option>
              <option value="female">Женская</option>
            </select>
          </label>

          <div className="flex-gap" style={{ flexWrap: "wrap" }}>
            <button
              type="button"
              disabled={busy || !status?.ready}
              onClick={() => cameraRef.current?.click()}
            >
              Сделать фото
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy || !status?.ready}
              onClick={() => fileRef.current?.click()}
            >
              Выбрать файл
            </button>
          </div>

          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            style={{ display: "none" }}
            onChange={onPickCamera}
          />
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={onPickFile}
          />
        </div>
      )}

      {step === STEPS.PREVIEW_CROP && (
        <div style={{ maxWidth: 420 }}>
          <p style={{ marginTop: 0 }}>Кадр 4:5 — отправить на сервер?</p>
          {croppedPreview ? (
            <img
              src={croppedPreview}
              alt="Кадр"
              style={{
                width: "100%",
                maxWidth: 320,
                borderRadius: 8,
                border: "1px solid var(--border)",
                display: "block",
                marginBottom: "0.75rem",
              }}
            />
          ) : null}
          <div className="flex-gap" style={{ flexWrap: "wrap" }}>
            <button type="button" disabled={busy} onClick={onGenerate}>
              {busy ? "Отправляем…" : "Отправить"}
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => {
                setCroppedFile(null);
                revokeUrl(croppedPreview);
                setCroppedPreview("");
                setStep(STEPS.PRODUCT);
              }}
            >
              Переснять
            </button>
          </div>
        </div>
      )}

      {step === STEPS.WAITING && (
        <div style={{ maxWidth: 420 }}>
          <p style={{ marginTop: 0, fontWeight: 600 }}>Fashn рисует кадр на сервере</p>
          <p style={{ color: "var(--muted)", marginTop: 0 }}>
            Телефон больше не ждёт ответ. Можно закрыть страницу и открыть её снова — здесь
            появится готовый кадр.
          </p>
        </div>
      )}

      {step === STEPS.RESULT && (
        <div style={{ maxWidth: 420 }}>
          <p style={{ marginTop: 0 }}>Результат Fashn</p>
          {resultUrl ? (
            <img
              src={resultUrl}
              alt="Результат"
              style={{
                width: "100%",
                maxWidth: 360,
                borderRadius: 8,
                border: "1px solid var(--border)",
                display: "block",
                marginBottom: "0.75rem",
              }}
            />
          ) : null}
          <div className="flex-gap" style={{ flexWrap: "wrap" }}>
            <button type="button" disabled={busy} onClick={onUpload}>
              {busy ? "Загружаем…" : "В МойСклад"}
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={onRedo}>
              Переделать
            </button>
          </div>
        </div>
      )}

      {step === STEPS.SUCCESS && (
        <div style={{ maxWidth: 420 }}>
          <p style={{ color: "var(--ok)", fontWeight: 600 }}>Изображение добавлено к товару в МойСклад.</p>
          {resultUrl ? (
            <img
              src={resultUrl}
              alt="Загружено"
              style={{
                width: "100%",
                maxWidth: 280,
                borderRadius: 8,
                border: "1px solid var(--border)",
                display: "block",
                marginBottom: "0.75rem",
                opacity: 0.95,
              }}
            />
          ) : null}
          <button type="button" onClick={resetAll}>
            Следующий товар
          </button>
        </div>
      )}

      {cropOpen && rawSrc ? (
        <ImageCropModal
          imageSrc={rawSrc}
          aspect={CROP_ASPECT}
          title="Кадр для каталога 4:5"
          hint="Уберите лишнее: фон, руки, другие вещи. В рамке — только товар."
          onCancel={onCropCancel}
          onConfirm={onCropConfirm}
        />
      ) : null}
    </div>
  );
}
