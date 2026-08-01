import "./HomeBottomBar.css";

export default function HomeBottomBar({ onUserClick, onAboutClick, userInitial }) {
	return (
		<div className="hv2-bottom">
			<button
				type="button"
				className="hv2-bottom__user"
				onClick={onUserClick}
				aria-label="Аккаунт"
			>
				{userInitial ? (
					<span className="hv2-bottom__user-initial">{userInitial}</span>
				) : (
					<svg viewBox="0 0 24 24" className="hv2-bottom__user-icon" aria-hidden>
						<circle
							cx="12"
							cy="9"
							r="3.2"
							fill="none"
							stroke="currentColor"
							strokeWidth="1.3"
						/>
						<path
							d="M5.5 19.2c1.4-3 3.6-4.5 6.5-4.5s5.1 1.5 6.5 4.5"
							fill="none"
							stroke="currentColor"
							strokeWidth="1.3"
							strokeLinecap="round"
						/>
					</svg>
				)}
			</button>
			<button type="button" className="hv2-bottom__about" onClick={onAboutClick}>
				Об Антраша
			</button>
		</div>
	);
}
