const WATCH_PATH_RE = /^\/watch\/([a-z0-9]+(?:-[a-z0-9]+)*)$/i;

export function watchSlugFromPath(url) {
	const path = (url || "").trim().split("?")[0];
	const m = path.match(WATCH_PATH_RE);
	return m ? m[1].toLowerCase() : null;
}
