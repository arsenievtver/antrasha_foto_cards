/** Экран, когда непросмотренных фото нет или каталог пуст. */

const GENDER_IN = {
	male: "мужской коллекции",
	female: "женской коллекции",
};

function inCollection(gender) {
	const key = (gender || "").trim().toLowerCase();
	return GENDER_IN[key] || "этой коллекции";
}

const btn = (id, label, tone) => ({ id, label, tone });

/**
 * @param {{
 *   kind: "exhausted" | "no_catalog",
 *   gender?: string,
 *   isAuthenticated: boolean,
 *   displayName?: string | null,
 *   totalInCatalog?: number,
 * }} ctx
 */
export function getSwipeFeedEmptyCopy(ctx) {
	const { kind, gender, isAuthenticated, displayName, totalInCatalog } = ctx;
	const where = inCollection(gender);
	const name = displayName?.trim() || null;
	const seen = Number(totalInCatalog) > 0 ? Number(totalInCatalog) : 0;

	if (kind === "no_catalog") {
		return {
			kicker: "Antrasha",
			title: "Пока пусто",
			line: `В ${where} нет образов. Загляните в другую коллекцию.`,
			actions: [btn("home", "На главную", "primary")],
		};
	}

	if (isAuthenticated) {
		return {
			kicker: "Antrasha",
			title: name ? `${name}, вы всё оценили` : "Вы всё оценили",
			stat: seen ? String(seen) : null,
			caption: seen ? "уже просмотрено" : null,
			line: `В ${where} нового нет. Пересмотр уточняет вкус.`,
			actions: [
				btn("replay", "Пересмотреть", "primary"),
				btn("home", "На главную", "quiet"),
			],
		};
	}

	return {
		kicker: "Antrasha",
		title: "Вы всё посмотрели",
		stat: seen ? String(seen) : null,
		caption: seen ? "уже просмотрено" : null,
		line: "Сохраните профиль — в следующий визит лента узнает вас с первого кадра.",
		actions: [
			btn("register", "Сохранить профиль", "primary"),
			btn("replay", "Пересмотреть", "ghost"),
			btn("home", "На главную", "quiet"),
		],
	};
}
