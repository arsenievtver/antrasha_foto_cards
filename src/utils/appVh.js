function currentViewportHeight() {
	const vv = window.visualViewport;
	const inner = window.innerHeight || 0;
	if (!vv) return inner;
	return Math.max(inner, Math.round(vv.height + vv.offsetTop));
}

export function syncAppVh() {
	const h = currentViewportHeight();
	if (h > 0) {
		document.documentElement.style.setProperty("--app-vh", `${h}px`);
	}
}

export function bindAppVh() {
	syncAppVh();
	window.addEventListener("resize", syncAppVh);
	window.addEventListener("orientationchange", syncAppVh);
	window.visualViewport?.addEventListener("resize", syncAppVh);
	window.visualViewport?.addEventListener("scroll", syncAppVh);
	return () => {
		window.removeEventListener("resize", syncAppVh);
		window.removeEventListener("orientationchange", syncAppVh);
		window.visualViewport?.removeEventListener("resize", syncAppVh);
		window.visualViewport?.removeEventListener("scroll", syncAppVh);
	};
}
