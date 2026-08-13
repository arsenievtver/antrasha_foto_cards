import { createContext, useCallback, useContext, useMemo, useState } from "react";
import VideoModal from "../components/VideoModal";

const VideoModalContext = createContext(null);

export function VideoModalProvider({ children }) {
	const [slug, setSlug] = useState(null);

	const openVideo = useCallback((nextSlug) => {
		const s = String(nextSlug || "")
			.trim()
			.toLowerCase();
		if (s) setSlug(s);
	}, []);

	const closeVideo = useCallback(() => setSlug(null), []);

	const value = useMemo(
		() => ({ openVideo, closeVideo, slug }),
		[openVideo, closeVideo, slug],
	);

	return (
		<VideoModalContext.Provider value={value}>
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
