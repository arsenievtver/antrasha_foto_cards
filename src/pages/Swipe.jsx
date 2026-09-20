import {
	useState,
	useMemo,
	useRef,
	useEffect,
	useLayoutEffect,
	useCallback,
} from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
	motion,
	AnimatePresence,
	useReducedMotion,
	useMotionValue,
	useTransform,
	animate,
} from "framer-motion";
import {
	fetchFeedPublicSettings,
	loadFeed,
	postInteraction,
} from "../api/client";
import SwipeCheckpoint from "../components/SwipeCheckpoint.jsx";
import SwipeFeedEmpty from "../components/SwipeFeedEmpty.jsx";
import PushNotifyPrompt from "../components/PushNotifyPrompt";
import { useAuth } from "../context/AuthContext";
import "./Swipe.css";

const SWIPE_COACH_KEY = "swipe_coach_v2_dismissed";

const DRAG_FEEDBACK_PX = 50;
const COMMIT_OFFSET_PX = 80;
const COMMIT_VELOCITY = 800;
function readCoachPermanentlyDismissed() {
	try {
		return (
			typeof localStorage !== "undefined" &&
			localStorage.getItem(SWIPE_COACH_KEY) === "1"
		);
	} catch {
		return true;
	}
}

const COACH_LABEL_LEAD_MS = 200;
const COACH_EXIT_MS = 920;
const COACH_PAUSE_MS = 1300;
const COACH_EXIT_DURATION = 0.92;
const COACH_PROMOTE_DURATION = 0.52;
const COACH_LABEL_DURATION = 0.58;
const COACH_SLOT_COUNT = 3;
const COACH_EASE = [0.22, 0.03, 0.26, 1];
const COACH_EASE_OUT = [0.16, 1, 0.3, 1];

/** Имитация стека карточек без фото — те же жесты и «опускание», что в ленте. */
function SwipeCoachStackDemo({ reduceMotion }) {
	const [order, setOrder] = useState(() =>
		Array.from({ length: COACH_SLOT_COUNT }, (_, i) => i),
	);
	const [labelDir, setLabelDir] = useState(null);
	const [exitDir, setExitDir] = useState(null);

	useEffect(() => {
		if (reduceMotion) return;

		let cancelled = false;
		let nextDir = "right";

		const wait = (ms) =>
			new Promise((resolve) => {
				window.setTimeout(resolve, ms);
			});

		const run = async () => {
			while (!cancelled) {
				const dir = nextDir;
				nextDir = dir === "right" ? "left" : "right";

				setLabelDir(dir);
				await wait(COACH_LABEL_LEAD_MS);
				if (cancelled) break;

				setExitDir(dir);
				await wait(COACH_EXIT_MS);
				if (cancelled) break;

				setOrder((prev) => [...prev.slice(1), prev[0]]);
				setExitDir(null);
				setLabelDir(null);
				await wait(COACH_PAUSE_MS);
			}
		};

		void run();
		return () => {
			cancelled = true;
		};
	}, [reduceMotion]);

	return (
		<div
			className={`swipe-coach-stack-demo${reduceMotion ? " swipe-coach-stack-demo--static" : ""}`}
			aria-hidden
		>
			<div className="swipe-coach-stack">
				<div className="swipe-coach-side-label-wrap swipe-coach-side-label-wrap--skip">
					<motion.span
						className="swipe-coach-side-label swipe-coach-side-label--skip"
						initial={false}
						animate={{
							opacity: labelDir === "left" ? 1 : 0,
						}}
						transition={{
							duration: COACH_LABEL_DURATION,
							ease: COACH_EASE_OUT,
						}}
					>
						Дальше
					</motion.span>
				</div>
				<div className="swipe-coach-side-label-wrap swipe-coach-side-label-wrap--like">
					<motion.span
						className="swipe-coach-side-label swipe-coach-side-label--like"
						initial={false}
						animate={{
							opacity: labelDir === "right" ? 1 : 0,
						}}
						transition={{
							duration: COACH_LABEL_DURATION,
							ease: COACH_EASE_OUT,
						}}
					>
						Нравится
					</motion.span>
				</div>
				{[...order].reverse().map((slotIdx) => {
					const stackPos = order.indexOf(slotIdx);
					const isTop = stackPos === 0;
					const exiting = isTop && exitDir;

					return (
						<motion.div
							key={`coach-slot-${slotIdx}`}
							className={`swipe-coach-card${isTop ? "" : " swipe-coach-card--back"}`}
							initial={false}
							animate={{
								y: stackPos * -10,
								x: exiting
									? exitDir === "right"
										? "120%"
										: "-120%"
									: 0,
								rotate: exiting
									? exitDir === "right"
										? 14
										: -14
									: 0,
								opacity: exiting ? 0.72 : 1,
								zIndex: 10 - stackPos,
							}}
							transition={{
								y: {
									duration: COACH_PROMOTE_DURATION,
									ease: COACH_EASE,
								},
								x: {
									duration: exiting ? COACH_EXIT_DURATION : 0,
									ease: COACH_EASE,
								},
								rotate: {
									duration: exiting ? COACH_EXIT_DURATION : 0,
									ease: COACH_EASE,
								},
								opacity: {
									duration: exiting ? COACH_EXIT_DURATION : 0.28,
									ease: COACH_EASE_OUT,
								},
							}}
						>
							{exiting && exitDir === "right" ? (
								<div
									className="swipe-card-tint swipe-card-tint--like"
									style={{ opacity: 0.4 }}
									aria-hidden
								/>
							) : null}
						</motion.div>
					);
				})}
			</div>
		</div>
	);
}

/** URL → Promise; Set готовых — общий кеш для preload и CardImage. */
const imageReadyUrls = new Set();
const imageLoadPromises = new Map();

function evictImageUrl(url) {
	if (!url) return;
	imageReadyUrls.delete(url);
	imageLoadPromises.delete(url);
}

function preloadImageUrl(url) {
	if (!url || typeof url !== "string") return Promise.resolve(false);
	if (imageReadyUrls.has(url)) return Promise.resolve(true);
	const pending = imageLoadPromises.get(url);
	if (pending) return pending;

	const promise = new Promise((resolve) => {
		const img = new Image();
		img.decoding = "async";
		const finish = (ok) => {
			if (ok) imageReadyUrls.add(url);
			else evictImageUrl(url);
			imageLoadPromises.delete(url);
			resolve(ok);
		};
		img.onload = () => finish(true);
		img.onerror = () => finish(false);
		img.src = url;
	});
	imageLoadPromises.set(url, promise);
	return promise;
}

/** Ограниченная параллельность — не забиваем канал, порядок в массиве сохраняем. */
async function preloadManyOrdered(urls, maxConcurrent = 3) {
	const queue = [...new Set(urls.filter((u) => typeof u === "string" && u.trim()))];
	if (!queue.length) return;

	let cursor = 0;
	async function worker() {
		while (cursor < queue.length) {
			const url = queue[cursor];
			cursor += 1;
			await preloadImageUrl(url);
		}
	}
	const workers = Math.min(maxConcurrent, queue.length);
	await Promise.all(Array.from({ length: workers }, () => worker()));
}

let backgroundPreloadGen = 0;

/** Сначала окно от currentIndex, остальное — фоном по одному. */
function scheduleFeedPreload(urls, currentIndex = 0) {
	const clean = urls.filter((u) => typeof u === "string" && u.trim());
	if (!clean.length) return;

	const gen = ++backgroundPreloadGen;
	const windowEnd = Math.min(clean.length, currentIndex + 8);
	const ahead = clean.slice(currentIndex, windowEnd);
	const tail = clean.slice(windowEnd);

	void (async () => {
		await preloadManyOrdered(ahead, 4);
		for (const url of tail) {
			if (gen !== backgroundPreloadGen) return;
			await preloadImageUrl(url);
		}
	})();
}

/** Только валидные для карточки; дубликаты id убираем (порядок первого вхождения). */
function normalizeFeedPhotos(raw) {
	const list = Array.isArray(raw) ? raw : [];
	const byId = new Map();
	for (const p of list) {
		const url = p?.url;
		if (typeof url !== "string" || !url.trim()) continue;
		if (!p?.id) continue;
		if (!byId.has(p.id)) byId.set(p.id, p);
	}
	return Array.from(byId.values());
}

/** Пустая выдача: исчерпан каталог vs реально нет фото в коллекции. */
function classifyEmptyFeed(meta) {
	if (!meta || typeof meta !== "object") return "exhausted";
	if (Number(meta.catalog_exhausted) > 0) return "exhausted";
	const total = Number(meta.total_active_for_gender);
	const seen = Number(meta.seen_in_this_collection);
	const candidates = Number(meta.candidates);
	if (total > 0 && seen >= total) return "exhausted";
	if (total > 0 && candidates === 0 && seen > 0) return "exhausted";
	if (total === 0) return "no_catalog";
	if (Number.isFinite(total) && total > 0) return "exhausted";
	return "exhausted";
}

function CardImage({ url, fetchPriority, photoId, eager, onBroken }) {
	const [ready, setReady] = useState(() => imageReadyUrls.has(url));
	const [broken, setBroken] = useState(false);
	const brokenReportedRef = useRef(false);
	const imgRef = useRef(null);

	const reportBroken = useCallback(() => {
		if (brokenReportedRef.current) return;
		brokenReportedRef.current = true;
		evictImageUrl(url);
		setBroken(true);
		setReady(false);
		onBroken?.();
	}, [url, onBroken]);

	useLayoutEffect(() => {
		brokenReportedRef.current = false;
		setBroken(false);
		if (imageReadyUrls.has(url)) {
			setReady(true);
			return;
		}
		const el = imgRef.current;
		if (el?.complete && el.naturalWidth > 0) {
			imageReadyUrls.add(url);
			setReady(true);
			return;
		}

		let cancelled = false;
		void preloadImageUrl(url).then((ok) => {
			if (cancelled) return;
			if (ok) setReady(true);
			else reportBroken();
		});
		return () => {
			cancelled = true;
		};
	}, [url, photoId, reportBroken]);

	if (broken) {
		return (
			<div className="swipe-card-media swipe-card-media--broken" role="status">
				<span className="swipe-card-broken-label">Фото недоступно</span>
			</div>
		);
	}

	return (
		<div className="swipe-card-media">
			<div className={`swipe-image-skeleton ${ready ? "swipe-image-skeleton--hide" : ""}`} aria-hidden />
			<img
				ref={imgRef}
				src={url}
				alt=""
				className={`swipe-image ${ready ? "swipe-image--ready" : ""}`}
				draggable={false}
				decoding="async"
				loading={eager ? "eager" : "lazy"}
				fetchPriority={fetchPriority}
				onLoad={() => {
					imageReadyUrls.add(url);
					setReady(true);
				}}
				onError={reportBroken}
			/>
		</div>
	);
}

/** Штампы: «Нравится» (лайк), «Дальше» (пропуск жестом), «Не моё» (кнопка 👎). */
function SwipeStamps({ overlay, likeOpacity, skipOpacity }) {
	if (overlay === "like") {
		return (
			<div className="swipe-stamp swipe-stamp--like swipe-stamp--committed" aria-hidden>
				Нравится
			</div>
		);
	}
	if (overlay === "skip") {
		return (
			<div className="swipe-stamp swipe-stamp--skip swipe-stamp--committed" aria-hidden>
				Дальше
			</div>
		);
	}
	if (overlay === "nope") {
		return (
			<div className="swipe-stamp swipe-stamp--nope swipe-stamp--committed" aria-hidden>
				Не моё
			</div>
		);
	}

	return (
		<>
			<motion.div
				className="swipe-stamp swipe-stamp--like"
				style={{ opacity: likeOpacity, scale: likeOpacity }}
				aria-hidden
			>
				Нравится
			</motion.div>
			<motion.div
				className="swipe-stamp swipe-stamp--skip"
				style={{ opacity: skipOpacity, scale: skipOpacity }}
				aria-hidden
			>
				Дальше
			</motion.div>
		</>
	);
}

export default function Swipe() {
	const { gender } = useParams();
	const navigate = useNavigate();
	const reduceMotion = useReducedMotion();
	const { isAuthenticated, profile } = useAuth();

	const [coachDismissed, setCoachDismissed] = useState(
		readCoachPermanentlyDismissed,
	);
	const [coachDontRemind, setCoachDontRemind] = useState(false);

	const [photos, setPhotos] = useState([]);
	const [loadError, setLoadError] = useState(null);
	const [loading, setLoading] = useState(true);

	const [phase, setPhase] = useState("swipe");
	const [feedEmptyKind, setFeedEmptyKind] = useState(null);
	const [replayCatalog, setReplayCatalog] = useState(false);
	const [chunkSize, setChunkSize] = useState(10);
	const [feedMeta, setFeedMeta] = useState(null);
	const [checkpoint, setCheckpoint] = useState(null);
	const [sessionLikes, setSessionLikes] = useState(0);
	const [sessionTotal, setSessionTotal] = useState(0);
	const [chunkLikes, setChunkLikes] = useState(0);
	const [chunkTotal, setChunkTotal] = useState(0);
	const [index, setIndex] = useState(0);
	const [isExiting, setIsExiting] = useState(false);
	const [likedPhotoIds, setLikedPhotoIds] = useState([]);
	const [overlay, setOverlay] = useState(null);
	const [showInfo, setShowInfo] = useState(false);

	const swipeHandledRef = useRef(false);
	const cardShownAtRef = useRef(Date.now());

	const dragX = useMotionValue(0);
	const dragRotate = useTransform(dragX, [-280, 0, 280], [-16, 0, 16]);
	const likeTintOpacity = useTransform(dragX, [0, DRAG_FEEDBACK_PX, 140], [0, 0.35, 0.55]);
	const likeStampOpacity = useTransform(dragX, [0, DRAG_FEEDBACK_PX, 130], [0, 0.5, 1]);
	const skipStampOpacity = useTransform(
		dragX,
		[-130, -DRAG_FEEDBACK_PX, 0],
		[1, 0.5, 0],
	);

	const goThankYou = useCallback(
		(likes, total, photoIds) => {
			navigate("/thank-you", {
				state: {
					likes,
					total,
					likedPhotoIds: photoIds,
				},
			});
		},
		[navigate],
	);

	const loadChunk = useCallback(
		async (limit, { includeSeen = false } = {}) => {
			const data = await loadFeed(gender, {
				limit,
				includeSeen: includeSeen || replayCatalog,
			});
			const list = normalizeFeedPhotos(data.photos ?? []);
			setFeedMeta(data.meta ?? null);
			setPhotos(list);
			setIndex(0);
			setChunkLikes(0);
			setChunkTotal(0);
			setOverlay(null);
			setShowInfo(false);
			setIsExiting(false);
			swipeHandledRef.current = false;
			dragX.set(0);
			const urls = list.map((p) => p.url);
			await preloadManyOrdered(urls.slice(0, 4), 3);
			scheduleFeedPreload(urls, 0);
			return { list, meta: data.meta ?? null };
		},
		[gender, dragX, replayCatalog],
	);

	const openFeedEmpty = useCallback((kind, meta) => {
		setFeedEmptyKind(kind);
		setFeedMeta(meta ?? null);
		setPhase("feed_empty");
		setPhotos([]);
	}, []);

	useEffect(() => {
		let cancelled = false;
		backgroundPreloadGen += 1;
		setLoading(true);
		setLoadError(null);
		setPhotos([]);
		setPhase("swipe");
		setFeedEmptyKind(null);
		setReplayCatalog(false);
		setCheckpoint(null);
		setSessionLikes(0);
		setSessionTotal(0);
		setLikedPhotoIds([]);
		setOverlay(null);
		setShowInfo(false);
		setIsExiting(false);
		swipeHandledRef.current = false;
		dragX.set(0);

		(async () => {
			try {
				const settings = await fetchFeedPublicSettings();
				const limit = Math.max(1, Number(settings?.swipe_chunk_size) || 10);
				if (!cancelled) setChunkSize(limit);
				const { list, meta } = await loadChunk(limit);
				if (cancelled) return;
				if (!list.length) {
					openFeedEmpty(classifyEmptyFeed(meta), meta);
				}
			} catch (e) {
				if (!cancelled) setLoadError(e.message || String(e));
			} finally {
				if (!cancelled) setLoading(false);
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [gender, dragX, goThankYou, loadChunk, openFeedEmpty]);

	const currentPhoto = photos[index];

	useEffect(() => {
		cardShownAtRef.current = Date.now();
		dragX.set(0);
	}, [index, dragX]);

	useEffect(() => {
		if (!photos.length) return;
		const urls = photos.map((p) => p.url);
		scheduleFeedPreload(urls, index);
	}, [index, photos]);

	const photoInfo = useMemo(() => {
		if (!currentPhoto) return null;
		const tags = Array.isArray(currentPhoto.tags) ? currentPhoto.tags : [];
		const brandFromPhoto =
			typeof currentPhoto.brand === "string" && currentPhoto.brand.trim()
				? currentPhoto.brand.trim()
				: null;
		const brandTag =
			tags.find((t) => t.type === "brand" && t.name) ||
			tags.find((t) => t.type === "label" && t.name);
		const productTypeTag =
			tags.find((t) => t.type === "product_type" && t.name) ||
			tags.find((t) => t.type === "garment_type" && t.name);
		return {
			brand: brandFromPhoto || brandTag?.name || "не указан",
			productType: productTypeTag?.name || "не указан",
		};
	}, [currentPhoto]);

	const removeBrokenPhoto = useCallback((photoId) => {
		setPhotos((prev) => {
			const removeIdx = prev.findIndex((p) => p.id === photoId);
			if (removeIdx < 0) return prev;
			const removed = prev[removeIdx];
			if (removed?.url) evictImageUrl(removed.url);
			const next = prev.filter((p) => p.id !== photoId);
			setIndex((i) => {
				if (removeIdx < i) return Math.max(0, i - 1);
				if (removeIdx === i && i >= next.length) {
					return Math.max(0, next.length - 1);
				}
				return i;
			});
			return next;
		});
	}, []);

	const sendAction = useCallback(
		async (action) => {
			if (!currentPhoto) return;
			const viewTimeMs = Math.round(Date.now() - cardShownAtRef.current);
			try {
				await postInteraction({
					photoId: currentPhoto.id,
					action,
					viewTimeMs,
				});
			} catch (e) {
				console.error(e);
			}
		},
		[currentPhoto],
	);

	const finishChunk = useCallback(
		(nextChunkLikes, nextChunkTotal, nextSessionLikes, nextSessionTotal, nextLikedIds) => {
			const hasMore = Number(feedMeta?.has_more_unseen) > 0;
			setCheckpoint({
				chunk: { likes: nextChunkLikes, total: nextChunkTotal },
				session: { likes: nextSessionLikes, total: nextSessionTotal },
				hasMore,
				tasteVectorReady: Number(feedMeta?.taste_vector_ready) > 0,
				likedPhotoIds: nextLikedIds,
			});
			setPhase("checkpoint");
			swipeHandledRef.current = false;
		},
		[feedMeta],
	);

	const handleAction = useCallback(
		(action) => {
			if (swipeHandledRef.current) return;
			swipeHandledRef.current = true;

			void sendAction(action);

			const nextChunkTotal = chunkTotal + 1;
			const nextSessionTotal = sessionTotal + 1;
			const nextChunkLikes = action === "like" ? chunkLikes + 1 : chunkLikes;
			const nextSessionLikes = action === "like" ? sessionLikes + 1 : sessionLikes;
			const nextLikedPhotoIds =
				action === "like"
					? [...likedPhotoIds, currentPhoto.id]
					: likedPhotoIds;

			setChunkTotal(nextChunkTotal);
			setSessionTotal(nextSessionTotal);
			setChunkLikes(nextChunkLikes);
			setSessionLikes(nextSessionLikes);
			setLikedPhotoIds(nextLikedPhotoIds);

			const nextIndex = index + 1;
			if (nextIndex >= photos.length) {
				finishChunk(
					nextChunkLikes,
					nextChunkTotal,
					nextSessionLikes,
					nextSessionTotal,
					nextLikedPhotoIds,
				);
				return;
			}

			setIndex(nextIndex);
			setOverlay(null);
			setShowInfo(false);
			setIsExiting(false);
			dragX.set(0);

			setTimeout(() => {
				swipeHandledRef.current = false;
			}, 0);
		},
		[
			sendAction,
			chunkLikes,
			chunkTotal,
			sessionLikes,
			sessionTotal,
			likedPhotoIds,
			currentPhoto,
			index,
			photos.length,
			finishChunk,
			dragX,
		],
	);

	const onCheckpointContinue = useCallback(async () => {
		if (!checkpoint) return;
		if (!checkpoint.hasMore) {
			goThankYou(
				checkpoint.session.likes,
				checkpoint.session.total,
				checkpoint.likedPhotoIds,
			);
			return;
		}
		setPhase("swipe");
		setCheckpoint(null);
		setLoading(true);
		try {
			const { list, meta } = await loadChunk(chunkSize);
			if (!list.length) {
				openFeedEmpty(classifyEmptyFeed(meta), meta);
			}
		} catch (e) {
			setLoadError(e.message || String(e));
		} finally {
			setLoading(false);
		}
	}, [checkpoint, chunkSize, goThankYou, loadChunk, openFeedEmpty]);

	const onReplayCatalog = useCallback(async () => {
		setReplayCatalog(true);
		setFeedEmptyKind(null);
		setPhase("swipe");
		setLoading(true);
		setLoadError(null);
		try {
			const { list, meta } = await loadChunk(chunkSize, { includeSeen: true });
			if (!list.length) {
				const emptyKind = classifyEmptyFeed(meta) || "no_catalog";
				openFeedEmpty(emptyKind, meta);
			}
		} catch (e) {
			setLoadError(e.message || String(e));
		} finally {
			setLoading(false);
		}
	}, [chunkSize, loadChunk, openFeedEmpty]);

	const onCheckpointThankYou = useCallback(() => {
		if (!checkpoint) return;
		goThankYou(
			checkpoint.session.likes,
			checkpoint.session.total,
			checkpoint.likedPhotoIds,
		);
	}, [checkpoint, goThankYou]);

	const commitExit = useCallback(
		(action, overlayKind, exitX) => {
			if (isExiting) return;
			swipeHandledRef.current = false;
			setOverlay(overlayKind);
			setIsExiting(true);

			const duration = reduceMotion ? 0.15 : 0.38;
			void animate(dragX, exitX, { duration }).then(() => {
				handleAction(action);
			});
		},
		[isExiting, dragX, handleAction, reduceMotion],
	);

	const handleDragEnd = (_e, info) => {
		if (isExiting) return;
		const offset = info.offset.x;
		const velocity = info.velocity.x;
		if (
			Math.abs(offset) > COMMIT_OFFSET_PX ||
			Math.abs(velocity) > COMMIT_VELOCITY
		) {
			const dir = offset !== 0 ? offset : velocity;
			if (dir > 0) {
				commitExit("like", "like", 520);
			} else {
				commitExit("skip", "skip", -520);
			}
		} else {
			setOverlay(null);
			void animate(dragX, 0, {
				type: "spring",
				stiffness: 520,
				damping: 36,
			});
		}
	};

	const handleButtonAction = (action) => {
		const overlayKind = action === "like" ? "like" : "nope";
		const exitX = action === "like" ? 520 : -520;
		commitExit(action, overlayKind, exitX);
	};

	const stack = useMemo(
		() => photos.slice(index, index + 3).filter((p) => p?.url),
		[photos, index],
	);

	if (loading) {
		return <div className="swipe-no-images">Загрузка…</div>;
	}

	if (phase === "feed_empty" && feedEmptyKind) {
		const totalInCatalog = Math.round(Number(feedMeta?.total_active_for_gender) || 0);
		return (
			<SwipeFeedEmpty
				kind={feedEmptyKind}
				gender={gender}
				isAuthenticated={isAuthenticated}
				displayName={profile?.display_name}
				totalInCatalog={totalInCatalog || undefined}
				onReplay={onReplayCatalog}
				onHome={() => navigate("/")}
				onGuestProgram={() => goThankYou(0, 0, [])}
			/>
		);
	}

	if (phase === "checkpoint" && checkpoint) {
		return (
			<SwipeCheckpoint
				isAuthenticated={isAuthenticated}
				displayName={profile?.display_name}
				chunk={checkpoint.chunk}
				session={checkpoint.session}
				hasMore={checkpoint.hasMore}
				tasteVectorReady={checkpoint.tasteVectorReady}
				onContinue={onCheckpointContinue}
				onGoThankYou={onCheckpointThankYou}
				onHome={() => navigate("/")}
			/>
		);
	}

	if (loadError) {
		return (
			<div className="swipe-no-images">
				Не удалось загрузить ленту. Запустите API (порт 8000) и Postgres.
				<pre style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{loadError}</pre>
			</div>
		);
	}

	if (!photos.length) {
		const fallbackKind = classifyEmptyFeed(feedMeta) || "no_catalog";
		return (
			<SwipeFeedEmpty
				kind={fallbackKind}
				gender={gender}
				isAuthenticated={isAuthenticated}
				displayName={profile?.display_name}
				totalInCatalog={
					Math.round(Number(feedMeta?.total_active_for_gender) || 0) || undefined
				}
				onReplay={onReplayCatalog}
				onHome={() => navigate("/")}
				onGuestProgram={() => goThankYou(0, 0, [])}
			/>
		);
	}

	const showCoach = !coachDismissed && photos.length > 0;
	const showPushPrompt =
		coachDismissed && photos.length > 0 && index >= 3 && index < photos.length;

	function dismissCoach() {
		if (coachDontRemind) {
			try {
				localStorage.setItem(SWIPE_COACH_KEY, "1");
			} catch {
				/* ignore */
			}
		}
		setCoachDismissed(true);
	}

	return (
		<div className="swipe-container">
			{showCoach && (
				<div
					className="swipe-coach"
					role="dialog"
					aria-modal="true"
					aria-labelledby="swipe-coach-title"
				>
					<div className="swipe-coach-scrim" aria-hidden />
					<div className="swipe-coach-inner">
						<h2 id="swipe-coach-title" className="swipe-coach-title">
							Листайте образы
						</h2>
						<p className="swipe-coach-lead">
							Влево — дальше, без оценки.
							<br />
							Вправо — нравится. Кнопка 👎 — явно «не моё».
						</p>
						<div className="swipe-coach-demo">
							<SwipeCoachStackDemo reduceMotion={reduceMotion} />
						</div>
						<div className="swipe-coach-actions">
							<label className="swipe-coach-dont-remind">
								<input
									type="checkbox"
									checked={coachDontRemind}
									onChange={(e) => setCoachDontRemind(e.target.checked)}
								/>
								<span>Больше не напоминать</span>
							</label>
							<button
								type="button"
								className="swipe-coach-cta"
								onClick={dismissCoach}
							>
								Понятно
							</button>
						</div>
					</div>
				</div>
			)}
			<div className="swipe-stack-wrap">
				<AnimatePresence>
					{stack.map((photo, i) => {
						const isTop = i === 0;

						return (
							<motion.div
								key={photo.id}
								className="swipe-card"
								drag={isTop && !isExiting ? "x" : false}
								dragConstraints={{ left: 0, right: 0 }}
								dragElastic={0.75}
								dragMomentum={false}
								onDragEnd={isTop ? handleDragEnd : undefined}
								style={
									isTop
										? { x: dragX, rotate: dragRotate, zIndex: 10 - i }
										: { zIndex: 10 - i }
								}
								initial={
									i === 0
										? { scale: 0.96, y: 0, opacity: 0 }
										: { scale: 1, y: i * -10, opacity: 1 }
								}
								animate={
									isTop && isExiting
										? { opacity: 0.6 }
										: { scale: 1, y: i * -10, opacity: 1 }
								}
								exit={{ opacity: 0 }}
								transition={{ duration: i === 0 ? 0.35 : 0.2 }}
							>
								{isTop && (
									<motion.div
										className="swipe-card-tint swipe-card-tint--like"
										style={{ opacity: likeTintOpacity }}
										aria-hidden
									/>
								)}
								<CardImage
									key={photo.id}
									url={photo.url}
									photoId={photo.id}
									fetchPriority={isTop ? "high" : i === 1 ? "auto" : "low"}
									eager={i <= 1}
									onBroken={() => removeBrokenPhoto(photo.id)}
								/>
								{typeof photo.badge_label === "string" &&
								photo.badge_label.trim() ? (
									<span className="swipe-card-badge" aria-label={photo.badge_label.trim()}>
										{photo.badge_label.trim()}
									</span>
								) : null}
								{isTop && (
									<SwipeStamps
										overlay={isExiting ? overlay : null}
										likeOpacity={isExiting ? undefined : likeStampOpacity}
										skipOpacity={isExiting ? undefined : skipStampOpacity}
									/>
								)}
								{isTop && showInfo && photoInfo ? (
									<div className="swipe-photo-info" role="status" aria-live="polite">
										<p>Бренд: {photoInfo.brand}</p>
										<p>Тип изделия: {photoInfo.productType}</p>
									</div>
								) : null}
							</motion.div>
						);
					})}
				</AnimatePresence>
			</div>

			<PushNotifyPrompt visible={showPushPrompt} gender={gender} />

			{index < photos.length && !showCoach && (
				<div className="swipe-buttons">
					<button
						type="button"
						onClick={() => handleButtonAction("dislike")}
						className="swipe-btn swipe-btn--left nope"
						aria-label="Не моё"
					>
						👎
					</button>
					<button
						type="button"
						className="swipe-btn-info"
						onClick={() => setShowInfo((v) => !v)}
						aria-label="Показать описание фото"
					>
						!
					</button>
					<button
						type="button"
						onClick={() => handleButtonAction("like")}
						className="swipe-btn swipe-btn--right like"
						aria-label="Нравится"
					>
						👍
					</button>
				</div>
			)}
		</div>
	);
}
