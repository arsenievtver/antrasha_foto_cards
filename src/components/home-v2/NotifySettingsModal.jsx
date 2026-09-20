import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext.jsx";
import {
	fetchPushAccountStatus,
	getPushUnsupportedHint,
	isPushActiveOnDevice,
	isPushAvailableOnServer,
	isPushReadyFromProbe,
	preparePushServiceWorker,
	pushGenderScopeLabel,
	subscribeToNewPhotosPush,
	unsubscribeFromNewPhotosPush,
} from "../../push/notifications.js";
import "./NotifySettingsModal.css";

const GENDER_OPTIONS = [
	{ value: "male", label: "Мужские" },
	{ value: "female", label: "Женские" },
	{ value: "both", label: "Мужские и женские" },
];

export default function NotifySettingsModal({ open, onClose, onPushStateChange }) {
	const { isAuthenticated } = useAuth();
	const [genderScope, setGenderScope] = useState("both");
	const [busy, setBusy] = useState(false);
	const [error, setError] = useState("");
	const [serverOk, setServerOk] = useState(null);
	const [deviceActive, setDeviceActive] = useState(false);
	const [accountActive, setAccountActive] = useState(false);
	const [accountScope, setAccountScope] = useState(null);
	const [pushProbe, setPushProbe] = useState(null);
	const pushReady = pushProbe ? isPushReadyFromProbe(pushProbe) : null;

	useEffect(() => {
		if (!open) return undefined;
		let cancelled = false;
		setError("");
		setServerOk(null);
		setDeviceActive(false);
		setAccountActive(false);
		setAccountScope(null);
		setPushProbe(null);

		(async () => {
			try {
				const probe = await preparePushServiceWorker();
				if (cancelled) return;
				setPushProbe(probe);
				if (!isPushReadyFromProbe(probe)) {
					setServerOk(false);
					return;
				}
				const ok = await isPushAvailableOnServer();
				if (cancelled) return;
				setServerOk(ok);
				const onDevice = await isPushActiveOnDevice();
				if (cancelled) return;
				setDeviceActive(onDevice);
				if (isAuthenticated) {
					const acc = await fetchPushAccountStatus();
					if (cancelled) return;
					setAccountActive(Boolean(acc?.active));
					setAccountScope(acc?.gender_scope ?? null);
					if (acc?.gender_scope) setGenderScope(acc.gender_scope);
				}
			} catch (e) {
				if (!cancelled) setError(e.message || String(e));
			}
		})();

		return () => {
			cancelled = true;
		};
	}, [open, isAuthenticated]);

	if (!open) return null;

	const pushEnabled = deviceActive || accountActive;
	const scopeLabel = pushGenderScopeLabel(accountScope || genderScope);

	async function handleEnable() {
		setBusy(true);
		setError("");
		try {
			await subscribeToNewPhotosPush(genderScope);
			onPushStateChange?.(true);
			onClose?.();
		} catch (e) {
			setError(e.message || "Не удалось включить уведомления");
		} finally {
			setBusy(false);
		}
	}

	async function handleDisable() {
		setBusy(true);
		setError("");
		try {
			await unsubscribeFromNewPhotosPush();
			onPushStateChange?.(false);
			onClose?.();
		} catch (e) {
			setError(e.message || "Не удалось отключить уведомления");
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
				{pushReady === null ? (
					<p className="hv2-notify-text">Проверяем push и service worker…</p>
				) : pushReady === false ? (
					<p className="hv2-notify-text">{getPushUnsupportedHint(pushProbe)}</p>
				) : serverOk === false ? (
					<p className="hv2-notify-text">Уведомления временно недоступны.</p>
				) : pushEnabled ? (
					<>
						<p className="hv2-notify-text hv2-notify-text--status">
							Уведомления о новинках <strong>включены</strong>
							{scopeLabel ? ` (${scopeLabel})` : ""}.
						</p>
						<p className="hv2-notify-text">
							Можно отключить в любой момент — на этом устройстве push перестанут
							приходить.
						</p>
						{error ? <p className="hv2-notify-error">{error}</p> : null}
						<button
							type="button"
							className="hv2-notify-btn hv2-notify-btn--secondary"
							onClick={handleDisable}
							disabled={busy}
						>
							{busy ? "Отключаем…" : "Отключить уведомления"}
						</button>
					</>
				) : (
					<>
						<p className="hv2-notify-text">
							Сообщим о новых образах — около одного раза в неделю.
							{isAuthenticated
								? " После входа подписка привязывается к профилю."
								: null}
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
