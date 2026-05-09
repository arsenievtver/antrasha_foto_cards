import {
	useState,
	useMemo,
	useRef,
	useEffect,
	useLayoutEffect,
	useCallback,
} from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { loadFeed, postInteraction } from "../api/client";
import { useAuth } from "../context/AuthContext";
import swipeHandAsset from "../assets/swipe.svg";
import "./Swipe.css";

const SWIPE_GUEST_COACH_KEY = "swipe_guest_coach_dismissed";

function readGuestCoachDismissed() {
	try {
		return (
			typeof localStorage !== "undefined" &&
			localStorage.getItem(SWIPE_GUEST_COACH_KEY) === "1"
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

	// Картинка из HTTP-кэша часто уже complete до срабатывания onLoad — иначе шиммер не исчезает никогда.
	// Важно: не использовать отдельный useEffect(() => setReady(false), [url]) — он шёл ПОСЛЕ этого и сбрасывал ready обратно в false.
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

export default function Swipe() {
	const { gender } = useParams();
	const navigate = useNavigate();
	const { isAuthenticated, loading: authLoading } = useAuth();
	const reduceMotion = useReducedMotion();

	const [coachDismissed, setCoachDismissed] = useState(readGuestCoachDismissed);

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

	useEffect(() => {
		let cancelled = false;
		setLoading(true);
		setLoadError(null);
		// Смена коллекции (male/female) не размонтирует страницу — иначе index остаётся от прошлой колоды
		// и slice(index) подставляет «хвост одной / начало другой» ↔ симптом «5 карт не те».
		setPhotos([]);
		setIndex(0);
		setLikes(0);
		setLikedPhotoIds([]);
		setOverlay(null);
		setShowInfo(false);
		setIsExiting(false);
		swipeHandledRef.current = false;

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
	}, [gender]);

	useEffect(() => {
		cardShownAtRef.current = Date.now();
	}, [index]);

	const currentPhoto = photos[index];
	const photoInfo = useMemo(() => {
		if (!currentPhoto) return null;
		const tags = Array.isArray(currentPhoto.tags) ? currentPhoto.tags : [];
		const brandTag =
			tags.find((t) => t.type === "brand" && t.name) ||
			tags.find((t) => t.type === "label" && t.name);
		const productTypeTag =
			tags.find((t) => t.type === "product_type" && t.name) ||
			tags.find((t) => t.type === "garment_type" && t.name);
		return {
			brand: brandTag?.name || "не указан",
			productType: productTypeTag?.name || "не указан",
		};
	}, [currentPhoto]);

	const sendSwipe = useCallback(
		async (direction) => {
			if (!currentPhoto) return;
			const viewTimeMs = Math.round(Date.now() - cardShownAtRef.current);
			const action = direction === "right" ? "like" : "dislike";
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

	const handleSwipe = (direction) => {
		if (swipeHandledRef.current) return;
		swipeHandledRef.current = true;

		void sendSwipe(direction);

		const newLikes = direction === "right" ? likes + 1 : likes;
		if (direction === "right") setLikes(newLikes);
		const nextLikedPhotoIds =
			direction === "right"
				? [...likedPhotoIds, currentPhoto.id]
				: likedPhotoIds;
		if (direction === "right") setLikedPhotoIds(nextLikedPhotoIds);

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

		setTimeout(() => {
			swipeHandledRef.current = false;
		}, 0);
	};

	const handleDragEnd = (e, info) => {
		if (isExiting) return;
		const offset = info.offset.x;
		const velocity = info.velocity.x;
		if (Math.abs(offset) > 80 || Math.abs(velocity) > 800) {
			const dir = offset > 0 ? "right" : "left";
			/* Как у кнопок: сначала штамп, улет карточки, затем handleSwipe — иначе setOverlay(null) в handleSwipe сразу снимает надпись */
			swipeHandledRef.current = false;
			setOverlay(dir === "right" ? "like" : "nope");
			setIsExiting(true);
			setTimeout(() => {
				handleSwipe(dir);
			}, 650);
		} else {
			setOverlay(null);
		}
	};

	const handleButtonSwipe = (dir) => {
		if (isExiting) return;
		swipeHandledRef.current = false;
		setOverlay(dir === "right" ? "like" : "nope");
		setIsExiting(true);

		setTimeout(() => {
			handleSwipe(dir);
		}, 650);
	};

	const handleDrag = (event, info) => {
		const threshold = 120;
		if (info.offset.x > threshold) setOverlay("like");
		else if (info.offset.x < -threshold) setOverlay("nope");
		else setOverlay(null);
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

	const showGuestCoach =
		!authLoading &&
		!isAuthenticated &&
		!coachDismissed &&
		photos.length > 0;

	function dismissGuestCoach() {
		try {
			localStorage.setItem(SWIPE_GUEST_COACH_KEY, "1");
		} catch {
			/* ignore */
		}
		setCoachDismissed(true);
	}

	return (
		<div className="swipe-container">
			{showGuestCoach && (
				<div
					className="swipe-coach"
					role="dialog"
					aria-modal="true"
					aria-labelledby="swipe-coach-title"
				>
					<div className="swipe-coach-scrim" aria-hidden />
					<div className="swipe-coach-inner">
						<h2 id="swipe-coach-title" className="swipe-coach-title">
							Смахните карточку
						</h2>
						<p className="swipe-coach-lead">
							Влево — не нравится, вправо — нравится.
							<br />
							Тоже самое можно сделать кнопками внизу.
						</p>
						<div
							className={`swipe-coach-demo${reduceMotion ? " swipe-coach-demo--static" : ""}`}
						>
							<span className="swipe-coach-side swipe-coach-side--nope">
								Нет
							</span>
							<div className="swipe-coach-track">
								<div className="swipe-coach-track-line" aria-hidden />
								<SwipeCoachHandOutline reduceMotion={reduceMotion} />
							</div>
							<span className="swipe-coach-side swipe-coach-side--like">
								Да
							</span>
						</div>
						<button
							type="button"
							className="swipe-coach-cta"
							onClick={dismissGuestCoach}
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
						const isLeaving = isTop && isExiting;

						return (
							<motion.div
								key={photo.id}
								className="swipe-card"
								drag={isTop && !isExiting ? "x" : false}
								dragConstraints={{ left: 0, right: 0 }}
								dragElastic={0.8}
								dragMomentum={true}
								onDrag={isTop ? handleDrag : undefined}
								onDragEnd={isTop ? handleDragEnd : undefined}
								/* Только верхняя карта появляется с fade; нижние сразу opacity:1 — иначе стопка выглядела как «пустые дыры» */
								initial={
									i === 0
										? { scale: 0.96, y: 0, opacity: 0 }
										: { scale: 1, y: i * -10, opacity: 1 }
								}
								animate={
									isLeaving
										? {
												x: overlay === "like" ? 1000 : -1000,
												opacity: 0,
											}
										: { scale: 1, y: i * -10, opacity: 1 }
								}
								exit={{ opacity: 0 }}
								style={{ zIndex: 10 - i }}
								transition={{ duration: i === 0 ? 0.35 : 0.2 }}
							>
								<CardImage
									key={photo.id}
									url={photo.url}
									photoId={photo.id}
									fetchPriority={isTop ? "high" : "low"}
								/>
								{isTop && overlay && (
									<div className={`overlay ${overlay}`}>
										{overlay === "like" ? "Нравится" : "Пропуск"}
									</div>
								)}
								{isTop && showInfo && photoInfo ? (
									<div className="swipe-photo-info" role="status" aria-live="polite">
										<p>
											Бренд: <strong>{photoInfo.brand}</strong>
										</p>
										<p>
											Тип изделия: <strong>{photoInfo.productType}</strong>
										</p>
									</div>
								) : null}
							</motion.div>
						);
					})}
				</AnimatePresence>
			</div>

			{index < photos.length && (
				<div className="swipe-buttons">
					<button
						type="button"
						onClick={() => handleButtonSwipe("left")}
						className="swipe-btn swipe-btn--left nope"
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
						onClick={() => handleButtonSwipe("right")}
						className="swipe-btn swipe-btn--right like"
					>
						👍
					</button>
				</div>
			)}
		</div>
	);
}
