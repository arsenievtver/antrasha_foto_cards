import {
	createContext,
	useCallback,
	useContext,
	useLayoutEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import VideoModal from "../components/VideoModal";
import { watchSlugFromPath } from "../utils/watchLink";

const VideoModalContext = createContext(null);

function WatchLocationBridge({ openVideo }) {
	const location = useLocation();
	const navigate = useNavigate();
	const handledKey = useRef(null);

	useLayoutEffect(() => {
		const urlSlug = watchSlugFromPath(location.pathname);
		if (!urlSlug) return;
		if (handledKey.current === location.key) return;
		handledKey.current = location.key;
		openVideo(urlSlug);
		const idx = window.history.state?.idx;
		if (typeof idx === "number" && idx > 0) {
			navigate(-1);
		} else {
			navigate("/", { replace: true });
		}
	}, [location, openVideo, navigate]);

	return null;
}

export function VideoModalProvider({ children }) {
	const [slug, setSlug] = useState(null);

	const openVideo = useCallback((nextSlug) => {
		const s = String(nextSlug || "")
			.trim()
			.toLowerCase();
		if (s) setSlug(s);
	}, []);

	const closeVideo = useCallback(() => setSlug(null), []);

	useLayoutEffect(() => {
		const onClick = (e) => {
			if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
				return;
			}
			if (e.button != null && e.button !== 0) return;
			const a = e.target instanceof Element ? e.target.closest("a") : null;
			if (!a) return;
			const href = a.getAttribute("href");
			const nextSlug = watchSlugFromPath(href || "");
			if (!nextSlug) return;
			e.preventDefault();
			e.stopPropagation();
			openVideo(nextSlug);
		};
		document.addEventListener("click", onClick, true);
		return () => document.removeEventListener("click", onClick, true);
	}, [openVideo]);

	const value = useMemo(
		() => ({ openVideo, closeVideo, slug }),
		[openVideo, closeVideo, slug],
	);

	return (
		<VideoModalContext.Provider value={value}>
			<WatchLocationBridge openVideo={openVideo} />
			{children}
			<VideoModal slug={slug} onClose={closeVideo} />
		</VideoModalContext.Provider>
	);
}

export function useVideoModal() {
	const ctx = useContext(VideoModalContext);
	if (!ctx) {
		return {
			openVideo: () => {},
			closeVideo: () => {},
			slug: null,
		};
	}
	return ctx;
}
