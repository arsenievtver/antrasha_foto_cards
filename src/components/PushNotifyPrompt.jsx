import { useEffect, useState } from "react";
import {
	isPushAvailableOnServer,
	isPushPromptDismissed,
	isPushSubscribedLocally,
	isPushSupported,
	markPushPromptDismissed,
	subscribeToNewPhotosPush,
} from "../push/notifications.js";
import "./PushNotifyPrompt.css";

const GENDER_OPTIONS = [
	{ value: "male", label: "Мужские" },
	{ value: "female", label: "Женские" },
	{ value: "both", label: "Мужские и женские" },
];

function defaultScopeFromGender(gender) {
	return gender === "male" || gender === "female" ? gender : "both";
}

export default function PushNotifyPrompt({ visible, gender }) {
	const [show, setShow] = useState(false);
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState(null);
	const [genderScope, setGenderScope] = useState(() => defaultScopeFromGender(gender));

	useEffect(() => {
		setGenderScope(defaultScopeFromGender(gender));
	}, [gender]);

	useEffect(() => {
		let cancelled = false;
		if (!visible || !isPushSupported()) {
			setShow(false);
			return undefined;
		}
		if (isPushSubscribedLocally() || isPushPromptDismissed()) {
			setShow(false);
			return undefined;
		}
		if (Notification.permission === "granted" && isPushSubscribedLocally()) {
			setShow(false);
			return undefined;
		}

		isPushAvailableOnServer().then((ok) => {
			if (!cancelled && ok) setShow(true);
		});
		return () => {
			cancelled = true;
		};
	}, [visible]);

	if (!show) return null;

	async function handleEnable() {
		setBusy(true);
		setError(null);
		try {
			await subscribeToNewPhotosPush(genderScope);
			setShow(false);
		} catch (e) {
			setError(e.message || "Не удалось включить уведомления");
		} finally {
			setBusy(false);
		}
	}

	function handleDismiss() {
		markPushPromptDismissed();
		setShow(false);
	}

	return (
		<div className="push-prompt" role="region" aria-label="Уведомления о новинках">
			<div className="push-prompt-inner">
				<p className="push-prompt-text">
					Сообщим о новых образах — не чаще одного раза в день. Что интересует?
				</p>
				<div
					className="push-prompt-genders"
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
									? "push-prompt-gender push-prompt-gender--active"
									: "push-prompt-gender"
							}
							onClick={() => setGenderScope(opt.value)}
							disabled={busy}
						>
							{opt.label}
						</button>
					))}
				</div>
				{error ? (
					<p className="push-prompt-error" role="alert">
						{error}
					</p>
				) : null}
				<div className="push-prompt-actions">
					<button
						type="button"
						className="push-prompt-btn push-prompt-btn--primary"
						onClick={handleEnable}
						disabled={busy}
					>
						{busy ? "Подключаем…" : "Включить уведомления"}
					</button>
					<button
						type="button"
						className="push-prompt-btn push-prompt-btn--ghost"
						onClick={handleDismiss}
						disabled={busy}
					>
						Не сейчас
					</button>
				</div>
			</div>
		</div>
	);
}
