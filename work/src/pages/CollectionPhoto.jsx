import { useCallback, useEffect, useRef, useState } from "react";
import {
  createCollectionPhotoJob,
  fetchCollectionPhotoStatus,
  lookupCollectionBarcode,
} from "../api.js";
import BarcodeScanner from "../components/BarcodeScanner.jsx";
import ImageCropModal from "../components/ImageCropModal.jsx";

const MAX_BARCODES = 3;

const STEPS = {
  BARCODE: "barcode",
  PRODUCT: "product",
  PHOTO_SOURCE: "photo_source",
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

function productGender(products) {
  const genders = products.map((p) => p.gender).filter((g) => g === "male" || g === "female");
  if (!genders.length) return null;
  const unique = [...new Set(genders)];
  if (unique.length === 1) return unique[0];
  return genders[0];
}

function productShortLine(p) {
  const head = p.article || p.name || p.barcode;
  return p.article && p.name ? `${head} · ${p.name}` : head;
}

export default function CollectionPhoto() {
  const [status, setStatus] = useState(null);
  const [step, setStep] = useState(STEPS.BARCODE);
  const [barcode, setBarcode] = useState("");
  const [products, setProducts] = useState([]);
  const [gender, setGender] = useState("male");
  const [rawSrc, setRawSrc] = useState("");
  const [cropOpen, setCropOpen] = useState(false);
  const [croppedFile, setCroppedFile] = useState(null);
  const [croppedPreview, setCroppedPreview] = useState("");
  const [scanOpen, setScanOpen] = useState(false);
  const [scanForAdd, setScanForAdd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [notice, setNotice] = useState("");
  const cameraRef = useRef(null);
  const galleryRef = useRef(null);

  const primaryProduct = products[0] || null;

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
    setProducts([]);
    setRawSrc("");
    setCropOpen(false);
    setCroppedFile(null);
    setCroppedPreview("");
    setScanOpen(false);
    setScanForAdd(false);
    setErr("");
    setNotice(message || "");
    if (cameraRef.current) cameraRef.current.value = "";
    if (galleryRef.current) galleryRef.current.value = "";
  }

  function applyProductsFound(list) {
    setProducts(list);
    const g = productGender(list);
    if (g) setGender(g);
    setStep(STEPS.PRODUCT);
  }

  async function resolveBarcode(codeRaw) {
    const code = String(codeRaw || "").trim();
    if (!code) {
      setErr("Введите штрихкод");
      return null;
    }
    setBusy(true);
    setErr("");
    setNotice("");
    try {
      return await lookupCollectionBarcode(code);
    } catch (ex) {
      setErr(ex.message);
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function runLookup(codeRaw) {
    const data = await resolveBarcode(codeRaw);
    if (!data) return;
    setBarcode(data.barcode || String(codeRaw).trim());
    applyProductsFound([data]);
  }

  async function runAddBarcode(codeRaw) {
    const code = String(codeRaw || "").trim();
    if (!code) {
      setErr("Введите штрихкод");
      return;
    }
    if (products.some((p) => p.barcode === code)) {
      setErr("Этот штрихкод уже в списке");
      return;
    }
    if (products.length >= MAX_BARCODES) {
      setErr(`Не больше ${MAX_BARCODES} позиций на один кадр`);
      return;
    }
    const data = await resolveBarcode(code);
    if (!data) return;
    if (products.some((p) => p.product_id === data.product_id)) {
      setErr("Эта позиция уже в списке");
      return;
    }
    applyProductsFound([...products, data]);
    setBarcode("");
  }

  function onLookup(e) {
    e?.preventDefault?.();
    void runLookup(barcode);
  }

  const runLookupRef = useRef(runLookup);
  runLookupRef.current = runLookup;
  const runAddRef = useRef(runAddBarcode);
  runAddRef.current = runAddBarcode;

  const onScanDetected = useCallback((code) => {
    setScanOpen(false);
    if (scanForAdd) {
      void runAddRef.current(code);
      setScanForAdd(false);
    } else {
      void runLookupRef.current(code);
    }
  }, [scanForAdd]);

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
    if (galleryRef.current) galleryRef.current.value = "";
    setStep(STEPS.PHOTO_SOURCE);
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
    if (!croppedFile || !primaryProduct?.barcode) {
      setErr("Сначала сделайте кадр");
      return;
    }
    setBusy(true);
    setErr("");
    const extra = products.slice(1).map((p) => p.barcode).filter(Boolean);
    try {
      await createCollectionPhotoJob({
        gender,
        file: croppedFile,
        barcode: primaryProduct.barcode,
        extraBarcodes: extra,
      });
      const names = products.map((p) => p.article || p.name || p.barcode).join(", ");
      resetToBarcode(`В админке: ${names}`);
    } catch (ex) {
      setErr(ex.message || "Не удалось отправить");
    } finally {
      setBusy(false);
    }
  }

  function removeProductAt(index) {
    if (index <= 0 || index >= products.length) return;
    setProducts(products.filter((_, i) => i !== index));
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
          <p className="muted small" style={{ marginTop: 0 }}>
            Один кадр можно привязать до {MAX_BARCODES} штрихкодов — например куртка и брюки комплекта.
          </p>
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

      {(step === STEPS.PRODUCT || step === STEPS.PHOTO_SOURCE || step === STEPS.PREVIEW_CROP) && products.length ? (
        <div className="outlet-card">
          <div className="muted small" style={{ marginBottom: "0.5rem" }}>
            {products.length > 1
              ? `Комплект · ${products.length} позиции · одно фото на все`
              : "Одна позиция"}
          </div>
          <ul className="collection-product-list">
            {products.map((p, i) => (
              <li key={p.product_id || p.barcode} className="collection-product-list__item">
                <div>
                  <div className="outlet-product__name" style={{ marginBottom: 2 }}>
                    {productShortLine(p)}
                  </div>
                  <div className="muted small">{p.barcode}</div>
                </div>
                {i > 0 ? (
                  <button
                    type="button"
                    className="secondary collection-product-list__remove"
                    disabled={busy}
                    onClick={() => removeProductAt(i)}
                  >
                    Убрать
                  </button>
                ) : null}
              </li>
            ))}
          </ul>
          {primaryProduct ? (
            <>
              <div className="muted small" style={{ marginTop: "0.65rem" }}>
                {brandLine(primaryProduct)}
                {primaryProduct.supplier_name ? ` Поставщик: ${primaryProduct.supplier_name}.` : ""}
              </div>
              {primaryProduct.brand_warning ? (
                <div className="muted small" style={{ marginTop: 4 }}>
                  {primaryProduct.brand_warning}
                </div>
              ) : null}
            </>
          ) : null}
          {products.length < MAX_BARCODES && step !== STEPS.PREVIEW_CROP ? (
            <div className="row-actions" style={{ marginTop: "0.75rem" }}>
              <button
                type="button"
                className="secondary"
                disabled={busy || !status?.ready}
                onClick={() => {
                  setErr("");
                  setScanForAdd(true);
                  setScanOpen(true);
                }}
              >
                + ещё штрихкод
              </button>
            </div>
          ) : null}
          <button
            type="button"
            className="secondary"
            style={{ marginTop: "0.75rem" }}
            disabled={busy}
            onClick={() => resetToBarcode("")}
          >
            Сбросить
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
          {!productGender(products) ? (
            <p className="muted small">Пол из папки не прочитался — проверьте выбор.</p>
          ) : null}
          <button
            type="button"
            style={{ marginTop: "0.85rem" }}
            disabled={busy || !status?.ready}
            onClick={() => setStep(STEPS.PHOTO_SOURCE)}
          >
            Дальше — фото
          </button>
        </div>
      )}

      {step === STEPS.PHOTO_SOURCE && (
        <div className="outlet-card">
          <p style={{ marginTop: 0 }}>Откуда взять кадр?</p>
          <div className="row-actions">
            <button type="button" disabled={busy || !status?.ready} onClick={() => cameraRef.current?.click()}>
              С камеры
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy || !status?.ready}
              onClick={() => galleryRef.current?.click()}
            >
              Из галереи
            </button>
          </div>
          <p className="muted small" style={{ marginBottom: 0 }}>
            Можно сначала сфотографировать несколько вещей, потом выбрать нужный снимок в галерее.
          </p>
          <button
            type="button"
            className="secondary"
            style={{ marginTop: "0.75rem" }}
            disabled={busy}
            onClick={() => setStep(STEPS.PRODUCT)}
          >
            Назад
          </button>
          <input
            ref={cameraRef}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => openSource(e.target.files?.[0])}
          />
          <input
            ref={galleryRef}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => openSource(e.target.files?.[0])}
          />
        </div>
      )}

      {step === STEPS.PREVIEW_CROP && (
        <div className="outlet-card">
          <p style={{ marginTop: 0 }}>
            Кадр уйдёт в админку
            {products.length > 1 ? ` и потом на ${products.length} позиции в МойСклад` : ""}, не в Fashn.
          </p>
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
                setStep(STEPS.PHOTO_SOURCE);
              }}
            >
              Другое фото
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
        <BarcodeScanner
          onDetected={onScanDetected}
          onClose={() => {
            setScanOpen(false);
            setScanForAdd(false);
          }}
        />
      ) : null}
    </div>
  );
}
