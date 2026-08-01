import { useEffect, useRef, useState } from "react";
import {
	isIosDevice,
	isPwaInstallDismissed,
	isPwaStandalone,
	markPwaInstallDismissed,
} from "../../utils/pwa.js";
import "./PwaInstallPrompt.css";

function IconShare({ className }) {
	return (
		<svg className={className} viewBox="0 0 24 24" aria-hidden>
			<path
				fill="none"
				stroke="currentColor"
				strokeWidth="1.6"
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M12 3v11M8.5 6.5 12 3l3.5 3.5"
			/>
			<path
				fill="none"
				stroke="currentColor"
				strokeWidth="1.6"
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M5 12.5V18a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5.5"
			/>
		</svg>
	);
}

function IconAddHome({ className }) {
	return (
		<svg className={className} viewBox="0 0 24 24" aria-hidden>
			<rect
				x="4"
				y="4"
				width="16"
				height="16"
				rx="3.5"
				fill="none"
				stroke="currentColor"
				strokeWidth="1.6"
			/>
			<path
				fill="none"
				stroke="currentColor"
				strokeWidth="1.6"
				strokeLinecap="round"
				d="M12 8.5v7M8.5 12h7"
			/>
		</svg>
	);
}

function IconHome({ className }) {
	return (
		<svg className={className} viewBox="0 0 24 24" aria-hidden>
			<path
				fill="none"
				stroke="currentColor"
				strokeWidth="1.6"
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M4.5 11.5 12 5l7.5 6.5"
			/>
			<path
				fill="none"
				stroke="currentColor"
				strokeWidth="1.6"
				strokeLinecap="round"
				strokeLinejoin="round"
				d="M7 10.8V19h10v-8.2"
			/>
		</svg>
	);
}

function IconMenu({ className }) {
	return (
		<svg className={className} viewBox="0 0 24 24" aria-hidden>
			<circle cx="12" cy="6" r="1.35" fill="currentColor" />
			<circle cx="12" cy="12" r="1.35" fill="currentColor" />
			<circle cx="12" cy="18" r="1.35" fill="currentColor" />
		</svg>
	);
}

function tryOpenInstalledPwa() {
	const url = `${window.location.origin}/`;
	try {
		const w = window.open(url, "_blank");
		if (w) return true;
	} catch {
		/* ignore */
	}
	return false;
}

/**
 * Предложение установить PWA на главной (не в standalone).
 * Android/Chrome — native install; iOS — только инструкция с иконками.
 */
export default function PwaInstallPrompt({ onInstalled }) {
	const ios = isIosDevice();
	const [visible, setVisible] = useState(false);
	const [deferred, setDeferred] = useState(null);
	const [busy, setBusy] = useState(false);
	/** Android: после успешной установки */
	const [installed, setInstalled] = useState(false);
	const installedOnce = useRef(false);

	function finishInstalled() {
		if (installedOnce.current) return;
		installedOnce.current = true;
		markPwaInstallDismissed({ permanent: true });
		setDeferred(null);
		setBusy(false);
		setInstalled(true);
		setVisible(true);
		/* WebAPK на Android собирается несколько секунд — пробуем открыть */
		window.setTimeout(() => {
			tryOpenInstalledPwa();
		}, 900);
		onInstalled?.();
	}

	useEffect(() => {
		if (isPwaStandalone() || isPwaInstallDismissed()) return undefined;

		let showTimer;
		let bipShown = false;

		const onBeforeInstall = (e) => {
			e.preventDefault();
			setDeferred(e);
			bipShown = true;
			clearTimeout(showTimer);
			showTimer = setTimeout(() => setVisible(true), 900);
		};

		const onAppInstalled = () => finishInstalled();

		window.addEventListener("beforeinstallprompt", onBeforeInstall);
		window.addEventListener("appinstalled", onAppInstalled);

		showTimer = setTimeout(() => {
			if (bipShown || isPwaStandalone() || isPwaInstallDismissed()) return;
			setVisible(true);
		}, ios ? 1400 : 4500);

		return () => {
			clearTimeout(showTimer);
			window.removeEventListener("beforeinstallprompt", onBeforeInstall);
			window.removeEventListener("appinstalled", onAppInstalled);
		};
		// finishInstalled закрыт через ref; onInstalled стабилен из HomeV2
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [ios, onInstalled]);

	if (!visible) return null;

	async function handleAndroidInstall() {
		if (!deferred) return;
		setBusy(true);
		try {
			deferred.prompt();
			const choice = await deferred.userChoice;
			setDeferred(null);
			if (choice?.outcome === "accepted") {
				finishInstalled();
			} else {
				markPwaInstallDismissed();
				setVisible(false);
			}
		} catch {
			markPwaInstallDismissed();
			setVisible(false);
		} finally {
			setBusy(false);
		}
	}

	function handleDismiss() {
		markPwaInstallDismissed();
		setVisible(false);
	}

	function handleOpenPwa() {
		tryOpenInstalledPwa();
		markPwaInstallDismissed({ permanent: true });
		setVisible(false);
	}

	/* —— после установки на Android —— */
	if (installed && !ios) {
		return (
			<div className="hv2-pwa" role="region" aria-label="Приложение установлено">
				<div className="hv2-pwa__inner">
					<p className="hv2-pwa__title">Готово</p>
					<p className="hv2-pwa__text">
						ANTRASHA на экране. Откройте приложение — так удобнее получать
						уведомления о новинках.
					</p>
					<div className="hv2-pwa__actions">
						<button
							type="button"
							className="hv2-pwa__btn hv2-pwa__btn--primary"
							onClick={handleOpenPwa}
						>
							Открыть приложение
						</button>
						<button
							type="button"
							className="hv2-pwa__btn hv2-pwa__btn--ghost"
							onClick={handleDismiss}
						>
							Позже
						</button>
					</div>
				</div>
			</div>
		);
	}

	/* —— iPhone / iPad: только инструкция —— */
	if (ios) {
		return (
			<div className="hv2-pwa" role="region" aria-label="Добавить на экран Домой">
				<div className="hv2-pwa__inner">
					<p className="hv2-pwa__title">Добавьте на экран «Домой»</p>
					<p className="hv2-pwa__text">
						На iPhone приложение ставится через Safari — займёт минуту, зато
						уведомления о новинках будут под рукой.
					</p>
					<ol className="hv2-pwa__steps hv2-pwa__steps--icons">
						<li>
							<span className="hv2-pwa__step-icon" aria-hidden>
								<IconShare className="hv2-pwa__glyph" />
							</span>
							<span>
								Внизу Safari нажмите{" "}
								<strong>«Поделиться»</strong>
							</span>
						</li>
						<li>
							<span className="hv2-pwa__step-icon" aria-hidden>
								<IconAddHome className="hv2-pwa__glyph" />
							</span>
							<span>
								Пролистайте и выберите{" "}
								<strong>«На экран „Домой“»</strong>
							</span>
						</li>
						<li>
							<span className="hv2-pwa__step-icon" aria-hidden>
								<IconHome className="hv2-pwa__glyph" />
							</span>
							<span>
								Откройте ярлык <strong>ANTRASHA</strong> и включите
								уведомления в колокольчике
							</span>
						</li>
					</ol>
					<div className="hv2-pwa__actions">
						<button
							type="button"
							className="hv2-pwa__btn hv2-pwa__btn--primary"
							onClick={handleDismiss}
						>
							Понятно
						</button>
						<button
							type="button"
							className="hv2-pwa__btn hv2-pwa__btn--ghost"
							onClick={handleDismiss}
						>
							Не сейчас
						</button>
					</div>
				</div>
			</div>
		);
	}

	/* —— Android / Chrome: native install —— */
	const canNativeInstall = Boolean(deferred);

	return (
		<div className="hv2-pwa" role="region" aria-label="Установка приложения">
			<div className="hv2-pwa__inner">
				<p className="hv2-pwa__title">
					{canNativeInstall ? "Установить приложение?" : "Установите ANTRASHA"}
				</p>
				<p className="hv2-pwa__text">
					{canNativeInstall
						? "Ярлык на экране — быстрее открывать и получать уведомления о новинках."
						: "Добавьте ярлык на экран через меню браузера — так удобнее следить за новинками."}
				</p>

				{!canNativeInstall ? (
					<ol className="hv2-pwa__steps hv2-pwa__steps--icons">
						<li>
							<span className="hv2-pwa__step-icon" aria-hidden>
								<IconMenu className="hv2-pwa__glyph" />
							</span>
							<span>
								Откройте меню браузера <strong>⋮</strong>
							</span>
						</li>
						<li>
							<span className="hv2-pwa__step-icon" aria-hidden>
								<IconAddHome className="hv2-pwa__glyph" />
							</span>
							<span>
								Выберите <strong>«Установить приложение»</strong> или «На
								главный экран»
							</span>
						</li>
						<li>
							<span className="hv2-pwa__step-icon" aria-hidden>
								<IconHome className="hv2-pwa__glyph" />
							</span>
							<span>
								Откройте ярлык и включите уведомления в колокольчике
							</span>
						</li>
					</ol>
				) : null}

				<div className="hv2-pwa__actions">
					{canNativeInstall ? (
						<button
							type="button"
							className="hv2-pwa__btn hv2-pwa__btn--primary"
							onClick={handleAndroidInstall}
							disabled={busy}
						>
							{busy ? "Устанавливаем…" : "Установить"}
						</button>
					) : (
						<button
							type="button"
							className="hv2-pwa__btn hv2-pwa__btn--primary"
							onClick={handleDismiss}
						>
							Понятно
						</button>
					)}
					<button
						type="button"
						className="hv2-pwa__btn hv2-pwa__btn--ghost"
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
