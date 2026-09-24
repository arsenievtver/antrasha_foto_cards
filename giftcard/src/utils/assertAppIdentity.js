function isLocalHost(hostname) {
  if (!hostname) return true;
  const host = hostname.toLowerCase();
  if (host === "localhost" || host === "127.0.0.1" || host === "::1") return true;
  if (/^192\.168\.\d+\.\d+$/.test(host)) return true;
  if (/^10\.\d+\.\d+\.\d+$/.test(host)) return true;
  if (/^172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+$/.test(host)) return true;
  return false;
}

function isGiftcardHost(hostname) {
  const host = (hostname || "").toLowerCase();
  return host === "giftcard.antrasha.ru" || host.startsWith("giftcard.");
}

export function assertAppIdentity() {
  const host = location.hostname;
  if (isLocalHost(host) || isGiftcardHost(host)) return true;
  const root = document.getElementById("root") || document.body;
  root.textContent = "Это приложение сертификатов открывается на giftcard.antrasha.ru";
  return false;
}
