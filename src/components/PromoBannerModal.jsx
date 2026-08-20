import { useNavigate } from "react-router-dom";
import { useEffect, useRef } from "react";
import { markPromoBannerSeen } from "../api/client.js";
import { markPromoBannerSeenThisSession } from "../utils/promoBannerSession.js";
import "./PromoBannerModal.css";

/**
 * Безопасный рендер: переносы строк + **жирный**. HTML из текста не интерпретируется.
 * @param {string} text
 * @returns {import("react").ReactNode[]}
 */
export function renderPromoMarkup(text) {
	const raw = String(text ?? "");
	const nodes = [];
	const lines = raw.split("\n");
	lines.forEach((line, lineIdx) => {
		if (lineIdx > 0) nodes.push(<br key={`br-${lineIdx}`} />);
		const re = /\*\*(.+?)\*\*/g;
		let last = 0;
		let m;
		let part = 0;
		while ((m = re.exec(line)) !== null) {
			if (m.index > last) {
				nodes.push(line.slice(last, m.index));
			}
			nodes.push(
				<strong key={`b-${lineIdx}-${part++}`}>{m[1]}</strong>,
			);
			last = m.index + m[0].length;
		}
		if (last < line.length) nodes.push(line.slice(last));
		if (line.length === 0 && lineIdx < lines.length - 1) {
			/* пустая строка уже дала <br> */
		}
	});
	return nodes;
}

/**
 * @param {{
 *   banner: {
 *     id: string,
 *     title: string,
 *     body?: string | null,
 *     image_url?: string | null,
 *     image_fit?: string | null,
 *     link_url?: string | null,
 *     link_label?: string | null,
 *     show_gender_ctas?: boolean,
 *     cta_male_label?: string | null,
 *     cta_female_label?: string | null,
 *   },
 *   onClose: () => void,
 * }} props
 */
export default function PromoBannerModal({ banner, onClose }) {
	const navigate = useNavigate();
	const seenSent = useRef(false);

	useEffect(() => {
		if (!banner || seenSent.current) return;
		seenSent.current = true;
		markPromoBannerSeenThisSession(banner.id);
		markPromoBannerSeen(banner.id).catch(() => {});
	}, [banner]);

	if (!banner) return null;

	const linkLabel = (banner.link_label || "").trim() || "Подробнее";
	const hasLink = !!(banner.link_url || "").trim();
	const showGender = !!banner.show_gender_ctas;
	const maleLabel = (banner.cta_male_label || "").trim() || "Мужчинам";
	const femaleLabel = (banner.cta_female_label || "").trim() || "Женщинам";
	const imageFit = banner.image_fit === "cover" ? "cover" : "fit";

	function goCollection(gender) {
		onClose();
		navigate(`/swipe/${gender}`);
	}

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
					<div
						className={`promo-banner-media promo-banner-media--${imageFit}`}
					>
						<img src={banner.image_url} alt="" />
					</div>
				) : null}
				<div className="promo-banner-body">
					<h2 id="promo-banner-title" className="promo-banner-title">
						{renderPromoMarkup(banner.title)}
					</h2>
					{banner.body ? (
						<p className="promo-banner-text">
							{renderPromoMarkup(banner.body)}
						</p>
					) : null}
					<div className="promo-banner-actions">
						{showGender ? (
							<div className="promo-banner-gender-row">
								<button
									type="button"
									className="promo-banner-cta promo-banner-cta--male"
									onClick={() => goCollection("male")}
								>
									{maleLabel}
								</button>
								<button
									type="button"
									className="promo-banner-cta promo-banner-cta--female"
									onClick={() => goCollection("female")}
								>
									{femaleLabel}
								</button>
							</div>
						) : null}
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
