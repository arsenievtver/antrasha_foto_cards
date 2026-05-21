const REF_KEY = "antrasha_ref";

/** Сохраняет ?ref= из URL (first-touch в рамках вкладки). */
export function captureRefFromUrl() {
	const ref = new URLSearchParams(window.location.search).get("ref");
	if (!ref?.trim()) return;
	sessionStorage.setItem(REF_KEY, ref.trim());
}

export function getStoredRef() {
	return sessionStorage.getItem(REF_KEY) || null;
}

/** Убирает ?ref из адресной строки после сохранения. */
export function stripRefFromUrl() {
	const params = new URLSearchParams(window.location.search);
	if (!params.has("ref")) return;
	params.delete("ref");
	const q = params.toString();
	const path = window.location.pathname + (q ? `?${q}` : "");
	window.history.replaceState(null, "", path + window.location.hash);
}
