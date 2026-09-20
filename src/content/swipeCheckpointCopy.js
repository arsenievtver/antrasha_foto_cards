/** Тексты промежуточного экрана после чанка свайпов. */

const HIGH_MATCH_RATIO = 0.5;

function pct(likes, total) {
	if (!total) return 0;
	return Math.round((likes / total) * 100);
}

function isHighMatch(likes, total) {
	return total > 0 && likes > 0 && likes / total >= HIGH_MATCH_RATIO;
}

/**
 * @param {{
 *   isAuthenticated: boolean,
 *   displayName?: string | null,
 *   chunk: { likes: number, total: number },
 *   session: { likes: number, total: number },
 *   hasMore: boolean,
 *   tasteVectorReady?: boolean,
 * }} ctx
 */
export function getSwipeCheckpointCopy(ctx) {
	const { isAuthenticated, displayName, chunk, session, hasMore, tasteVectorReady } =
		ctx;
	const name = displayName?.trim() || null;
	const chunkPct = pct(chunk.likes, chunk.total);
	const sessionPct = pct(session.likes, session.total);
	const high = isHighMatch(chunk.likes, chunk.total);
	const chunkNoLikes = chunk.total > 0 && chunk.likes === 0;
	const isFinal = !hasMore;

	const tasteHint =
		tasteVectorReady && chunk.likes > 0
			? "По вашим отметкам подборка сужается — дальше чаще будут образы ближе к вашим лайкам."
			: tasteVectorReady
				? "Профиль вкуса уже считается — лайки и дизлайки уточняют его; «Дальше» только отмечает просмотр."
				: null;

	if (!isAuthenticated) {
		if (isFinal) {
			return {
				kicker: ["Antrasha", "персональная подборка"],
				title: "Вы посмотрели всё, что было в подборке сейчас",
				stats: `За визит: ${session.likes} из ${session.total} с лайком${session.total ? ` (${sessionPct}%)` : ""}.`,
				body:
					chunkNoLikes && session.likes === 0
						? "Если захотите быть в курсе новых образов — вступите в программу: сохраним прогресс и будем присылать подборки под ваш стиль."
						: "Вступите в Antrasha — сохраним лайки и будем присылать новинки под ваш вкус.",
				tasteHint,
				showGuestProgram: true,
				primaryLabel: "Итоги и регистрация",
				secondaryLabel: "На главную",
			};
		}

		if (chunkNoLikes) {
			return {
				kicker: ["Antrasha", "персональная подборка"],
				title: "Пока без совпадений — это нормально",
				stats: `В этом блоке: 0 из ${chunk.total}. За сессию: ${session.likes} из ${session.total}.`,
				body:
					"Можно идти дальше — в следующих образах часто появляется то, что цепляет. Или вернуться на главную.",
				tasteHint,
				showGuestProgram: true,
				primaryLabel: "Продолжить",
				secondaryLabel: "На главную",
				continueLabel: null,
			};
		}

		if (high) {
			return {
				kicker: ["Antrasha", "персональная подборка"],
				title: "Сильное совпадение в этом блоке",
				stats: `${chunk.likes} из ${chunk.total} — ${chunkPct}% лайков. За сессию: ${session.likes} из ${session.total}.`,
				body:
					"Похоже, коллекция вам близка. Закрепите профиль — точнее подберём новинки и откроем заявку на примерку после регистрации.",
				tasteHint,
				showGuestProgram: true,
				primaryLabel: "Продолжить",
				secondaryLabel: "На главную",
				continueLabel: null,
			};
		}

		return {
			kicker: ["Antrasha", "персональная подборка"],
			title: "Уже виден ваш ритм",
			stats: `В этом блоке: ${chunk.likes} из ${chunk.total} — ${chunkPct}%. За сессию: ${session.likes} из ${session.total}.`,
			body: tasteHint,
			tasteHint: null,
			showGuestProgram: true,
			guestProgramLead:
				"Сохраните прогресс в программе Antrasha — перенесём лайки в профиль, будем присылать новинки под ваш стиль (около одного раза в неделю).",
			primaryLabel: "Продолжить",
			secondaryLabel: "На главную",
			continueLabel: null,
		};
	}

	// Авторизован
	if (isFinal) {
		return {
			kicker: ["Antrasha", "программа лояльности вкуса"],
			title: name
				? `${name}, на сегодня всё из текущего каталога`
				: "На сегодня всё из текущего каталога",
			stats: `За визит: ${session.likes} из ${session.total} с лайком${session.total ? ` (${sessionPct}%)` : ""}.`,
			body:
				"Когда появятся новые образы — подстроим ленту под ваш профиль. Можно оформить заявку на примерку или вернуться на главную.",
			tasteHint,
			showGuestProgram: false,
			primaryLabel: "Итоги и примерка",
			secondaryLabel: "На главную",
			continueLabel: null,
		};
	}

	if (chunkNoLikes) {
		return {
			kicker: ["Antrasha", "программа лояльности вкуса"],
			title: name ? `${name}, в этом блоке мимо — бывает` : "В этом блоке мимо — бывает",
			stats: `0 из ${chunk.total} в этом блоке. За визит: ${session.likes} из ${session.total}.`,
			body: "Продолжим подборку — ваши прошлые лайки учитываются в рекомендациях.",
			tasteHint,
			showGuestProgram: false,
			primaryLabel: "Смотреть дальше",
			secondaryLabel: "На главную",
			continueLabel: null,
		};
	}

	if (high) {
		return {
			kicker: ["Antrasha", "программа лояльности вкуса"],
			title: name ? `${name}, отличный темп` : "Отличный темп",
			stats: `В этом блоке: ${chunk.likes} из ${chunk.total} (${chunkPct}%). Всего за визит: ${session.likes} из ${session.total}.`,
			body: "Профиль вкуса обновляется — следующие образы ранжируем точнее под вас.",
			tasteHint,
			showGuestProgram: false,
			primaryLabel: "Смотреть дальше",
			secondaryLabel: "На главную",
			continueLabel: null,
		};
	}

	return {
		kicker: ["Antrasha", "программа лояльности вкуса"],
		title: name ? `${name}, хороший ритм` : "Хороший ритм",
		stats: `В этом блоке: ${chunk.likes} из ${chunk.total} (${chunkPct}%). За визит: ${session.likes} из ${session.total}.`,
		body: "Профиль вкуса обновляется — следующие образы будем подстраивать под вас.",
		tasteHint,
		showGuestProgram: false,
		primaryLabel: "Смотреть дальше",
		secondaryLabel: "На главную",
		continueLabel: null,
	};
}
