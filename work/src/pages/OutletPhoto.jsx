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
import BarcodeScanner from "../components/BarcodeScanner.jsx";
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
  const [scanOpen, setScanOpen] = useState(false);
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
    setScanOpen(false);
    if (id) void dismissOutletPhotoJob(id).catch(() => {});
    if (cameraRef.current) cameraRef.current.value = "";
    if (fileRef.current) fileRef.current.value = "";
  }

  async function runLookup(codeRaw) {
    const code = String(codeRaw || "").trim();
    if (!code) {
      setErr("Введите штрихкод");
      return;
    }
    setBusy(true);
    setErr("");
    setBarcode(code);
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

  function onLookup(e) {
    e?.preventDefault?.();
    void runLookup(barcode);
  }

  const runLookupRef = useRef(runLookup);
  runLookupRef.current = runLookup;

  const onScanDetected = useCallback((code) => {
    setScanOpen(false);
    void runLookupRef.current(code);
  }, []);

  function openSource(file) {
    if (!file) return;
    revokeUrl(rawSrc);
    const url = URL.createObjectURL(file);
    setRawSrc(url);
    setCropOpen(true);
    setErr("");
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
    setResultUrl("");
    revokeUrl(resultUrlRef.current);
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
    return <p className="muted">Загрузка…</p>;
  }

  return (
    <div className="outlet-page">
      {status ? (
        <div className="outlet-status">
          МойСклад:{" "}
          <strong className={status.moysklad_configured ? "ok" : "bad"}>
            {status.moysklad_configured ? "ок" : "нет токена"}
          </strong>
          {" · "}
          Fashn:{" "}
          <strong className={status.fashn_configured ? "ok" : "bad"}>
            {status.fashn_configured ? "ок" : "нет ключа"}
          </strong>
        </div>
      ) : null}

      {err ? <p className="error">{err}</p> : null}

      {step === STEPS.BARCODE && (
        <div className="outlet-card">
          <form className="form-stack" onSubmit={onLookup}>
            <label>
              Штрихкод
              <input
                type="text"
                inputMode="numeric"
                autoComplete="off"
                value={barcode}
                onChange={(e) => setBarcode(e.target.value)}
                placeholder="Или введите вручную"
                disabled={busy || !status?.ready}
              />
            </label>
            <div className="row-actions">
              <button
                type="button"
                disabled={busy || !status?.ready}
                onClick={() => setScanOpen(true)}
              >
                Сканировать
              </button>
              <button
                type="submit"
                className="secondary"
                disabled={busy || !status?.ready || !barcode.trim()}
              >
                {busy ? "Ищем…" : "Найти"}
              </button>
            </div>
          </form>
        </div>
      )}

      {(step === STEPS.PRODUCT ||
        step === STEPS.PREVIEW_CROP ||
        step === STEPS.WAITING ||
        step === STEPS.RESULT ||
        step === STEPS.SUCCESS) &&
        product && (
          <div className="outlet-card">
            <div className="outlet-product__name">{product.name}</div>
            <div className="muted small">
              {product.article ? <>Арт. {product.article} · </> : null}
              {product.barcode}
            </div>
            {product.path_name ? (
              <div className="muted small" style={{ marginTop: 4 }}>
                {product.path_name}
              </div>
            ) : null}
            <div className="muted small" style={{ marginTop: 4 }}>
              Пол:{" "}
              {product.gender === "female"
                ? "женский"
                : product.gender === "male"
                  ? "мужской"
                  : "не определён"}
            </div>
            {product.existing_images_count > 0 ? (
              <div className="outlet-product__existing">
                {product.existing_image_preview ? (
                  <img
                    src={product.existing_image_preview}
                    alt=""
                    className="outlet-product__thumb"
                  />
                ) : null}
                <span className="muted small">
                  В МойСклад уже {product.existing_images_count} фото
                </span>
              </div>
            ) : null}
            {step !== STEPS.SUCCESS ? (
              <button
                type="button"
                className="secondary"
                style={{ marginTop: "0.75rem" }}
                disabled={busy}
                onClick={resetAll}
              >
                Другой штрихкод
              </button>
            ) : null}
          </div>
        )}

      {step === STEPS.PRODUCT && (
        <div className="outlet-card">
          <label>
            Модель
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              disabled={busy}
            >
              <option value="male">Мужская</option>
              <option value="female">Женская</option>
            </select>
          </label>
          <div className="row-actions" style={{ marginTop: "0.85rem" }}>
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
              Файл
            </button>
          </div>
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => openSource(e.target.files?.[0])}
          />
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => openSource(e.target.files?.[0])}
          />
        </div>
      )}

      {step === STEPS.PREVIEW_CROP && (
        <div className="outlet-card">
          <p style={{ marginTop: 0 }}>Кадр 4:5 — отправить на сервер?</p>
          {croppedPreview ? (
            <img src={croppedPreview} alt="Кадр" className="outlet-preview" />
          ) : null}
          <div className="row-actions">
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
        <div className="outlet-card">
          <p style={{ marginTop: 0, fontWeight: 600 }}>Fashn рисует кадр на сервере</p>
          <p className="muted" style={{ marginTop: 0 }}>
            Телефон больше не ждёт ответ. Можно закрыть страницу и открыть её снова — здесь
            появится готовый кадр.
          </p>
        </div>
      )}

      {step === STEPS.RESULT && (
        <div className="outlet-card">
          <p style={{ marginTop: 0 }}>Результат</p>
          {resultUrl ? <img src={resultUrl} alt="Результат" className="outlet-preview" /> : null}
          <div className="row-actions">
            <button type="button" disabled={busy} onClick={onUpload}>
              {busy ? "Загрузка…" : "В МойСклад"}
            </button>
            <button type="button" className="secondary" disabled={busy} onClick={onRedo}>
              Переделать
            </button>
          </div>
        </div>
      )}

      {step === STEPS.SUCCESS && (
        <div className="outlet-card">
          <p className="ok" style={{ fontWeight: 600 }}>
            Изображение добавлено в МойСклад.
          </p>
          {resultUrl ? <img src={resultUrl} alt="Загружено" className="outlet-preview" /> : null}
          <button type="button" onClick={resetAll}>
            Следующий товар
          </button>
        </div>
      )}

      {scanOpen ? (
        <BarcodeScanner onDetected={onScanDetected} onClose={() => setScanOpen(false)} />
      ) : null}

      {cropOpen && rawSrc ? (
        <ImageCropModal
          imageSrc={rawSrc}
          aspect={CROP_ASPECT}
          title="Кадр 4:5"
          hint="Уберите лишнее — в рамке только товар."
          onCancel={onCropCancel}
          onConfirm={onCropConfirm}
        />
      ) : null}
    </div>
  );
}
