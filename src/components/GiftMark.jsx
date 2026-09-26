export default function GiftMark({ className }) {
	return (
		<span className={className} aria-hidden>
			<svg
				viewBox="0 0 24 24"
				width="13"
				height="13"
				fill="none"
				stroke="currentColor"
				strokeWidth="2.2"
				strokeLinecap="round"
				strokeLinejoin="round"
			>
				<rect x="3" y="8" width="18" height="12" rx="1.4" />
				<path d="M12 8v12" />
				<path d="M3 13h18" />
				<path d="M12 8C9.5 5.2 6.2 5.6 7 7.4 7.6 8.6 10 8.4 12 8" />
				<path d="M12 8C14.5 5.2 17.8 5.6 17 7.4 16.4 8.6 14 8.4 12 8" />
			</svg>
		</span>
	);
}
