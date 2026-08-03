import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchOutletPhotoStatus,
  generateOutletPhoto,
  lookupOutletPhotoBarcode,
  uploadOutletPhotoToMoySklad,
} from "../api.js";
import BarcodeScanner from "../components/BarcodeScanner.jsx";
import ImageCropModal from "../components/ImageCropModal.jsx";

const STEPS = {
  BARCODE: "barcode",
  PRODUCT: "product",
  PREVIEW_CROP: "preview_crop",
  RESULT: "result",
  SUCCESS: "success",
};

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
  const [resultB64, setResultB64] = useState("");
  const [resultMime, setResultMime] = useState("image/png");
  const [resultFilename, setResultFilename] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [scanOpen, setScanOpen] = useState(false);
  const cameraRef = useRef(null);
  const fileRef = useRef(null);

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
      } catch (e) {
        if (!c) setErr(e.message);
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

  function resetAll() {
    revokeUrl(rawSrc);
    revokeUrl(croppedPreview);
    setStep(STEPS.BARCODE);
    setBarcode("");
    setProduct(null);
    setRawSrc("");
    setCropOpen(false);
    setCroppedFile(null);
    setCroppedPreview("");
    setResultB64("");
    setResultMime("image/png");
    setResultFilename("");
    setErr("");
    setBusy(false);
    setScanOpen(false);
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
    if (!croppedFile) {
      setErr("Сначала сделайте кадр");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const data = await generateOutletPhoto(gender, croppedFile);
      setResultB64(data.image_base64);
      setResultMime(data.mime || "image/png");
      setResultFilename(data.filename || `outlet-${Date.now()}.png`);
      setStep(STEPS.RESULT);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  function onRedo() {
    setResultB64("");
    setResultFilename("");
    setErr("");
    setStep(STEPS.PRODUCT);
    setCroppedFile(null);
    revokeUrl(croppedPreview);
    setCroppedPreview("");
    if (cameraRef.current) cameraRef.current.value = "";
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onUpload() {
    if (!product?.product_id || !resultB64) {
      setErr("Нет результата для загрузки");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await uploadOutletPhotoToMoySklad({
        productId: product.product_id,
        filename: resultFilename || `outlet-${Date.now()}.png`,
        content: resultB64,
        name: product.name,
        article: product.article,
        code: product.code,
        barcode: product.barcode,
        pathName: product.path_name,
        gender: product.gender || gender,
      });
      setStep(STEPS.SUCCESS);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  const resultSrc = resultB64 ? `data:${resultMime};base64,${resultB64}` : "";

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
          <p style={{ marginTop: 0 }}>Кадр 4:5 — отправить в Fashn?</p>
          {croppedPreview ? (
            <img src={croppedPreview} alt="Кадр" className="outlet-preview" />
          ) : null}
          <div className="row-actions">
            <button type="button" disabled={busy} onClick={onGenerate}>
              {busy ? "Генерация…" : "Сгенерировать"}
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

      {step === STEPS.RESULT && (
        <div className="outlet-card">
          <p style={{ marginTop: 0 }}>Результат</p>
          {resultSrc ? <img src={resultSrc} alt="Результат" className="outlet-preview" /> : null}
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
          {resultSrc ? <img src={resultSrc} alt="Загружено" className="outlet-preview" /> : null}
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
