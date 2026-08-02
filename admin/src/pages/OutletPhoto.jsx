import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchOutletPhotoStatus,
  generateOutletPhoto,
  lookupOutletPhotoBarcode,
  uploadOutletPhotoToMoySklad,
} from "../api.js";
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
      });
      setStep(STEPS.SUCCESS);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  const resultSrc = resultB64
    ? `data:${resultMime};base64,${resultB64}`
    : "";

  if (loadingStatus && !status) {
    return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;
  }

  return (
    <div className="outlet-photo">
      <h2 style={{ marginTop: 0 }}>Аутлет: фото</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, maxWidth: 560 }}>
        Штрихкод → товар в МойСклад → кадр → Fashn (каталог) → загрузка изображения в товар.
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
            <div style={{ fontSize: "0.85rem", color: "var(--muted)", marginTop: 4 }}>
              product_id: {product.product_id}
              {product.entity_type === "variant" && product.variant_id
                ? ` · найден как модификация ${product.variant_id}`
                : ""}
            </div>
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
          <p style={{ marginTop: 0 }}>Кадр 4:5 — отправить в Fashn?</p>
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
              {busy ? "Генерация… (до ~5 мин)" : "Сгенерировать"}
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
        <div style={{ maxWidth: 420 }}>
          <p style={{ marginTop: 0 }}>Результат Fashn</p>
          {resultSrc ? (
            <img
              src={resultSrc}
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
          {resultSrc ? (
            <img
              src={resultSrc}
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
