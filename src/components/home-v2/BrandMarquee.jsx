import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { fetchPublicBrands } from "../../api/client.js";
import { HOME_V2_BRANDS } from "./homeV2Constants";
import "./BrandMarquee.css";

function BrandGroup({ brands, ariaHidden = false }) {
	return (
		<div className="hv2-brands__group" aria-hidden={ariaHidden || undefined}>
			{brands.map((name, i) => (
				<span key={`${name}-${i}`} className="hv2-brands__item">
					<span className="hv2-brands__name">{name}</span>
					<span className="hv2-brands__sep" aria-hidden>
						|
					</span>
				</span>
			))}
		</div>
	);
}

function fillCopies(brands, copies) {
	const out = [];
	for (let c = 0; c < copies; c += 1) out.push(...brands);
	return out;
}

export default function BrandMarquee() {
	const [names, setNames] = useState(null);
	const [copies, setCopies] = useState(2);
	const [ready, setReady] = useState(false);
	const wrapRef = useRef(null);
	const measureRef = useRef(null);

	useEffect(() => {
		let cancelled = false;
		(async () => {
			let next = HOME_V2_BRANDS;
			try {
				const data = await fetchPublicBrands();
				const items = Array.isArray(data?.items) ? data.items : [];
				const fromDb = items
					.map((b) => String(b?.name || "").trim())
					.filter(Boolean)
					.map((n) => n.toUpperCase());
				if (fromDb.length > 0) next = fromDb;
			} catch {
				/* fallback */
			}
			if (!cancelled) {
				setReady(false);
				setCopies(2);
				setNames(next);
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	useLayoutEffect(() => {
		if (!names?.length) return undefined;

		let cancelled = false;

		const run = async () => {
			try {
				if (document.fonts?.ready) await document.fonts.ready;
			} catch {
				/* ignore */
			}
			if (cancelled) return;

			const wrapW = wrapRef.current?.clientWidth || 0;
			const oneCycleW = measureRef.current?.scrollWidth || 0;
			if (wrapW && oneCycleW) {
				const need = Math.max(2, Math.ceil((wrapW * 1.25) / oneCycleW));
				if (need !== copies) {
					setCopies(need);
					return; /* следующий layout-effect после обновления copies */
				}
			}

			requestAnimationFrame(() => {
				if (!cancelled) setReady(true);
			});
		};

		setReady(false);
		run();

		const onResize = () => {
			setReady(false);
			setCopies(2);
		};
		window.addEventListener("resize", onResize);
		return () => {
			cancelled = true;
			window.removeEventListener("resize", onResize);
		};
	}, [names, copies]);

	if (!names?.length) {
		return (
			<section className="hv2-brands" aria-label="Бренды в бутиках" />
		);
	}

	const group = fillCopies(names, copies);
	const durationSec = Math.max(40, Math.min(90, group.length * 3.5));

	return (
		<section className="hv2-brands" aria-label="Бренды в бутиках">
			<div className="hv2-brands__track-wrap" ref={wrapRef}>
				<div className="hv2-brands__measure" ref={measureRef} aria-hidden>
					<BrandGroup brands={names} ariaHidden />
				</div>
				<div
					key={`${names.join("|")}::${copies}`}
					className={
						ready
							? "hv2-brands__track hv2-brands__track--run"
							: "hv2-brands__track"
					}
					style={{ "--hv2-marquee-duration": `${durationSec}s` }}
				>
					<BrandGroup brands={group} />
					<BrandGroup brands={group} ariaHidden />
				</div>
			</div>
		</section>
	);
}
