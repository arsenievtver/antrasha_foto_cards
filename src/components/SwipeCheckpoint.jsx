import JournalScreen, {
	JournalActions,
	JournalContacts,
} from "./JournalScreen.jsx";
import { getSwipeCheckpointCopy } from "../content/swipeCheckpointCopy.js";
import "./JournalScreen.css";

export default function SwipeCheckpoint({
	isAuthenticated,
	displayName,
	chunk,
	session,
	hasMore,
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
	});

	function onAction(id) {
		if (id === "register") onGoThankYou();
		else if (id === "home") onHome();
		else onContinue();
	}

	return (
		<JournalScreen
			kicker={copy.kicker}
			title={copy.title}
			stat={copy.stat}
			caption={copy.caption}
			meta={copy.meta}
			line={copy.line}
		>
			<JournalActions actions={copy.actions} onAction={onAction} />
			{copy.showContacts ? <JournalContacts /> : null}
		</JournalScreen>
	);
}
