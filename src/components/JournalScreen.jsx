const CONTACTS = [
	{ href: "tel:+74822453557", label: "Позвонить" },
	{
		href: "https://t.me/AntrashaBot",
		label: "Telegram",
		external: true,
	},
	{ href: "mailto:alexei@antrasha.ru", label: "Почта" },
];

export default function JournalScreen({
	kicker = "Antrasha",
	title,
	stat,
	caption,
	meta,
	line,
	reserveMenu = false,
	children,
}) {
	return (
		<div className={reserveMenu ? "journal-page journal-page--menu" : "journal-page"}>
			<article className="journal-card">
				<p className="journal-kicker">{kicker}</p>
				<h1 className="journal-title">{title}</h1>
				{stat ? (
					<p className="journal-stat">
						<span className="journal-stat__value">{stat}</span>
						{caption ? (
							<span className="journal-stat__cap">{caption}</span>
						) : null}
					</p>
				) : null}
				{meta ? <p className="journal-meta">{meta}</p> : null}
				{line ? <p className="journal-line">{line}</p> : null}
				{children}
			</article>
		</div>
	);
}

export function JournalActions({ actions, onAction }) {
	if (!actions?.length) return null;
	return (
		<div className="journal-stack">
			{actions.map((action) => (
				<button
					key={action.id}
					type="button"
					className={`journal-btn journal-btn--${action.tone}`}
					onClick={() => onAction(action.id)}
				>
					{action.label}
				</button>
			))}
		</div>
	);
}

export function JournalContacts({ title = "Или напишите сами" }) {
	return (
		<div className="journal-contacts">
			<p className="journal-section">{title}</p>
			<div className="journal-contacts__row">
				{CONTACTS.map((item) => (
					<a
						key={item.href}
						className="journal-contact"
						href={item.href}
						{...(item.external
							? { target: "_blank", rel: "noopener noreferrer" }
							: {})}
					>
						{item.label}
					</a>
				))}
			</div>
		</div>
	);
}
