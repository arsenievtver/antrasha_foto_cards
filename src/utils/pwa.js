export const PWA_INSTALL_DISMISSED_KEY = "antrasha_pwa_install_dismissed";
/** Сколько дней не показывать баннер после «Не сейчас» */
export const PWA_INSTALL_DISMISS_DAYS = 7;

export function isPwaStandalone() {
	if (typeof window === "undefined") return true;
	const mq = window.matchMedia?.("(display-mode: standalone)");
	if (mq?.matches) return true;
	if (window.matchMedia?.("(display-mode: fullscreen)")?.matches) return true;
	// iOS Safari
	if (navigator.standalone === true) return true;
	return false;
}

export function isIosDevice() {
	if (typeof navigator === "undefined") return false;
	const ua = navigator.userAgent || "";
	const iOS = /iPad|iPhone|iPod/.test(ua);
	const iPadOs = navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1;
	return iOS || iPadOs;
}

export function isPwaInstallDismissed() {
	try {
		const raw = localStorage.getItem(PWA_INSTALL_DISMISSED_KEY);
		if (!raw) return false;
		/* старый формат "1" — считаем dismissed до явного сброса / TTL */
		if (raw === "1") return true;
		const until = Number(raw);
		if (!Number.isFinite(until)) return false;
		if (Date.now() >= until) {
			localStorage.removeItem(PWA_INSTALL_DISMISSED_KEY);
			return false;
		}
		return true;
	} catch {
		return true;
	}
}

/** @param {{ permanent?: boolean }} [opts] permanent — после install / «Понятно» с шагами */
export function markPwaInstallDismissed(opts = {}) {
	try {
		if (opts.permanent) {
			localStorage.setItem(PWA_INSTALL_DISMISSED_KEY, "1");
			return;
		}
		const until = Date.now() + PWA_INSTALL_DISMISS_DAYS * 24 * 60 * 60 * 1000;
		localStorage.setItem(PWA_INSTALL_DISMISSED_KEY, String(until));
	} catch {
		/* ignore */
	}
}
