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

const SCAN_CONFIG = {
  fps: 12,
  qrbox: (viewW, viewH) => {
    const w = Math.min(Math.floor(viewW * 0.92), 420);
    const h = Math.min(Math.floor(viewH * 0.32), 160);
    return { width: Math.max(180, w), height: Math.max(80, h) };
  },
  aspectRatio: 1.777,
};

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function cameraErrorMessage(e) {
  const name = e?.name || "";
  const msg = String(e?.message || e || "");
  if (name === "NotAllowedError" || /permission|denied|not allowed/i.test(msg)) {
    return "Нет доступа к камере. Разрешите камеру для work.antrasha.ru в настройках браузера/сайта.";
  }
  if (name === "NotFoundError" || /not found|no camera/i.test(msg)) {
    return "Камера не найдена на устройстве.";
  }
  if (name === "NotReadableError" || /in use|track/i.test(msg)) {
    return "Камера занята другим приложением. Закройте его и повторите.";
  }
  if (name === "OverconstrainedError" || /constraint/i.test(msg)) {
    return "Камера не приняла настройки. Нажмите «Включить камеру» ещё раз.";
  }
  if (/secure|https|only/i.test(msg)) {
    return "Камера доступна только по HTTPS.";
  }
  return msg || "Не удалось открыть камеру";
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

async function startWithFallback(scanner, onSuccess, onError) {
  /** Сначала простой facingMode — HD constraints в start() часто ломают iOS Safari. */
  const attempts = [
    { facingMode: { ideal: "environment" } },
    { facingMode: "environment" },
    true, // любая камера
  ];
  let lastErr = null;
  for (const cam of attempts) {
    try {
      await scanner.start(cam, SCAN_CONFIG, onSuccess, onError);
      return;
    } catch (e) {
      lastErr = e;
      try {
        if (scanner.isScanning) await scanner.stop();
      } catch {
        /* ignore */
      }
    }
  }
  throw lastErr || new Error("Не удалось открыть камеру");
}

async function enhanceRunningCamera(scanner) {
  await sleep(350);
  try {
    const caps = scanner.getRunningTrackCapabilities?.() || {};
    const next = {};
    if (
      (Array.isArray(caps.focusMode) && caps.focusMode.includes("continuous")) ||
      typeof caps.focusMode === "string"
    ) {
      next.focusMode = "continuous";
    }
    // Мягкий апгрейд разрешения — ideal, без Overconstrained на старте.
    if (caps.width || caps.height) {
      next.width = { ideal: 1920 };
      next.height = { ideal: 1080 };
    }
    if (Object.keys(next).length) {
      await scanner.applyVideoConstraints(next);
    }
  } catch {
    /* ignore — зум/фокус ниже важнее */
  }
}

/**
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
  const startingRef = useRef(false);

  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(false);
  const [running, setRunning] = useState(false);
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

  const stopScanner = useCallback(async () => {
    const s = scannerRef.current;
    scannerRef.current = null;
    zoomFeatureRef.current = null;
    torchFeatureRef.current = null;
    if (s) {
      try {
        if (s.isScanning) await s.stop();
      } catch {
        /* ignore */
      }
      try {
        s.clear();
      } catch {
        /* ignore */
      }
    }
    setRunning(false);
    setTorchOn(false);
    setTorchSupported(false);
    setZoomSupported(false);
  }, []);

  useEffect(() => {
    return () => {
      void stopScanner();
    };
  }, [stopScanner]);

  /** Старт по клику — на iOS getUserMedia требует user gesture. */
  async function startCamera() {
    if (startingRef.current || running) return;
    startingRef.current = true;
    setStarting(true);
    setErr("");
    await stopScanner();

    const scanner = new Html5Qrcode(regionId, SCANNER_CONFIG);
    scannerRef.current = scanner;

    try {
      await startWithFallback(
        scanner,
        (decoded) => emitCode(decoded),
        () => {},
      );

      await enhanceRunningCamera(scanner);

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
          const preferred = Math.min(max, Math.max(min, min + (max - min) * 0.35));
          const startZoom = Math.round(preferred / step) * step;
          try {
            await zf.apply(startZoom);
          } catch {
            /* ignore */
          }
          setZoomSupported(true);
          setZoomMin(min);
          setZoomMax(max);
          setZoomStep(step);
          setZoom(startZoom);
        }

        if (tf?.isSupported?.()) {
          setTorchSupported(true);
        }
      } catch {
        /* capabilities optional */
      }

      setRunning(true);
    } catch (e) {
      setErr(cameraErrorMessage(e));
      await stopScanner();
    } finally {
      startingRef.current = false;
      setStarting(false);
    }
  }

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
          Нажмите «Включить камеру», держите телефон в 20–40 см. Для мелких кодов — зум или «С фото».
        </p>
        <div id={regionId} className="scanner-modal__view" />

        {!running ? (
          <div className="scanner-controls">
            <button type="button" disabled={starting} onClick={() => void startCamera()}>
              {starting ? "Открываем…" : "Включить камеру"}
            </button>
          </div>
        ) : null}

        {running && (zoomSupported || torchSupported) ? (
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
            disabled={fileBusy}
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

        {err ? <p className="error">{err}</p> : null}
      </div>
    </div>
  );
}
