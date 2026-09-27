import JournalScreen, {
	JournalActions,
} from "./JournalScreen.jsx";
import { getSwipeFeedEmptyCopy } from "../content/swipeFeedEmptyCopy.js";
import "./JournalScreen.css";

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

	function onAction(id) {
		if (id === "register") onGuestProgram();
		else if (id === "replay") onReplay();
		else onHome();
	}

	return (
		<JournalScreen
			kicker={copy.kicker}
			title={copy.title}
			stat={copy.stat}
			caption={copy.caption}
			line={copy.line}
		>
			<JournalActions actions={copy.actions} onAction={onAction} />
		</JournalScreen>
	);
}
