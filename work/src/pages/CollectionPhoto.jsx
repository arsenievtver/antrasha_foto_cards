import { useCallback, useEffect, useRef, useState } from "react";
import {
  createCollectionPhotoJob,
  fetchCollectionPhotoStatus,
  lookupCollectionBarcode,
} from "../api.js";
import BarcodeScanner from "../components/BarcodeScanner.jsx";
import ImageCropModal from "../components/ImageCropModal.jsx";

const STEPS = {
  BARCODE: "barcode",
  PRODUCT: "product",
  PREVIEW_CROP: "preview_crop",
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

function brandLine(product) {
  if (product.brand_match === "linked" && product.brand_name) {
    return `Бренд: ${product.brand_name}`;
  }
  if (product.brand_match === "name" && product.brand_name) {
    return `Похоже на бренд «${product.brand_name}». Администратор подтвердит.`;
  }
  return "Бренд выберет администратор.";
}

export default function CollectionPhoto() {
  const [status, setStatus] = useState(null);
  const [step, setStep] = useState(STEPS.BARCODE);
  const [barcode, setBarcode] = useState("");
  const [product, setProduct] = useState(null);
  const [gender, setGender] = useState("male");
  const [rawSrc, setRawSrc] = useState("");
  const [cropOpen, setCropOpen] = useState(false);
  const [croppedFile, setCroppedFile] = useState(null);
  const [croppedPreview, setCroppedPreview] = useState("");
  const [scanOpen, setScanOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const cameraRef = useRef(null);
  const fileRef = useRef(null);

  useEffect(() => {
    let stop = false;
    fetchCollectionPhotoStatus()
      .then((data) => {
        if (!stop) setStatus(data);
      })
      .catch((ex) => {
        if (!stop) setErr(ex.message);
      });
    return () => {
      stop = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      revokeUrl(rawSrc);
      revokeUrl(croppedPreview);
    };
  }, [rawSrc, croppedPreview]);

  function resetToBarcode(message) {
    revokeUrl(rawSrc);
    revokeUrl(croppedPreview);
    setStep(STEPS.BARCODE);
    setBarcode("");
    setProduct(null);
    setRawSrc("");
    setCropOpen(false);
    setCroppedFile(null);
    setCroppedPreview("");
    setScanOpen(false);
    setErr("");
    setNotice(message || "");
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
    setNotice("");
    setBarcode(code);
    try {
      const data = await lookupCollectionBarcode(code);
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
    setRawSrc(URL.createObjectURL(file));
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

  async function onSend() {
    if (!croppedFile || !product?.barcode) {
      setErr("Сначала сделайте кадр");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await createCollectionPhotoJob({
        gender,
        file: croppedFile,
        barcode: product.barcode,
      });
      const name = product.article || product.name || "кадр";
      resetToBarcode(`В админке: ${name}`);
    } catch (ex) {
      setErr(ex.message || "Не удалось отправить");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="outlet-page">
      {status ? (
        <div className="outlet-status">
          МойСклад:{" "}
          <strong className={status.moysklad_configured ? "ok" : "bad"}>
            {status.moysklad_configured ? "ок" : "нет токена"}
          </strong>
        </div>
      ) : null}

      {notice ? <p className="ok">{notice}</p> : null}
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
              <button type="button" disabled={busy || !status?.ready} onClick={() => setScanOpen(true)}>
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

      {(step === STEPS.PRODUCT || step === STEPS.PREVIEW_CROP) && product ? (
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
            {brandLine(product)}
            {product.supplier_name ? ` Поставщик: ${product.supplier_name}.` : ""}
          </div>
          {product.brand_warning ? (
            <div className="muted small" style={{ marginTop: 4 }}>
              {product.brand_warning}
            </div>
          ) : null}
          {product.existing_images_count > 0 ? (
            <div className="outlet-product__existing">
              {product.existing_image_preview ? (
                <img src={product.existing_image_preview} alt="" className="outlet-product__thumb" />
              ) : null}
              <span className="muted small">В МойСклад уже {product.existing_images_count} фото</span>
            </div>
          ) : null}
          <button
            type="button"
            className="secondary"
            style={{ marginTop: "0.75rem" }}
            disabled={busy}
            onClick={() => resetToBarcode("")}
          >
            Другой штрихкод
          </button>
        </div>
      ) : null}

      {step === STEPS.PRODUCT && (
        <div className="outlet-card">
          <label>
            Пол каталога
            <select value={gender} onChange={(e) => setGender(e.target.value)} disabled={busy}>
              <option value="male">Мужской</option>
              <option value="female">Женский</option>
            </select>
          </label>
          {!product?.gender ? (
            <p className="muted small">Пол из папки не прочитался — проверьте выбор.</p>
          ) : null}
          <div className="row-actions" style={{ marginTop: "0.85rem" }}>
            <button type="button" disabled={busy || !status?.ready} onClick={() => cameraRef.current?.click()}>
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
          <p style={{ marginTop: 0 }}>Кадр уйдёт в админку, не в Fashn.</p>
          {croppedPreview ? <img src={croppedPreview} alt="Кадр" className="outlet-preview" /> : null}
          <div className="row-actions">
            <button type="button" disabled={busy} onClick={onSend}>
              {busy ? "Отправляем…" : "В админку"}
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

      {cropOpen && rawSrc ? (
        <ImageCropModal
          imageSrc={rawSrc}
          aspect={CROP_ASPECT}
          title="Кадр для каталога"
          hint="4:5, вещь целиком"
          onCancel={onCropCancel}
          onConfirm={onCropConfirm}
        />
      ) : null}
      {scanOpen ? (
        <BarcodeScanner onDetected={onScanDetected} onClose={() => setScanOpen(false)} />
      ) : null}
    </div>
  );
}
