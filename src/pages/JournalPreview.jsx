import { useState } from "react";
import SwipeCheckpoint from "../components/SwipeCheckpoint.jsx";
import SwipeFeedEmpty from "../components/SwipeFeedEmpty.jsx";
import JournalScreen, { JournalContacts } from "../components/JournalScreen.jsx";
import PrivacyConsent from "../components/PrivacyConsent.jsx";
import { getThankYouCopy } from "../content/thankYouCopy.js";
import "../components/JournalScreen.css";
import "./JournalPreview.css";

const noop = () => {};

const SCREENS = [
	{
		id: "guest-zero",
		label: "Гость, без лайков",
		render: () => (
			<SwipeCheckpoint
				isAuthenticated={false}
				chunk={{ likes: 0, total: 10 }}
				session={{ likes: 0, total: 10 }}
				hasMore
				onContinue={noop}
				onGoThankYou={noop}
				onHome={noop}
			/>
		),
	},
	{
		id: "guest-some",
		label: "Гость, есть лайки",
		render: () => (
			<SwipeCheckpoint
				isAuthenticated={false}
				chunk={{ likes: 3, total: 10 }}
				session={{ likes: 3, total: 20 }}
				hasMore
				onContinue={noop}
				onGoThankYou={noop}
				onHome={noop}
			/>
		),
	},
	{
		id: "guest-high",
		label: "Гость, сильное совпадение",
		render: () => (
			<SwipeCheckpoint
				isAuthenticated={false}
				chunk={{ likes: 6, total: 10 }}
				session={{ likes: 6, total: 10 }}
				hasMore
				onContinue={noop}
				onGoThankYou={noop}
				onHome={noop}
			/>
		),
	},
	{
		id: "guest-final",
		label: "Гость, всё просмотрено",
		render: () => (
			<SwipeCheckpoint
				isAuthenticated={false}
				chunk={{ likes: 7, total: 10 }}
				session={{ likes: 7, total: 20 }}
				hasMore={false}
				onContinue={noop}
				onGoThankYou={noop}
				onHome={noop}
			/>
		),
	},
	{
		id: "member-next",
		label: "Профиль, смотреть дальше",
		render: () => (
			<SwipeCheckpoint
				isAuthenticated
				displayName="Анна"
				chunk={{ likes: 6, total: 10 }}
				session={{ likes: 9, total: 20 }}
				hasMore
				onContinue={noop}
				onGoThankYou={noop}
				onHome={noop}
			/>
		),
	},
	{
		id: "member-final",
		label: "Профиль, заявка",
		render: () => (
			<SwipeCheckpoint
				isAuthenticated
				displayName="Анна"
				chunk={{ likes: 7, total: 10 }}
				session={{ likes: 7, total: 20 }}
				hasMore={false}
				onContinue={noop}
				onGoThankYou={noop}
				onHome={noop}
			/>
		),
	},
	{
		id: "member-zero",
		label: "Профиль, без лайков",
		render: () => (
			<SwipeCheckpoint
				isAuthenticated
				displayName="Анна"
				chunk={{ likes: 0, total: 10 }}
				session={{ likes: 0, total: 20 }}
				hasMore={false}
				onContinue={noop}
				onGoThankYou={noop}
				onHome={noop}
			/>
		),
	},
	{
		id: "empty-guest",
		label: "Лента пуста, гость",
		render: () => (
			<SwipeFeedEmpty
				kind="exhausted"
				gender="female"
				isAuthenticated={false}
				totalInCatalog={42}
				onReplay={noop}
				onHome={noop}
				onGuestProgram={noop}
			/>
		),
	},
	{
		id: "empty-member",
		label: "Лента пуста, профиль",
		render: () => (
			<SwipeFeedEmpty
				kind="exhausted"
				gender="female"
				isAuthenticated
				displayName="Анна"
				totalInCatalog={42}
				onReplay={noop}
				onHome={noop}
				onGuestProgram={noop}
			/>
		),
	},
	{
		id: "thanks-form",
		label: "Итоги, регистрация",
		render: () => <ThanksForm />,
	},
	{
		id: "thanks-fit",
		label: "Итоги, примерка",
		render: () => <ThanksFitting />,
	},
];

function ThanksForm() {
	const copy = getThankYouCopy({
		isAuthenticated: false,
		likes: 7,
		total: 20,
	});
	return (
		<JournalScreen title={copy.title} stat={copy.stat} caption={copy.caption} line={copy.line}>
			<div className="journal-tabs">
				<button type="button" className="journal-tab">
					Войти
				</button>
				<button type="button" className="journal-tab is-active">
					Регистрация
				</button>
			</div>
			<form className="journal-form" onSubmit={(e) => e.preventDefault()}>
				<label className="journal-label">Имя</label>
				<input className="journal-input" placeholder="Как к вам обращаться" readOnly />
				<label className="journal-label">Телефон</label>
				<input className="journal-input" placeholder="+7 (999) 123-45-67" readOnly />
				<label className="journal-label">PIN</label>
				<p className="journal-hint">6 цифр — код входа с любого устройства.</p>
				<input className="journal-input" placeholder="•••-•••" readOnly />
				<PrivacyConsent className="privacy-consent--journal" />
				<button type="button" className="journal-btn journal-btn--primary">
					Сохранить профиль
				</button>
			</form>
			<button type="button" className="journal-btn journal-btn--quiet journal-home">
				На главную
			</button>
		</JournalScreen>
	);
}

function ThanksFitting() {
	const copy = getThankYouCopy({
		isAuthenticated: true,
		displayName: "Анна",
		likes: 12,
		total: 20,
	});
	return (
		<JournalScreen title={copy.title} stat={copy.stat} caption={copy.caption} line={copy.line}>
			<section className="journal-panel">
				<p className="journal-section">Примерка</p>
				<p className="journal-line">{copy.fittingLine}</p>
				<PrivacyConsent className="privacy-consent--journal" />
				<button type="button" className="journal-btn journal-btn--primary">
					Заявка на примерку
				</button>
				<JournalContacts />
			</section>
			<button type="button" className="journal-btn journal-btn--quiet journal-home">
				На главную
			</button>
		</JournalScreen>
	);
}

export default function JournalPreview() {
	const [id, setId] = useState(SCREENS[0].id);
	const current = SCREENS.find((item) => item.id === id) || SCREENS[0];

	return (
		<div className="journal-preview">
			<div className="journal-preview__bar" role="tablist" aria-label="Примеры экранов">
				{SCREENS.map((item) => (
					<button
						key={item.id}
						type="button"
						role="tab"
						aria-selected={item.id === id}
						className={
							item.id === id
								? "journal-preview__chip is-active"
								: "journal-preview__chip"
						}
						onClick={() => setId(item.id)}
					>
						{item.label}
					</button>
				))}
			</div>
			{current.render()}
		</div>
	);
}
