/** Тексты итогов после свайпов. Форма и заявка живут в ThankYou. */

function pct(likes, total) {
	if (!total) return 0;
	return Math.round((likes / total) * 100);
}

function titled(name, phrase) {
	if (name) return `${name}, ${phrase}`;
	return phrase.charAt(0).toUpperCase() + phrase.slice(1);
}

/**
 * @param {{
 *   isAuthenticated: boolean,
 *   displayName?: string | null,
 *   likes: number,
 *   total: number,
 * }} ctx
 */
export function getThankYouCopy(ctx) {
	const { isAuthenticated, displayName, likes, total } = ctx;
	const name = displayName?.trim() || null;
	const hasLikes = likes > 0;
	const high = total > 0 && likes / total >= 0.5;
	const ratio = pct(likes, total);

	let title;
	let line;

	if (isAuthenticated && name) {
		title = `${name}, спасибо`;
		line = hasLikes
			? "Отметки уже в профиле."
			: "Сессию учли — в следующий раз будет точнее.";
	} else if (!hasLikes) {
		title = titled(name, "в этот раз мимо");
		line = isAuthenticated
			? "Сессию учли — в следующий раз будет точнее."
			: "Профиль запомнит этот визит. В следующий раз лента откроется уже вашей.";
	} else if (high) {
		title = titled(name, "сильное совпадение");
		line = isAuthenticated
			? "Отметки уже в профиле."
			: "Сохраните профиль — и оставьте заявку на примерку.";
	} else {
		title = titled(name, "хороший старт");
		line = isAuthenticated
			? "Отметки уже в профиле."
			: "Сохраним лайки — подборка станет личной.";
	}

	return {
		title,
		line,
		stat: total > 0 ? `${likes}/${total}` : null,
		caption:
			total > 0 ? (hasLikes ? `${ratio}% совпало` : "без лайков") : null,
		hasLikes,
		fittingLine:
			"Позвоним по номеру из профиля: бутик на Радищева, 37 или выезд к вам.",
	};
}
