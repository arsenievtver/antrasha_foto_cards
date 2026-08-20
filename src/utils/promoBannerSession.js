const KEY = "antrasha_promo_banner_session_seen";

function readIds() {
	try {
		const raw = sessionStorage.getItem(KEY);
		if (!raw) return [];
		const parsed = JSON.parse(raw);
		return Array.isArray(parsed) ? parsed.map(String) : [];
	} catch {
		return [];
	}
}

export function wasPromoBannerSeenThisSession(bannerId) {
	if (!bannerId) return false;
	return readIds().includes(String(bannerId));
}

export function markPromoBannerSeenThisSession(bannerId) {
	if (!bannerId) return;
	const id = String(bannerId);
	const ids = readIds();
	if (ids.includes(id)) return;
	try {
		sessionStorage.setItem(KEY, JSON.stringify([...ids, id]));
	} catch {
		/* private mode / quota */
	}
}
