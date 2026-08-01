import { useEffect, useState } from "react";
import {
	isPushAvailableOnServer,
	isPushSubscribedLocally,
	isPushSupported,
	subscribeToNewPhotosPush,
} from "../../push/notifications.js";
import "./NotifySettingsModal.css";

const GENDER_OPTIONS = [
	{ value: "male", label: "Мужские" },
	{ value: "female", label: "Женские" },
	{ value: "both", label: "Мужские и женские" },
];

export default function NotifySettingsModal({ open, onClose }) {
	const [genderScope, setGenderScope] = useState("both");
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");
	const [serverOk, setServerOk] = useState(null);
	const subscribed = isPushSubscribedLocally();

	useEffect(() => {
		if (!open) return undefined;
		let cancelled = false;
		setError("");
		if (!isPushSupported()) {
			setServerOk(false);
			return undefined;
		}
		isPushAvailableOnServer().then((ok) => {
			if (!cancelled) setServerOk(ok);
		});
		return () => {
			cancelled = true;
		};
	}, [open]);

	if (!open) return null;

	async function handleEnable() {
		setBusy(true);
		setError("");
		try {
			await subscribeToNewPhotosPush(genderScope);
			onClose?.();
		} catch (e) {
			setError(e.message || "Не удалось включить уведомления");
		} finally {
			setBusy(false);
		}
	}

	return (
		<div className="hv2-notify-backdrop" role="presentation" onClick={onClose}>
			<div
				className="hv2-notify-modal"
				role="dialog"
				aria-modal
				aria-labelledby="hv2-notify-title"
				onClick={(ev) => ev.stopPropagation()}
			>
				<button
					type="button"
					className="hv2-notify-close"
					onClick={onClose}
					aria-label="Закрыть"
				>
					×
				</button>
				<h2 id="hv2-notify-title" className="hv2-notify-title">
					Уведомления
				</h2>
				{!isPushSupported() ? (
					<p className="hv2-notify-text">
						Ваш браузер не поддерживает push-уведомления.
					</p>
				) : serverOk === false ? (
					<p className="hv2-notify-text">Уведомления временно недоступны.</p>
				) : subscribed ? (
					<p className="hv2-notify-text">
						Уведомления о новинках уже включены на этом устройстве.
					</p>
				) : (
					<>
						<p className="hv2-notify-text">
							Сообщим о новых образах — не чаще одного раза в день.
						</p>
						<div
							className="hv2-notify-genders"
							role="radiogroup"
							aria-label="Категория новинок"
						>
							{GENDER_OPTIONS.map((opt) => (
								<button
									key={opt.value}
									type="button"
									role="radio"
									aria-checked={genderScope === opt.value}
									className={
										genderScope === opt.value
											? "hv2-notify-gender hv2-notify-gender--active"
											: "hv2-notify-gender"
									}
									onClick={() => setGenderScope(opt.value)}
									disabled={busy}
								>
									{opt.label}
								</button>
							))}
						</div>
						{error ? <p className="hv2-notify-error">{error}</p> : null}
						<button
							type="button"
							className="hv2-notify-btn"
							onClick={handleEnable}
							disabled={busy || serverOk === null}
						>
							{busy ? "Подключаем…" : "Включить уведомления"}
						</button>
					</>
				)}
			</div>
		</div>
	);
}
