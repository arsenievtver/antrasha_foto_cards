import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useVideoModal } from "../../context/VideoModalContext";
import { watchSlugFromPath } from "../../utils/watchLink";
import "./HeroBanner.css";

/** Сколько слайд стоит на экране до следующей смены (без учёта fade). */
const SLIDE_DWELL_MS = 6500;
const SWIPE_THRESHOLD_PX = 52;

function padIndex(n) {
	return String(n).padStart(2, "0");
}

function isInternalPath(url) {
	return typeof url === "string" && url.startsWith("/") && !url.startsWith("//");
}

function withCacheBust(url, updatedAt) {
	if (!url) return url;
	if (!updatedAt) return url;
	const t = new Date(updatedAt).getTime();
	if (!Number.isFinite(t)) return url;
	const sep = url.includes("?") ? "&" : "?";
	return `${url}${sep}v=${t}`;
}

function slideMediaSrc(slide, desktop) {
	const mobile = withCacheBust(slide?.image_url, slide?.updated_at);
	const desk =
		withCacheBust(slide?.image_url_desktop, slide?.updated_at) || mobile;
	return desktop ? desk || mobile : mobile || desk;
}

function prefetchSlide(slide) {
	if (!slide || typeof window === "undefined") return;
	const desktop = window.matchMedia("(min-width: 768px)").matches;
	const url = slideMediaSrc(slide, desktop);
	if (!url) return;
	const img = new Image();
	img.src = url;
}

function SlideMedia({ slide }) {
	const mobileSrc = withCacheBust(slide?.image_url, slide?.updated_at);
	const desktopSrc =
		withCacheBust(slide?.image_url_desktop, slide?.updated_at) || mobileSrc;
	if (!mobileSrc && !desktopSrc) {
		return <div className="hv2-hero__blank" />;
	}
	return (
		<picture>
			{desktopSrc ? (
				<source media="(min-width: 768px)" srcSet={desktopSrc} />
			) : null}
			<img src={mobileSrc || desktopSrc} alt="" className="hv2-hero__img" />
		</picture>
	);
}

function SlideCopy({ slide, active, onOpenVideo }) {
	const title = (slide?.title || "").trim();
	const subtitle = (slide?.subtitle || "").trim();
	const body = (slide?.body || "").trim();
	const linkUrl = (slide?.link_url || "").trim();
	const linkLabel = (slide?.link_label || "").trim() || "СМОТРЕТЬ НОВИНКИ";
	const watchSlug = watchSlugFromPath(linkUrl);
	const hasImage = Boolean(slide?.image_url || slide?.image_url_desktop);
	const isPlaceholderTitle = !hasImage && title.length > 40;
	const ctaInner = (
		<span className="hv2-hero__cta-shimmer">
			<span>{linkLabel}</span>
			<span className="hv2-hero__cta-arrow" aria-hidden>
				→
			</span>
		</span>
	);

	return (
		<div
			className={active ? "hv2-hero__copy is-active" : "hv2-hero__copy"}
			aria-hidden={!active}
			{...(!active ? { inert: "" } : {})}
		>
			{title ? (
				<h1
					className={
						isPlaceholderTitle
							? "hv2-hero__title hv2-hero__title--sentence"
							: "hv2-hero__title"
					}
				>
					{title}
				</h1>
			) : null}
			{subtitle ? <p className="hv2-hero__subtitle">{subtitle}</p> : null}
			{body ? (
				<>
					<span className="hv2-hero__rule" aria-hidden />
					<p className="hv2-hero__body">{body}</p>
				</>
			) : null}
			{linkUrl ? (
				watchSlug ? (
					<button
						type="button"
						className="hv2-hero__cta"
						tabIndex={active ? 0 : -1}
						onClick={(e) => {
							e.preventDefault();
							e.stopPropagation();
							onOpenVideo?.(watchSlug);
						}}
					>
						{ctaInner}
					</button>
				) : isInternalPath(linkUrl) ? (
					<Link className="hv2-hero__cta" to={linkUrl} tabIndex={active ? 0 : -1}>
						{ctaInner}
					</Link>
				) : (
					<a
						className="hv2-hero__cta"
						href={linkUrl}
						target="_blank"
						rel="noopener noreferrer"
						tabIndex={active ? 0 : -1}
					>
						{ctaInner}
					</a>
				)
			) : null}
		</div>
	);
}

export default function HeroBanner({ items }) {
	const { openVideo, slug: videoSlug } = useVideoModal();
	const slides = items?.length ? items : [];
	const [index, setIndex] = useState(0);
	const [hidden, setHidden] = useState(false);
	const paused = hidden || Boolean(videoSlug);
	const touchRef = useRef(null);
	const remainingRef = useRef(SLIDE_DWELL_MS);
	const startedRef = useRef(0);
	const slideKey = slides.map((s) => s.id).join("|");
	const total = slides.length;
	const multi = total > 1;

	useEffect(() => {
		setIndex(0);
	}, [slideKey]);

	useEffect(() => {
		if (!multi) return;
		prefetchSlide(slides[(index + 1) % total]);
	}, [index, multi, total, slideKey]);

	useEffect(() => {
		const onVis = () => setHidden(document.hidden);
		onVis();
		document.addEventListener("visibilitychange", onVis);
		return () => document.removeEventListener("visibilitychange", onVis);
	}, []);

	useEffect(() => {
		remainingRef.current = SLIDE_DWELL_MS;
		startedRef.current = 0;
	}, [index]);

	useEffect(() => {
		if (!multi) return undefined;
		if (paused) {
			if (startedRef.current) {
				remainingRef.current = Math.max(
					0,
					remainingRef.current - (Date.now() - startedRef.current),
				);
				startedRef.current = 0;
			}
			return undefined;
		}
		startedRef.current = Date.now();
		const t = window.setTimeout(() => {
			remainingRef.current = SLIDE_DWELL_MS;
			setIndex((i) => (i + 1) % total);
		}, remainingRef.current);
		return () => window.clearTimeout(t);
	}, [index, multi, paused, total]);

	const goTo = (next) => {
		if (!multi) return;
		const n = ((next % total) + total) % total;
		setIndex(n);
	};

	const onTouchStart = (e) => {
		if (!multi) return;
		const t = e.changedTouches[0];
		touchRef.current = { x: t.clientX, y: t.clientY };
	};

	const onTouchEnd = (e) => {
		if (!multi || !touchRef.current) return;
		const t = e.changedTouches[0];
		const dx = t.clientX - touchRef.current.x;
		const dy = t.clientY - touchRef.current.y;
		touchRef.current = null;
		if (Math.abs(dx) < SWIPE_THRESHOLD_PX) return;
		if (Math.abs(dx) < Math.abs(dy) * 1.35) return;
		goTo(dx < 0 ? index + 1 : index - 1);
	};

	if (!slides.length) return null;

	const active = slides[index] || slides[0];
	const hasImage = Boolean(active?.image_url || active?.image_url_desktop);

	return (
		<section
			className={[
				"hv2-hero",
				hasImage ? "" : "hv2-hero--placeholder",
				paused ? "hv2-hero--paused" : "",
			]
				.filter(Boolean)
				.join(" ")}
			aria-label="Баннер"
			style={{ "--hv2-hero-dwell": `${SLIDE_DWELL_MS}ms` }}
			onTouchStart={onTouchStart}
			onTouchEnd={onTouchEnd}
		>
			<div className="hv2-hero__media" aria-hidden>
				{slides.map((slide, i) => (
					<div
						key={slide.id || i}
						className={
							i === index ? "hv2-hero__slide is-active" : "hv2-hero__slide"
						}
					>
						<SlideMedia slide={slide} />
					</div>
				))}
				<div className="hv2-hero__scrim" />
			</div>

			<div className="hv2-hero__content">
				<div className="hv2-hero__copy-stack">
					{slides.map((slide, i) => (
						<SlideCopy
							key={slide.id || i}
							slide={slide}
							active={i === index}
							onOpenVideo={openVideo}
						/>
					))}
				</div>

				{multi ? (
					<div className="hv2-hero__footer">
						<span className="hv2-hero__counter">
							{padIndex(index + 1)} / {padIndex(total)}
						</span>
					</div>
				) : null}
			</div>

			{multi ? (
				<div className="hv2-hero__progress" role="tablist" aria-label="Слайды баннера">
					{slides.map((s, i) => (
						<button
							key={s.id || i}
							type="button"
							role="tab"
							aria-label={`Слайд ${i + 1}`}
							aria-selected={i === index}
							className={
								i === index
									? "hv2-hero__progress-item is-active"
									: i < index
										? "hv2-hero__progress-item is-past"
										: "hv2-hero__progress-item"
							}
							onClick={() => goTo(i)}
						>
							<span className="hv2-hero__progress-track">
								<span
									className="hv2-hero__progress-fill"
									key={i === index ? `run-${index}` : `idle-${i}`}
								/>
							</span>
						</button>
					))}
				</div>
			) : null}
		</section>
	);
}
