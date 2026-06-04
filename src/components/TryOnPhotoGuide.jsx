import exampleGuide from "../assets/image/example.png";
import "./TryOnPhotoGuide.css";

export const TRYON_PHOTO_GUIDE_DISMISS_KEY = "tryon_photo_guide_dismissed";

export function isPhotoGuideDismissed() {
	try {
		return localStorage.getItem(TRYON_PHOTO_GUIDE_DISMISS_KEY) === "1";
	} catch {
		return false;
	}
}

export function dismissPhotoGuideForever() {
	try {
		localStorage.setItem(TRYON_PHOTO_GUIDE_DISMISS_KEY, "1");
	} catch {
		/* private mode */
	}
}

/**
 * @param {{ open: boolean, onClose: () => void, onDismissForever: () => void }} props
 */
export default function TryOnPhotoGuide({ open, onClose, onDismissForever }) {
	if (!open) return null;

	return (
		<div
			className="tryon-guide-backdrop"
			role="presentation"
			onClick={onClose}
		>
			<div
				className="tryon-guide-dialog"
				role="dialog"
				aria-labelledby="tryon-guide-title"
				aria-modal="true"
				onClick={(e) => e.stopPropagation()}
			>
				<h3 id="tryon-guide-title" className="tryon-guide-dialog__title">
					Какое фото нужно
				</h3>
				<p className="tryon-guide-dialog__lead">
					Слева направо: ваш снимок → образ из каталога → как может выглядеть
					результат.
				</p>
				<figure className="tryon-guide-figure">
					<img
						src={exampleGuide}
						alt="Пример: ваше фото, образ с моделью и результат примерки"
						className="tryon-guide-figure__img"
					/>
					<figcaption className="tryon-guide-figure__labels">
						<span>Ваше фото</span>
						<span>Образ</span>
						<span>Результат</span>
					</figcaption>
				</figure>
				<ul className="tryon-guide-list">
					<li>В полный рост или по пояс — видны лицо, плечи и торс.</li>
					<li>Один человек в кадре, без сильного наклона.</li>
					<li>Не поворачивайте снимок в галерее — загрузите как есть.</li>
				</ul>
				<div className="tryon-guide-dialog__actions">
					<button
						type="button"
						className="tryon-guide-btn tryon-guide-btn--primary"
						onClick={onClose}
					>
						Понял
					</button>
					<button
						type="button"
						className="tryon-guide-btn tryon-guide-btn--ghost"
						onClick={onDismissForever}
					>
						Понял, больше не напоминать
					</button>
				</div>
			</div>
		</div>
	);
}
