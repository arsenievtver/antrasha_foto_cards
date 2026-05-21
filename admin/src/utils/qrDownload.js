import QRCode from "qrcode";

const QR_OPTS = {
  errorCorrectionLevel: "M",
  margin: 2,
  color: { dark: "#000000", light: "#ffffff" },
};

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function triggerDataUrlDownload(dataUrl, filename) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = filename;
  a.click();
}

/** PNG с белым фоном — соцсети, монтаж, печать. */
export async function downloadQrPng(url, { slug, sizePx }) {
  const dataUrl = await QRCode.toDataURL(url, {
    ...QR_OPTS,
    width: sizePx,
    type: "image/png",
  });
  triggerDataUrlDownload(dataUrl, `antrasha-qr-${slug}-${sizePx}.png`);
}

/** SVG — сайты, Figma, масштаб без потери качества. */
export async function downloadQrSvg(url, { slug }) {
  const svg = await QRCode.toString(url, { ...QR_OPTS, type: "svg" });
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  triggerDownload(blob, `antrasha-qr-${slug}.svg`);
}

/** PNG на прозрачном фоне — наложение на видео/баннеры. */
export async function downloadQrPngTransparent(url, { slug, sizePx }) {
  const dataUrl = await QRCode.toDataURL(url, {
    ...QR_OPTS,
    width: sizePx,
    type: "image/png",
    color: { dark: "#000000", light: "#00000000" },
  });
  triggerDataUrlDownload(dataUrl, `antrasha-qr-${slug}-${sizePx}-transparent.png`);
}

export async function qrPreviewDataUrl(url, sizePx = 200) {
  return QRCode.toDataURL(url, { ...QR_OPTS, width: sizePx, type: "image/png" });
}
