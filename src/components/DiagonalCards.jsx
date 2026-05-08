import React, { useId } from "react";

export function MaleShape({ onClick, className = "", image }) {
	const clipId = useId();

	const pathD =
		"M4 7C4 3.13401 7.13401 0 11 0L96.9999 0C100.866 0 104 3.13401 104 7V26.0503C104 29.3142 101.744 32.1449 98.5627 32.8736L12.5628 52.5704C8.17942 53.5743 4 50.2439 4 45.747V7Z";

	return (
		<svg viewBox="0 0 108 55" className={className}>
			<defs>
				<clipPath id={clipId}>
					<path d={pathD} />
				</clipPath>
			</defs>

			{/* 1️⃣ Цветной фон (как было) */}
			<path d={pathD} fill="currentColor" />

			{/* 2️⃣ Картинка поверх цвета, но обрезанная */}
			{image && (
				<image
					href={image}
					width="108"
					preserveAspectRatio="xMidYMid slice"
					clipPath={`url(#${clipId})`}
				/>
			)}

			{/* 3️⃣ Отдельный прозрачный слой для клика */}
			<path
				d={pathD}
				fill="transparent"
				onClick={onClick}
				style={{ pointerEvents: "visiblePainted", cursor: "pointer" }}
			/>
		</svg>
	);
}


export function FemaleShape({ onClick, className = "", image }) {
	const clipId = useId();

	const pathD =
		"M104 89.1602C104 93.3954 100.866 96.8287 97 96.8287H11.0001C7.13414 96.8287 4.00014 93.3954 4.00014 89.1602V71.2847C4.00014 67.6569 6.32068 64.5255 9.56152 63.7799L95.5614 43.9952C99.9113 42.9945 104 46.6308 104 51.5V89.1602Z";

	return (
		<svg viewBox="0 0 108 53" className={className}>
			<defs>
				<clipPath id={clipId}>
					{/* смещаем форму вверх на 44 */}
					<path d={pathD} transform="translate(0 -44)" />
				</clipPath>
			</defs>

			{/* Цветной фон */}
			<path
				d={pathD}
				transform="translate(0 -44)"
				fill="currentColor"
			/>

			{/* Картинка, прибитая к правому нижнему углу */}
			{image && (
				<image
					href={image}
					width="108"
					height="55"
					preserveAspectRatio="xMaxYMax slice"
					clipPath={`url(#${clipId})`}
				/>
			)}

			{/* Клик слой */}
			<path
				d={pathD}
				transform="translate(0 -44)"
				fill="transparent"
				onClick={onClick}
				style={{ pointerEvents: "visiblePainted", cursor: "pointer" }}
			/>
		</svg>
	);
}