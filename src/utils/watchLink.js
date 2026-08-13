export function watchSlugFromPath(url) {
	if (!url || typeof url !== "string") return null;
	let path = url.trim();
	try {
		if (/^[a-z][a-z0-9+.-]*:/i.test(path) || path.startsWith("//")) {
			path = new URL(path, "https://local.invalid").pathname;
		}
	} catch {
		return null;
	}
	const cut = path.split(/[?#]/)[0].replace(/\/+$/, "");
	const m = cut.match(/^(?:\/)?watch\/([a-z0-9]+(?:-[a-z0-9]+)*)$/i);
	return m ? m[1].toLowerCase() : null;
}
