import { useEffect, useRef } from "react";
import { markPromoBannerSeen } from "../api/client.js";
import "./PromoBannerModal.css";

/**
 * @param {{ banner: { id: string, title: string, body?: string | null, image_url?: string | null, link_url?: string | null, link_label?: string | null }, onClose: () => void }} props
 */
export default function PromoBannerModal({ banner, onClose }) {
	const seenSent = useRef(false);

	useEffect(() => {
		if (!banner || seenSent.current) return;
		seenSent.current = true;
		markPromoBannerSeen(banner.id).catch(() => {});
	}, [banner]);

	if (!banner) return null;

	const linkLabel = (banner.link_label || "").trim() || "Подробнее";
	const hasLink = !!(banner.link_url || "").trim();

	return (
		<div
			className="promo-banner"
			role="dialog"
			aria-modal="true"
			aria-labelledby="promo-banner-title"
		>
			<button
				type="button"
				className="promo-banner-close"
				onClick={onClose}
				aria-label="Закрыть"
			>
				×
			</button>
			<div className="promo-banner-scrim" aria-hidden onClick={onClose} />
			<div className="promo-banner-card">
				{banner.image_url ? (
					<div className="promo-banner-media">
						<img src={banner.image_url} alt="" />
					</div>
				) : null}
				<div className="promo-banner-body">
					<h2 id="promo-banner-title" className="promo-banner-title">
						{banner.title}
					</h2>
					{banner.body ? (
						<p className="promo-banner-text">{banner.body}</p>
					) : null}
					<div className="promo-banner-actions">
						{hasLink ? (
							<a
								className="promo-banner-link"
								href={banner.link_url.trim()}
								target="_blank"
								rel="noopener noreferrer"
							>
								{linkLabel}
							</a>
						) : null}
						<button
							type="button"
							className="promo-banner-dismiss"
							onClick={onClose}
						>
							Закрыть
						</button>
					</div>
				</div>
			</div>
		</div>
	);
}
