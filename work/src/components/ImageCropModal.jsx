import { useCallback, useState } from "react";
import Cropper from "react-easy-crop";

async function createCroppedBlob(imageSrc, pixelCrop, mime = "image/jpeg") {
  const image = await new Promise((resolve, reject) => {
    const img = new Image();
    img.addEventListener("load", () => resolve(img));
    img.addEventListener("error", reject);
    img.crossOrigin = "anonymous";
    img.src = imageSrc;
  });

  const canvas = document.createElement("canvas");
  const w = Math.max(1, Math.round(pixelCrop.width));
  const h = Math.max(1, Math.round(pixelCrop.height));
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas недоступен");

  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    w,
    h,
  );

  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob(
      (b) => (b ? resolve(b) : reject(new Error("Не удалось обрезать"))),
      mime,
      0.92,
    );
  });
  return blob;
}

export default function ImageCropModal({
  imageSrc,
  aspect,
  title = "Кадрирование",
  hint,
  onCancel,
  onConfirm,
}) {
  const [crop, setCrop] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const onCropComplete = useCallback((_area, pixels) => {
    setCroppedAreaPixels(pixels);
  }, []);

  async function handleConfirm() {
    if (!croppedAreaPixels) return;
    setBusy(true);
    setErr("");
    try {
      const blob = await createCroppedBlob(imageSrc, croppedAreaPixels);
      const file = new File([blob], `outlet-crop-${Date.now()}.jpg`, {
        type: "image/jpeg",
      });
      const previewUrl = URL.createObjectURL(blob);
      onConfirm(file, previewUrl);
    } catch (e) {
      setErr(e.message || "Ошибка обрезки");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scanner-backdrop crop-backdrop" role="presentation" onClick={onCancel}>
      <div
        className="scanner-modal crop-modal"
        role="dialog"
        aria-modal
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        {hint ? <p className="muted" style={{ marginTop: 0 }}>{hint}</p> : null}
        <div className="crop-modal__stage">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={aspect}
            onCropChange={setCrop}
            onZoomChange={setZoom}
            onCropComplete={onCropComplete}
            showGrid
            objectFit="contain"
          />
        </div>
        <label className="crop-modal__zoom">
          <span>Масштаб</span>
          <input
            type="range"
            min={1}
            max={3}
            step={0.01}
            value={zoom}
            onChange={(e) => setZoom(Number(e.target.value))}
          />
        </label>
        {err ? <p className="error">{err}</p> : null}
        <div className="row-actions" style={{ marginTop: "0.75rem" }}>
          <button type="button" className="secondary" onClick={onCancel} disabled={busy}>
            Отмена
          </button>
          <button type="button" onClick={handleConfirm} disabled={busy || !croppedAreaPixels}>
            {busy ? "Обрезаем…" : "Применить кадр"}
          </button>
        </div>
      </div>
    </div>
  );
}
