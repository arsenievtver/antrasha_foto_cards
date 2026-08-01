import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchHomeV2GenderCards } from "../../api/client.js";
import menFallback from "../../assets/image/2m.webp";
import womenFallback from "../../assets/image/1w.webp";
import "./GenderCards.css";

function withCacheBust(url, updatedAt) {
	if (!url) return url;
	if (!updatedAt) return url;
	const t = new Date(updatedAt).getTime();
	if (!Number.isFinite(t)) return url;
	const sep = url.includes("?") ? "&" : "?";
	return `${url}${sep}v=${t}`;
}

export default function GenderCards() {
	const navigate = useNavigate();
	const [maleSrc, setMaleSrc] = useState(menFallback);
	const [femaleSrc, setFemaleSrc] = useState(womenFallback);

	useEffect(() => {
		let cancelled = false;
		(async () => {
			try {
				const data = await fetchHomeV2GenderCards();
				if (cancelled) return;
				const male = withCacheBust(data?.image_url_male, data?.updated_at);
				const female = withCacheBust(data?.image_url_female, data?.updated_at);
				if (male) setMaleSrc(male);
				if (female) setFemaleSrc(female);
			} catch {
				/* fallback assets */
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	return (
		<section className="hv2-gender" aria-label="Коллекции">
			<button
				type="button"
				className="hv2-gender__card"
				onClick={() => navigate("/swipe/male")}
			>
				<img src={maleSrc} alt="" className="hv2-gender__img" />
				<div className="hv2-gender__gloss" aria-hidden />
				<div className="hv2-gender__overlay">
					<span className="hv2-gender__label">MEN</span>
					<span className="hv2-gender__sub">Новинки</span>
					<span className="hv2-gender__cta">
						СМОТРЕТЬ <span aria-hidden>→</span>
					</span>
				</div>
			</button>
			<button
				type="button"
				className="hv2-gender__card"
				onClick={() => navigate("/swipe/female")}
			>
				<img src={femaleSrc} alt="" className="hv2-gender__img" />
				<div className="hv2-gender__gloss" aria-hidden />
				<div className="hv2-gender__overlay">
					<span className="hv2-gender__label">WOMEN</span>
					<span className="hv2-gender__sub">Новинки</span>
					<span className="hv2-gender__cta">
						СМОТРЕТЬ <span aria-hidden>→</span>
					</span>
				</div>
			</button>
		</section>
	);
}
