/** Экран, когда в ленте нет непросмотренных фото (каталог исчерпан) или каталог пуст. */

const GENDER_LABEL = {
	male: "мужская коллекция",
	female: "женская коллекция",
};

function genderLabel(gender) {
	const g = (gender || "").trim().toLowerCase();
	return GENDER_LABEL[g] || "эта коллекция";
}

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
	const collection = genderLabel(gender);
	const name = displayName?.trim() || null;

	if (kind === "no_catalog") {
		return {
			kicker: ["Antrasha", "подборка образов"],
			title: "В этой коллекции пока нет образов",
			body: `Сейчас в ${collection} нет активных фото. Загляните в другую коллекцию или на главную — мы добавляем новые пакеты регулярно.`,
			primaryLabel: "На главную",
			secondaryLabel: null,
			showReplay: false,
		};
	}

	// catalog exhausted — всё уже просмотрено
	if (isAuthenticated) {
		return {
			kicker: ["Antrasha", "программа лояльности вкуса"],
			title: name
				? `${name}, вы уже оценили всё в ${collection}`
				: `Вы уже оценили всё в ${collection}`,
			body:
				totalInCatalog && totalInCatalog > 0
					? `Новых образов здесь пока нет (${totalInCatalog} вы уже видели). Когда выйдет свежий пакет — подстроим ленту под ваш профиль. А пока можно спокойно пересмотреть увиденное — лайки и «Дальше» по-прежнему уточняют ваш вкус.`
					: "Новых образов здесь пока нет. Когда появится свежий пакет — подстроим ленту под ваш профиль. А пока можно пересмотреть уже увиденное.",
			primaryLabel: "Пересмотреть увиденное",
			secondaryLabel: "На главную",
			showReplay: true,
		};
	}

	return {
		kicker: ["Antrasha", "персональная подборка"],
		title: "Вы посмотрели всё, что было в этой подборке",
		body:
			totalInCatalog && totalInCatalog > 0
				? `Сейчас ${totalInCatalog} образов — вы их уже листали. Новые появятся позже; можно пересмотреть каталог или вступить в программу, чтобы сохранить лайки и получать подборки (около одного раза в неделю).`
				: "Новые образы появятся позже. Можно пересмотреть каталог или вступить в программу Antrasha.",
		primaryLabel: "Пересмотреть увиденное",
		secondaryLabel: "На главную",
		showReplay: true,
		showGuestHint: true,
	};
}
