import { useEffect, useState } from "react";
import { useAuth } from "../../context/AuthContext.jsx";
import {
	buildPushDiagnosticReport,
	fetchPushAccountStatus,
	getPushUnsupportedHint,
	isPushActiveOnDevice,
	isPushAvailableOnServer,
	isPushReadyFromProbe,
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
	const [probeBusy, setProbeBusy] = useState(false);
	const [diagText, setDiagText] = useState("");
	const [probeStatus, setProbeStatus] = useState("");
	const [copyHint, setCopyHint] = useState("");
	const pushReady = pushProbe ? isPushReadyFromProbe(pushProbe) : null;

	async function runPushProbe({ forceRetry = false } = {}) {
		setProbeBusy(true);
		setError("");
		setCopyHint("");
		setProbeStatus(
			forceRetry
				? "Сбрасываем service worker… подождите до 30 сек."
				: "Проверяем окружение…",
		);
		try {
			const { probe, text } = await buildPushDiagnosticReport({ forceRetry });
			setPushProbe(probe);
			setDiagText(text);
			if (!isPushReadyFromProbe(probe)) {
				setServerOk(false);
				setProbeStatus(
					forceRetry
						? `Готово. Push: ${probe.registrationReady ? "SW ok" : "SW нет"}.`
						: "Push пока недоступен — см. текст и диагностику ниже.",
				);
				return;
			}
			setProbeStatus("Окружение готово, проверяем сервер…");
			const ok = await isPushAvailableOnServer();
			setServerOk(ok);
			const onDevice = await isPushActiveOnDevice();
			setDeviceActive(onDevice);
			if (isAuthenticated) {
				const acc = await fetchPushAccountStatus();
				setAccountActive(Boolean(acc?.active));
				setAccountScope(acc?.gender_scope ?? null);
				if (acc?.gender_scope) setGenderScope(acc.gender_scope);
			}
			setProbeStatus(ok ? "Можно включать уведомления." : "Сервер push временно недоступен.");
		} catch (e) {
			setError(e.message || String(e));
			setProbeStatus("Ошибка проверки — см. сообщение выше.");
		} finally {
			setProbeBusy(false);
		}
	}

	async function copyDiagnostics() {
		if (!diagText) return;
		try {
			await navigator.clipboard.writeText(diagText);
			setCopyHint("Скопировано — вставьте в Telegram или Notes.");
		} catch {
			setCopyHint("Не удалось скопировать — выделите текст в блоке ниже вручную.");
		}
	}

	useEffect(() => {
		if (!open) return undefined;
		setServerOk(null);
		setDeviceActive(false);
		setAccountActive(false);
		setAccountScope(null);
		setPushProbe(null);
		setDiagText("");
		setProbeStatus("");
		setCopyHint("");
		void runPushProbe();
		// eslint-disable-next-line react-hooks/exhaustive-deps -- только открытие модалки
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
				{probeBusy && !pushProbe ? (
					<p className="hv2-notify-text">{probeStatus || "Проверяем push и service worker…"}</p>
				) : pushReady === false ? (
					<>
						<p className="hv2-notify-text">{getPushUnsupportedHint(pushProbe)}</p>
						{probeStatus ? (
							<p className="hv2-notify-text hv2-notify-text--status">{probeStatus}</p>
						) : null}
						{error ? <p className="hv2-notify-error">{error}</p> : null}
						<p className="hv2-notify-text hv2-notify-text--hint">
							Кнопка «Сбросить SW» работает только в приложении с иконки (не Safari). Ждите
							до 30 сек — статус обновится здесь.
						</p>
						<button
							type="button"
							className="hv2-notify-btn"
							disabled={probeBusy}
							onClick={() => runPushProbe({ forceRetry: true })}
						>
							{probeBusy ? "Сброс SW…" : "Сбросить service worker и проверить снова"}
						</button>
						{diagText ? (
							<>
								<button
									type="button"
									className="hv2-notify-btn hv2-notify-btn--secondary hv2-notify-btn--diag"
									onClick={copyDiagnostics}
								>
									Скопировать диагностику
								</button>
								{copyHint ? (
									<p className="hv2-notify-text hv2-notify-text--status">{copyHint}</p>
								) : null}
								<pre className="hv2-notify-diag" aria-label="Диагностика push">
									{diagText}
								</pre>
							</>
						) : null}
					</>
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
