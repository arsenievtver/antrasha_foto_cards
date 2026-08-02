import { useEffect, useRef, useState } from "react";
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

/**
 * Fullscreen barcode scanner modal.
 * @param {{ onDetected: (code: string) => void, onClose: () => void }} props
 */
export default function BarcodeScanner({ onDetected, onClose }) {
  const regionId = useRef(`bc-scan-${Math.random().toString(36).slice(2, 9)}`).current;
  const scannerRef = useRef(null);
  const handledRef = useRef(false);
  const onDetectedRef = useRef(onDetected);
  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(true);

  onDetectedRef.current = onDetected;

  useEffect(() => {
    let cancelled = false;
    const scanner = new Html5Qrcode(regionId, { formatsToSupport: BARCODE_FORMATS });
    scannerRef.current = scanner;

    (async () => {
      try {
        await scanner.start(
          { facingMode: "environment" },
          {
            fps: 10,
            qrbox: (viewW, viewH) => {
              const w = Math.min(Math.floor(viewW * 0.88), 360);
              const h = Math.min(Math.floor(viewH * 0.28), 140);
              return { width: w, height: h };
            },
            aspectRatio: 1.777,
          },
          (decoded) => {
            if (handledRef.current || cancelled) return;
            const code = String(decoded || "").trim();
            if (!code) return;
            handledRef.current = true;
            onDetectedRef.current?.(code);
          },
          () => {},
        );
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
      if (s) {
        s.stop()
          .then(() => s.clear())
          .catch(() => {});
      }
    };
  }, [regionId]);

  return (
    <div className="scanner-backdrop" role="presentation">
      <div className="scanner-modal" role="dialog" aria-modal aria-label="Сканер штрихкода">
        <div className="scanner-modal__head">
          <strong>Сканер штрихкода</strong>
          <button type="button" className="secondary" onClick={onClose}>
            Закрыть
          </button>
        </div>
        <p className="scanner-modal__hint">Наведите камеру на штрихкод товара</p>
        <div id={regionId} className="scanner-modal__view" />
        {starting ? <p className="muted">Запуск камеры…</p> : null}
        {err ? <p className="error">{err}</p> : null}
      </div>
    </div>
  );
}
