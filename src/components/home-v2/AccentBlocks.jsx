import { HOME_V2_ACCENTS } from "./homeV2Constants";
import "./AccentBlocks.css";

function AccentIcon({ type }) {
	if (type === "truck") {
		return (
			<svg viewBox="0 0 24 24" className="hv2-accent__icon" aria-hidden>
				<path
					fill="none"
					stroke="currentColor"
					strokeWidth="1.2"
					d="M3 7.5h11v8H3zM14 10.5h4.2L21 13.2v2.3h-7z"
				/>
				<circle cx="7" cy="16.5" r="1.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
				<circle cx="17.5" cy="16.5" r="1.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
			</svg>
		);
	}
	if (type === "hanger") {
		return (
			<svg viewBox="0 0 24 24" className="hv2-accent__icon" aria-hidden>
				<path
					fill="none"
					stroke="currentColor"
					strokeWidth="1.2"
					d="M12 4.5a1.6 1.6 0 1 1 1.5 1.55V8L21 14.2a1 1 0 0 1-.6 1.8H3.6a1 1 0 0 1-.6-1.8L10.5 8V6.05"
				/>
			</svg>
		);
	}
	return (
		<svg viewBox="0 0 24 24" className="hv2-accent__icon" aria-hidden>
			<path
				fill="none"
				stroke="currentColor"
				strokeWidth="1.2"
				d="M12 3.5 13.9 9h5.6l-4.5 3.4 1.7 5.6L12 14.8 7.3 18l1.7-5.6L4.5 9h5.6z"
			/>
		</svg>
	);
}

export default function AccentBlocks({ onSelect }) {
	return (
		<section className="hv2-accents" aria-label="Сервис">
			{HOME_V2_ACCENTS.map((item) => (
				<button
					key={item.id}
					type="button"
					className="hv2-accent"
					onClick={() => onSelect?.(item)}
				>
					<AccentIcon type={item.icon} />
					<span className="hv2-accent__title">{item.title}</span>
				</button>
			))}
		</section>
	);
}
