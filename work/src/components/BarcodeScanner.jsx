import { useCallback, useEffect, useRef, useState } from "react";
import { Html5Qrcode, Html5QrcodeSupportedFormats } from "html5-qrcode";

const BARCODE_FORMATS = [
  Html5QrcodeSupportedFormats.EAN_13,
  Html5QrcodeSupportedFormats.EAN_8,
  Html5QrcodeSupportedFormats.CODE_128,
  Html5QrcodeSupportedFormats.CODE_39,
  Html5QrcodeSupportedFormats.UPC_A,
  Html5QrcodeSupportedFormats.UPC_E,
  Html5QrcodeSupportedFormats.ITF,
];

const SCANNER_CONFIG = {
  formatsToSupport: BARCODE_FORMATS,
  useBarCodeDetectorIfSupported: true,
};

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function decodeBarcodeFromFile(file) {
  const id = `bc-file-${Math.random().toString(36).slice(2, 9)}`;
  const el = document.createElement("div");
  el.id = id;
  el.setAttribute("aria-hidden", "true");
  el.style.cssText = "position:fixed;left:-9999px;width:1px;height:1px;overflow:hidden;";
  document.body.appendChild(el);
  const reader = new Html5Qrcode(id, SCANNER_CONFIG);
  try {
    const text = await reader.scanFile(file, false);
    return String(text || "").trim();
  } finally {
    try {
      reader.clear();
    } catch {
      /* ignore */
    }
    el.remove();
  }
}

/**
 * Fullscreen barcode scanner: HD + focus + zoom/torch when available + photo decode fallback.
 * @param {{ onDetected: (code: string) => void, onClose: () => void }} props
 */
export default function BarcodeScanner({ onDetected, onClose }) {
  const regionId = useRef(`bc-scan-${Math.random().toString(36).slice(2, 9)}`).current;
  const scannerRef = useRef(null);
  const handledRef = useRef(false);
  const onDetectedRef = useRef(onDetected);
  const fileRef = useRef(null);
  const zoomFeatureRef = useRef(null);
  const torchFeatureRef = useRef(null);

  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(true);
  const [fileBusy, setFileBusy] = useState(false);
  const [torchOn, setTorchOn] = useState(false);
  const [torchSupported, setTorchSupported] = useState(false);
  const [zoomSupported, setZoomSupported] = useState(false);
  const [zoomMin, setZoomMin] = useState(1);
  const [zoomMax, setZoomMax] = useState(1);
  const [zoomStep, setZoomStep] = useState(0.1);
  const [zoom, setZoom] = useState(1);

  onDetectedRef.current = onDetected;

  const emitCode = useCallback((raw) => {
    if (handledRef.current) return;
    const code = String(raw || "").trim();
    if (!code) return;
    handledRef.current = true;
    onDetectedRef.current?.(code);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const scanner = new Html5Qrcode(regionId, SCANNER_CONFIG);
    scannerRef.current = scanner;

    (async () => {
      try {
        await scanner.start(
          {
            facingMode: "environment",
            width: { ideal: 1920 },
            height: { ideal: 1080 },
          },
          {
            fps: 12,
            qrbox: (viewW, viewH) => {
              const w = Math.min(Math.floor(viewW * 0.92), 420);
              const h = Math.min(Math.floor(viewH * 0.32), 160);
              return { width: Math.max(180, w), height: Math.max(80, h) };
            },
            aspectRatio: 1.777,
          },
          (decoded) => {
            if (cancelled) return;
            emitCode(decoded);
          },
          () => {},
        );

        // Камера должна быть активна, чтобы применить focus/zoom.
        await sleep(400);
        if (cancelled) return;

        try {
          const caps = scanner.getRunningTrackCapabilities?.() || {};
          const next = {};
          if (Array.isArray(caps.focusMode) && caps.focusMode.includes("continuous")) {
            next.focusMode = "continuous";
          } else if (typeof caps.focusMode === "string") {
            next.focusMode = "continuous";
          }
          if (Object.keys(next).length) {
            await scanner.applyVideoConstraints(next);
          }
        } catch {
          /* device may ignore focusMode */
        }

        if (cancelled) return;

        try {
          const camCaps = scanner.getRunningTrackCameraCapabilities();
          const zf = camCaps.zoomFeature();
          const tf = camCaps.torchFeature();
          zoomFeatureRef.current = zf;
          torchFeatureRef.current = tf;

          if (zf?.isSupported?.()) {
            const min = Number(zf.min?.() ?? 1);
            const max = Number(zf.max?.() ?? min);
            const step = Number(zf.step?.() || 0.1) || 0.1;
            // Лёгкий зум по умолчанию — мелкие EAN читаются на нормальной дистанции.
            const preferred = Math.min(max, Math.max(min, min + (max - min) * 0.35));
            const startZoom = Math.round(preferred / step) * step;
            try {
              await zf.apply(startZoom);
            } catch {
              /* ignore */
            }
            if (!cancelled) {
              setZoomSupported(true);
              setZoomMin(min);
              setZoomMax(max);
              setZoomStep(step);
              setZoom(startZoom);
            }
          }

          if (tf?.isSupported?.() && !cancelled) {
            setTorchSupported(true);
          }
        } catch {
          /* capabilities API missing on some browsers */
        }

        if (!cancelled) setStarting(false);
      } catch (e) {
        if (!cancelled) {
          setStarting(false);
          setErr(e?.message || "Не удалось открыть камеру");
        }
      }
    })();

    return () => {
      cancelled = true;
      const s = scannerRef.current;
      scannerRef.current = null;
      zoomFeatureRef.current = null;
      torchFeatureRef.current = null;
      if (s) {
        s.stop()
          .then(() => s.clear())
          .catch(() => {});
      }
    };
  }, [emitCode, regionId]);

  async function onZoomChange(value) {
    const next = Number(value);
    setZoom(next);
    const zf = zoomFeatureRef.current;
    if (!zf?.isSupported?.()) return;
    try {
      await zf.apply(next);
    } catch (e) {
      setErr(e?.message || "Зум недоступен");
    }
  }

  async function toggleTorch() {
    const tf = torchFeatureRef.current;
    if (!tf?.isSupported?.()) return;
    const next = !torchOn;
    try {
      await tf.apply(next);
      setTorchOn(next);
    } catch (e) {
      setErr(e?.message || "Фонарик недоступен");
    }
  }

  async function onPickFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || handledRef.current) return;
    setFileBusy(true);
    setErr("");
    try {
      const code = await decodeBarcodeFromFile(file);
      if (!code) throw new Error("Штрихкод на фото не найден");
      emitCode(code);
    } catch (ex) {
      setErr(
        ex?.message?.includes("No QR code") || ex?.message?.includes("No MultiFormat")
          ? "На фото штрихкод не найден — снимите крупнее и чётче"
          : ex?.message || "Не удалось распознать фото",
      );
    } finally {
      setFileBusy(false);
    }
  }

  return (
    <div className="scanner-backdrop" role="presentation">
      <div className="scanner-modal" role="dialog" aria-modal aria-label="Сканер штрихкода">
        <div className="scanner-modal__head">
          <strong>Сканер штрихкода</strong>
          <button type="button" className="secondary" onClick={onClose}>
            Закрыть
          </button>
        </div>
        <p className="scanner-modal__hint">
          Держите телефон на расстоянии 20–40 см. Для мелких кодов увеличьте зум или снимите фото.
        </p>
        <div id={regionId} className="scanner-modal__view" />

        {!starting && (zoomSupported || torchSupported) ? (
          <div className="scanner-controls">
            {zoomSupported ? (
              <label className="scanner-controls__zoom">
                <span>Зум {zoom.toFixed(1)}×</span>
                <input
                  type="range"
                  min={zoomMin}
                  max={zoomMax}
                  step={zoomStep}
                  value={zoom}
                  onChange={(e) => void onZoomChange(e.target.value)}
                />
              </label>
            ) : null}
            {torchSupported ? (
              <button
                type="button"
                className={torchOn ? undefined : "secondary"}
                onClick={() => void toggleTorch()}
              >
                {torchOn ? "Фонарик вкл" : "Фонарик"}
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="scanner-controls scanner-controls--file">
          <button
            type="button"
            className="secondary"
            disabled={fileBusy || starting}
            onClick={() => fileRef.current?.click()}
          >
            {fileBusy ? "Распознаём…" : "С фото / галереи"}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => void onPickFile(e)}
          />
        </div>

        {starting ? <p className="muted">Запуск камеры…</p> : null}
        {err ? <p className="error">{err}</p> : null}
      </div>
    </div>
  );
}
