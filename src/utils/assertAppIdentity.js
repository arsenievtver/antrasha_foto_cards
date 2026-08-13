/**
 * Жёсткая проверка: клиентский бандл не должен крутиться на work.* и наоборот.
 * Ловит перепутанный nginx upstream / кэш / «установку на домашний экран» с чужого домена.
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
			font-family:system-ui,-apple-system,sans-serif;background:#0c0b0a;color:#f5f0e8;
		">
			<p style="margin:0;letter-spacing:.2em;text-transform:uppercase;font-size:11px;color:#c9a96e">
				ANTRASHA · защита сборки
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
 * @param {"client" | "work"} expected
 * @returns {boolean} true если можно монтировать приложение
 */
export function assertAppIdentity(expected) {
	const host = location.hostname;
	if (isLocalHost(host)) return true;

	if (expected === "client" && isWorkHost(host)) {
		paintFatal(
			"Открыт не тот адрес",
			"Это клиентское приложение ANTRASHA, а домен — рабочий (work). Откройте antrasha.ru или удалите ярлык с домашнего экрана и установите заново с правильного сайта.",
		);
		return false;
	}

	if (expected === "work" && !isWorkHost(host)) {
		paintFatal(
			"Открыт не тот адрес",
			"Это рабочее приложение сотрудников, а домен — клиентский. Откройте work.antrasha.ru. Если на домашнем экране ярлык «ANTRASHA» открывает это — удалите ярлык и поставьте клиентское приложение с antrasha.ru.",
		);
		return false;
	}

	return true;
}
