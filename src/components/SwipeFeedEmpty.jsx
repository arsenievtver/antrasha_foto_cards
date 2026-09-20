import { Link } from "react-router-dom";
import { getSwipeFeedEmptyCopy } from "../content/swipeFeedEmptyCopy.js";
import "../pages/ThankYou.css";

export default function SwipeFeedEmpty({
	kind,
	gender,
	isAuthenticated,
	displayName,
	totalInCatalog,
	onReplay,
	onHome,
	onGuestProgram,
}) {
	const copy = getSwipeFeedEmptyCopy({
		kind,
		gender,
		isAuthenticated,
		displayName,
		totalInCatalog,
	});

	return (
		<div className="thank-container thank-scroll">
			<p className="thank-kicker">
				<span>{copy.kicker[0]}</span>
				<span>{copy.kicker[1]}</span>
			</p>
			<h2 className="thank-heading">{copy.title}</h2>
			<p className="thank-note">{copy.body}</p>

			{copy.showGuestHint ? (
				<div className="thank-fitting" style={{ marginTop: "0.5rem" }}>
					<p className="thank-fitting-text">
						Вступите в программу — сохраним прогресс и будем присылать новинки под ваш стиль.
					</p>
					<button type="button" className="thank-button thank-submit" onClick={onGuestProgram}>
						Вступить в программу
					</button>
				</div>
			) : null}

			{copy.showReplay ? (
				<button type="button" className="thank-button thank-submit" onClick={onReplay}>
					{copy.primaryLabel}
				</button>
			) : (
				<button type="button" className="thank-button thank-submit" onClick={onHome}>
					{copy.primaryLabel}
				</button>
			)}

			{copy.secondaryLabel ? (
				<button type="button" className="thank-button thank-secondary" onClick={onHome}>
					{copy.secondaryLabel}
				</button>
			) : null}

			<p className="thank-note" style={{ marginTop: "0.75rem", fontSize: "0.82rem" }}>
				<Link to="/about" style={{ color: "rgba(255,255,255,0.5)" }}>
					О программе
				</Link>
			</p>
		</div>
	);
}
