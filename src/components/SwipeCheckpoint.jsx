import { Link } from "react-router-dom";
import { getSwipeCheckpointCopy } from "../content/swipeCheckpointCopy.js";
import "../pages/ThankYou.css";

export default function SwipeCheckpoint({
	isAuthenticated,
	displayName,
	chunk,
	session,
	hasMore,
	tasteVectorReady,
	onContinue,
	onGoThankYou,
	onHome,
}) {
	const copy = getSwipeCheckpointCopy({
		isAuthenticated,
		displayName,
		chunk,
		session,
		hasMore,
		tasteVectorReady,
	});

	const guestLead =
		copy.guestProgramLead ||
		"Вступите в программу Antrasha: сохраним лайки и предпочтения, будем присылать новинки под вашу эстетику (около одного раза в неделю).";

	return (
		<div className="thank-container thank-scroll">
			<p className="thank-kicker">
				<span>{copy.kicker[0]}</span>
				<span>{copy.kicker[1]}</span>
			</p>
			<h2 className="thank-heading">{copy.title}</h2>
			<p className="thank-stats">{copy.stats}</p>
			{copy.body ? <p className="thank-note">{copy.body}</p> : null}
			{copy.tasteHint ? (
				<p className="thank-note" style={{ fontSize: "0.88rem", color: "rgba(255,255,255,0.55)" }}>
					{copy.tasteHint}
				</p>
			) : null}

			{copy.showGuestProgram ? (
				<div className="thank-fitting" style={{ marginTop: "0.5rem" }}>
					<p className="thank-fitting-text">{guestLead}</p>
					<button type="button" className="thank-button thank-submit" onClick={onGoThankYou}>
						Вступить в программу
					</button>
				</div>
			) : null}

			<button type="button" className="thank-button thank-submit" onClick={onContinue}>
				{copy.primaryLabel}
			</button>
			<button type="button" className="thank-button thank-secondary" onClick={onHome}>
				{copy.secondaryLabel}
			</button>
			<p className="thank-note" style={{ marginTop: "0.75rem", fontSize: "0.82rem" }}>
				<Link to="/about" style={{ color: "rgba(255,255,255,0.5)" }}>
					О программе
				</Link>
			</p>
		</div>
	);
}
