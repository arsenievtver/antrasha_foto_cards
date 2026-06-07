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
import { loadFeed, postInteraction } from "../api/client";
import PushNotifyPrompt from "../components/PushNotifyPrompt";
import swipeHandAsset from "../assets/swipe.svg";
import "./Swipe.css";

const SWIPE_COACH_KEY = "swipe_coach_v2_dismissed";

const DRAG_FEEDBACK_PX = 50;
const COMMIT_OFFSET_PX = 80;
const COMMIT_VELOCITY = 800;
function readCoachDismissed() {
	try {
		return (
			typeof localStorage !== "undefined" &&
			localStorage.getItem(SWIPE_COACH_KEY) === "1"
		);
	} catch {
		return true;
	}
}

/** Кисть из `src/assets/swipe.svg`. Движение в CSS (`@keyframes`) — filter и transform на разных узлах, иначе анимация часто не видна. */
function SwipeCoachHandOutline({ reduceMotion }) {
	return (
		<div className="swipe-coach-hand" aria-hidden>
			<div
				className={
					reduceMotion
						? "swipe-coach-hand-motion swipe-coach-hand-motion--off"
						: "swipe-coach-hand-motion"
				}
			>
				<div className="swipe-coach-hand-visual">
					<img
						src={swipeHandAsset}
						alt=""
						className="swipe-coach-hand-svg"
						draggable={false}
					/>
					<span className="swipe-coach-hand-glow" aria-hidden />
				</div>
			</div>
		</div>
	);
}

/** Старт загрузок строго в порядке массива (0 → 1 → …); браузер может закончить в другом порядке, но очередь одна). */
function preloadImageUrls(urls) {
	for (const url of urls) {
		if (!url) continue;
		const img = new Image();
		img.decoding = "async";
		img.src = url;
	}
}

const PRELOAD_SYNC_HEAD = 20;
const PRELOAD_RAF_BATCH = 8;

/** Одна цепочка: синхронно первые N URL, остальное — только через rAF волнами (без второго useEffect и без microtask — не пересекается с предзагрузкой при смене index). */
function schedulePreloadInOrder(urls) {
	const clean = urls.filter((u) => typeof u === "string" && u.trim().length > 0);
	if (!clean.length) return;
	preloadImageUrls(clean.slice(0, PRELOAD_SYNC_HEAD));
	const rest = clean.slice(PRELOAD_SYNC_HEAD);
	if (!rest.length) return;
	let offset = 0;
	const step = () => {
		preloadImageUrls(rest.slice(offset, offset + PRELOAD_RAF_BATCH));
		offset += PRELOAD_RAF_BATCH;
		if (offset < rest.length) requestAnimationFrame(step);
	};
	requestAnimationFrame(step);
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

function CardImage({ url, fetchPriority, photoId }) {
	const [ready, setReady] = useState(false);
	const imgRef = useRef(null);

	useLayoutEffect(() => {
		const el = imgRef.current;
		if (el?.complete && el.naturalWidth > 0) {
			setReady(true);
		}
	}, [url, photoId]);

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
				fetchPriority={fetchPriority}
				onLoad={() => setReady(true)}
				onError={() => setReady(true)}
			/>
		</div>
	);
}

/** Штампы: «Мой стиль» (лайк), «Дальше» (пропуск жестом), «Не моё» (кнопка 👎). */
function SwipeStamps({ overlay, likeOpacity, skipOpacity }) {
	if (overlay === "like") {
		return (
			<div className="swipe-stamp swipe-stamp--like swipe-stamp--committed" aria-hidden>
				Мой стиль
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
				Мой стиль
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

	const [coachDismissed, setCoachDismissed] = useState(readCoachDismissed);

	const [photos, setPhotos] = useState([]);
	const [loadError, setLoadError] = useState(null);
	const [loading, setLoading] = useState(true);

	const [index, setIndex] = useState(0);
	const [isExiting, setIsExiting] = useState(false);
	const [likes, setLikes] = useState(0);
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

	useEffect(() => {
		let cancelled = false;
		setLoading(true);
		setLoadError(null);
		setPhotos([]);
		setIndex(0);
		setLikes(0);
		setLikedPhotoIds([]);
		setOverlay(null);
		setShowInfo(false);
		setIsExiting(false);
		swipeHandledRef.current = false;
		dragX.set(0);

		loadFeed(gender, { limit: 40 })
			.then((data) => {
				if (!cancelled) {
					const list = normalizeFeedPhotos(data.photos ?? []);
					const urls = list.map((p) => p.url);
					setPhotos(list);
					schedulePreloadInOrder(urls);
				}
			})
			.catch((e) => {
				if (!cancelled) setLoadError(e.message || String(e));
			})
			.finally(() => {
				if (!cancelled) setLoading(false);
			});
		return () => {
			cancelled = true;
		};
	}, [gender, dragX]);

	const currentPhoto = photos[index];

	useEffect(() => {
		cardShownAtRef.current = Date.now();
		dragX.set(0);
	}, [index, dragX]);

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

	const handleAction = useCallback(
		(action) => {
			if (swipeHandledRef.current) return;
			swipeHandledRef.current = true;

			void sendAction(action);

			const newLikes = action === "like" ? likes + 1 : likes;
			if (action === "like") setLikes(newLikes);
			const nextLikedPhotoIds =
				action === "like"
					? [...likedPhotoIds, currentPhoto.id]
					: likedPhotoIds;
			if (action === "like") setLikedPhotoIds(nextLikedPhotoIds);

			const nextIndex = index + 1;
			if (nextIndex >= photos.length) {
				navigate("/thank-you", {
					state: {
						likes: newLikes,
						total: photos.length,
						likedPhotoIds: nextLikedPhotoIds,
					},
				});
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
			likes,
			likedPhotoIds,
			currentPhoto,
			index,
			photos.length,
			navigate,
			dragX,
		],
	);

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

	if (loadError) {
		return (
			<div className="swipe-no-images">
				Не удалось загрузить ленту. Запустите API (порт 8000) и Postgres.
				<pre style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{loadError}</pre>
			</div>
		);
	}

	if (!photos.length) return <div className="swipe-no-images">Нет фото в базе</div>;

	const showCoach = !coachDismissed && photos.length > 0;
	const showPushPrompt =
		coachDismissed && photos.length > 0 && index >= 3 && index < photos.length;

	function dismissCoach() {
		try {
			localStorage.setItem(SWIPE_COACH_KEY, "1");
		} catch {
			/* ignore */
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
						<div
							className={`swipe-coach-demo${reduceMotion ? " swipe-coach-demo--static" : ""}`}
						>
							<span className="swipe-coach-side swipe-coach-side--skip">
								Дальше
							</span>
							<div className="swipe-coach-track">
								<div className="swipe-coach-track-line" aria-hidden />
								<SwipeCoachHandOutline reduceMotion={reduceMotion} />
							</div>
							<span className="swipe-coach-side swipe-coach-side--like">
								Нравится
							</span>
						</div>
						<button
							type="button"
							className="swipe-coach-cta"
							onClick={dismissCoach}
						>
							Понятно
						</button>
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
									fetchPriority={isTop ? "high" : "low"}
								/>
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

			{index < photos.length && (
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
