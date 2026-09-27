/** Короткие тексты экрана после блока свайпов. Одно действие — одна золотая кнопка. */

function pct(likes, total) {
	if (!total) return 0;
	return Math.round((likes / total) * 100);
}

function titled(name, phrase) {
	if (name) return `${name}, ${phrase}`;
	return phrase.charAt(0).toUpperCase() + phrase.slice(1);
}

function chunkStat(chunk) {
	const ratio = pct(chunk.likes, chunk.total);
	return {
		stat: `${chunk.likes}/${chunk.total}`,
		caption: chunk.likes > 0 ? `${ratio}% в этом блоке` : "в этом блоке",
	};
}

function visitStat(session) {
	const ratio = pct(session.likes, session.total);
	return {
		stat: `${session.likes}/${session.total}`,
		caption: session.likes > 0 ? `${ratio}% за визит` : "за этот визит",
	};
}

function sessionMeta(session, chunk) {
	if (!session?.total || session.total <= chunk.total) return null;
	return `За визит — ${session.likes} из ${session.total}`;
}

const btn = (id, label, tone) => ({ id, label, tone });

const home = () => btn("home", "На главную", "quiet");

/**
 * @param {{
 *   isAuthenticated: boolean,
 *   displayName?: string | null,
 *   chunk: { likes: number, total: number },
 *   session: { likes: number, total: number },
 *   hasMore: boolean,
 * }} ctx
 */
export function getSwipeCheckpointCopy(ctx) {
	const { isAuthenticated, displayName, chunk, session, hasMore } = ctx;
	const name = displayName?.trim() || null;
	const noLikes = chunk.total > 0 && chunk.likes === 0;
	const high = chunk.total > 0 && chunk.likes / chunk.total >= 0.5;
	const isFinal = !hasMore;

	if (!isAuthenticated && isFinal) {
		const saved = session.likes > 0;
		return {
			kicker: "Antrasha",
			title: saved ? "Подборка собрана" : "Вы посмотрели всё",
			...visitStat(session),
			line: saved
				? "Сохраните лайки — и можно оставить заявку на примерку."
				: "Сохраните профиль — в следующий визит лента узнает вас.",
			actions: [btn("register", "Сохранить профиль", "primary"), home()],
		};
	}

	if (!isAuthenticated) {
		return {
			kicker: "Antrasha",
			title: noLikes
				? "Пока без совпадений"
				: high
					? "Сильное совпадение"
					: "Ваш ритм",
			...chunkStat(chunk),
			meta: sessionMeta(session, chunk),
			line: noLikes
				? "Дальше часто появляется то, что цепляет."
				: high
					? "Сохраните профиль — после этого откроется примерка."
					: "Лайки можно оставить в профиле.",
			actions: noLikes
				? [
						btn("continue", "Смотреть дальше", "primary"),
						btn("register", "Сохранить профиль", "ghost"),
						home(),
					]
				: [
						btn("register", "Сохранить профиль", "primary"),
						btn("continue", "Смотреть дальше", "ghost"),
						home(),
					],
		};
	}

	if (isFinal) {
		const saved = session.likes > 0;
		return {
			kicker: "Antrasha",
			title: titled(name, "на сегодня всё"),
			...visitStat(session),
			line: saved
				? "Соберём отмеченное на примерку."
				: "Новое подстроим под ваш профиль.",
			actions: saved
				? [btn("results", "Заявка на примерку", "primary"), home()]
				: [btn("home", "На главную", "primary")],
			showContacts: !saved,
		};
	}

	return {
		kicker: "Antrasha",
		title: titled(
			name,
			noLikes ? "без совпадений" : high ? "сильное совпадение" : "ваш ритм",
		),
		...chunkStat(chunk),
		meta: sessionMeta(session, chunk),
		line: noLikes
			? "Прошлые отметки уже в подборке."
			: high
				? "Ещё образы уточнят подборку."
				: "Дальше — ближе к вашим лайкам.",
		actions: [btn("continue", "Смотреть дальше", "primary"), home()],
	};
}
