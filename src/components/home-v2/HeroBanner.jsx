import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import "./HeroBanner.css";

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

export default function HeroBanner({ items }) {
	const slides = items?.length ? items : [];
	const [index, setIndex] = useState(0);

	useEffect(() => {
		setIndex(0);
	}, [slides.length]);

	useEffect(() => {
		if (slides.length <= 1) return undefined;
		const t = setInterval(() => {
			setIndex((i) => (i + 1) % slides.length);
		}, 6000);
		return () => clearInterval(t);
	}, [slides.length]);

	if (!slides.length) return null;
	const slide = slides[index] || null;
	const mobileSrc = withCacheBust(slide?.image_url, slide?.updated_at);
	const desktopSrc =
		withCacheBust(slide?.image_url_desktop, slide?.updated_at) || mobileSrc;
	const hasImage = Boolean(mobileSrc || desktopSrc);
	const title = (slide?.title || "").trim();
	const subtitle = (slide?.subtitle || "").trim();
	const body = (slide?.body || "").trim();
	const linkUrl = (slide?.link_url || "").trim();
	const linkLabel = (slide?.link_label || "").trim() || "СМОТРЕТЬ НОВИНКИ";
	const total = slides.length;
	const isPlaceholderTitle = !hasImage && title.length > 40;
	const ctaInner = (
		<>
			<span>{linkLabel}</span>
			<span className="hv2-hero__cta-arrow" aria-hidden>
				→
			</span>
		</>
	);

	return (
		<section
			className={hasImage ? "hv2-hero" : "hv2-hero hv2-hero--placeholder"}
			aria-label="Баннер"
		>
			<div className="hv2-hero__media" aria-hidden>
				{hasImage ? (
					<picture>
						{desktopSrc ? (
							<source media="(min-width: 768px)" srcSet={desktopSrc} />
						) : null}
						<img src={mobileSrc || desktopSrc} alt="" className="hv2-hero__img" />
					</picture>
				) : (
					<div className="hv2-hero__blank" />
				)}
				<div className="hv2-hero__scrim" />
			</div>

			<div className="hv2-hero__content">
				<div className="hv2-hero__copy">
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
						isInternalPath(linkUrl) ? (
							<Link className="hv2-hero__cta" to={linkUrl}>
								{ctaInner}
							</Link>
						) : (
							<a
								className="hv2-hero__cta"
								href={linkUrl}
								target="_blank"
								rel="noopener noreferrer"
							>
								{ctaInner}
							</a>
						)
					) : null}
				</div>

				{total > 1 ? (
					<div className="hv2-hero__footer">
						<span className="hv2-hero__counter">
							{padIndex(index + 1)} / {padIndex(total)}
						</span>
					</div>
				) : null}
			</div>

			{slides.length > 1 ? (
				<div className="hv2-hero__dots" role="tablist" aria-label="Слайды баннера">
					{slides.map((s, i) => (
						<button
							key={s.id || i}
							type="button"
							role="tab"
							aria-selected={i === index}
							className={
								i === index ? "hv2-hero__dot hv2-hero__dot--active" : "hv2-hero__dot"
							}
							onClick={() => setIndex(i)}
						/>
					))}
				</div>
			) : null}
		</section>
	);
}
