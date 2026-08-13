/**
 * Жёсткая проверка: рабочий бандл не должен крутиться на клиентском домене.
 */

function isLocalHost(hostname) {
  if (!hostname) return true;
  const h = hostname.toLowerCase();
  if (h === "localhost" || h === "127.0.0.1" || h === "::1") return true;
  if (/^192\.168\.\d+\.\d+$/.test(h)) return true;
  if (/^10\.\d+\.\d+\.\d+$/.test(h)) return true;
  if (/^172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+$/.test(h)) return true;
  return false;
}

function isWorkHost(hostname) {
  const h = (hostname || "").toLowerCase();
  return h === "work.antrasha.ru" || h.startsWith("work.");
}

function paintFatal(title, detail) {
  const root = document.getElementById("root") || document.body;
  root.innerHTML = `
    <div style="
      box-sizing:border-box;min-height:100dvh;padding:32px 20px;
      display:flex;flex-direction:column;justify-content:center;gap:12px;
      font-family:system-ui,-apple-system,sans-serif;background:#1a1c1f;color:#f2f1ee;
    ">
      <p style="margin:0;letter-spacing:.16em;text-transform:uppercase;font-size:11px;opacity:.65">
        ANTRASHA · рабочее
      </p>
      <h1 style="margin:0;font-size:1.35rem;font-weight:600;line-height:1.25">${title}</h1>
      <p style="margin:0;opacity:.78;line-height:1.45;max-width:28rem">${detail}</p>
      <p style="margin:8px 0 0;opacity:.5;font-size:12px;word-break:break-all">
        host: ${location.host}<br/>href: ${location.href}
      </p>
    </div>
  `;
}

/**
 * @returns {boolean}
 */
export function assertAppIdentity() {
  const host = location.hostname;
  if (isLocalHost(host)) return true;
  if (!isWorkHost(host)) {
    paintFatal(
      "Открыт не тот адрес",
      "Это рабочее приложение сотрудников. Клиентское — на antrasha.ru. Если ярлык «ANTRASHA» открывает рабочее — удалите его с домашнего экрана и установите заново с правильного сайта.",
    );
    return false;
  }
  return true;
}
