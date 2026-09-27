import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
	createFittingRequest,
	getRememberedPhone,
	loginUser,
	registerUser,
	setRememberedPhone,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import {
	formatPhoneMask,
	formatPinMask,
	normalizePhoneRu,
	pinDigits,
} from "../utils/masks";
import PrivacyConsent from "../components/PrivacyConsent";
import JournalScreen, { JournalContacts } from "../components/JournalScreen";
import { getThankYouCopy } from "../content/thankYouCopy.js";
import "../components/JournalScreen.css";

export default function ThankYou() {
	const { state } = useLocation();
	const navigate = useNavigate();
	const { isAuthenticated, profile, loginWithToken, refreshProfile } = useAuth();

	const likes = state?.likes ?? 0;
	const total = state?.total ?? 0;
	const likedPhotoIds = Array.isArray(state?.likedPhotoIds)
		? state.likedPhotoIds
		: [];

	const [mode, setMode] = useState(() =>
		getRememberedPhone() ? "login" : "register",
	);
	const [name, setName] = useState("");
	const [phone, setPhone] = useState(() =>
		formatPhoneMask(getRememberedPhone()),
	);
	const [pin, setPin] = useState("");
	const [err, setErr] = useState("");
	const [saving, setSaving] = useState(false);
	const [justAuthed, setJustAuthed] = useState(null);
	const [fittingRequested, setFittingRequested] = useState(false);
	const [fittingBusy, setFittingBusy] = useState(false);

	const namePart = profile?.display_name?.trim();
	const copy = getThankYouCopy({
		isAuthenticated,
		displayName: namePart,
		likes,
		total,
	});

	function switchMode(next) {
		setMode(next);
		setErr("");
		setPin("");
	}

	async function onSubmit(e) {
		e.preventDefault();
		setErr("");
		const norm = normalizePhoneRu(phone);
		const p = pinDigits(pin);
		if (mode === "register") {
			const nm = name.trim();
			if (!nm) {
				setErr("Укажите имя");
				return;
			}
			if (!norm) {
				setErr("Укажите корректный номер телефона");
				return;
			}
			if (p.length !== 6) {
				setErr("PIN — 6 цифр (формат •••-•••)");
				return;
			}
		} else if (!norm || p.length < 4) {
			setErr("Укажите телефон и PIN");
			return;
		}
		setSaving(true);
		try {
			const data =
				mode === "register"
					? await registerUser({ displayName: name.trim(), phone: norm, pin: p })
					: await loginUser({ phone: norm, pin: p });
			setRememberedPhone(norm);
			loginWithToken(data.access_token, data.refresh_token);
			await refreshProfile();
			setJustAuthed(mode);
		} catch (ex) {
			const msg = ex.message || "";
			setErr(
				/invalid phone or pin/i.test(msg)
					? "Неверный телефон или PIN"
					: msg || (mode === "register" ? "Не удалось сохранить" : "Ошибка входа"),
			);
		} finally {
			setSaving(false);
		}
	}

	async function onFittingRequest() {
		setErr("");
		setFittingBusy(true);
		try {
			await createFittingRequest({ likes, total, photoIds: likedPhotoIds });
			setFittingRequested(true);
		} catch (ex) {
			setErr(ex.message || "Не удалось отправить заявку");
		} finally {
			setFittingBusy(false);
		}
	}

	const lead = justAuthed
		? justAuthed === "login"
			? "С возвращением."
			: "Профиль сохранён."
		: !isAuthenticated && mode === "login"
			? "Войдите — эта сессия сохранится в профиле."
			: copy.line;

	const showFitting = isAuthenticated && copy.hasLikes;
	const homeIsPrimary = isAuthenticated && (!showFitting || fittingRequested);

	return (
		<JournalScreen
			reserveMenu
			title={copy.title}
			stat={copy.stat}
			caption={copy.caption}
			line={lead}
		>
			{err ? <p className="journal-error">{err}</p> : null}

			{!isAuthenticated ? (
				<>
					<div className="journal-tabs" role="tablist" aria-label="Аккаунт">
						<button
							type="button"
							role="tab"
							aria-selected={mode === "login"}
							className={
								mode === "login" ? "journal-tab is-active" : "journal-tab"
							}
							onClick={() => switchMode("login")}
						>
							Войти
						</button>
						<button
							type="button"
							role="tab"
							aria-selected={mode === "register"}
							className={
								mode === "register" ? "journal-tab is-active" : "journal-tab"
							}
							onClick={() => switchMode("register")}
						>
							Регистрация
						</button>
					</div>
					<form className="journal-form" onSubmit={onSubmit}>
						{mode === "register" ? (
							<>
								<label className="journal-label" htmlFor="thank-name">
									Имя
								</label>
								<input
									id="thank-name"
									className="journal-input"
									value={name}
									onChange={(e) => setName(e.target.value)}
									autoComplete="name"
									placeholder="Как к вам обращаться"
									required
								/>
							</>
						) : null}
						<label className="journal-label" htmlFor="thank-phone">
							Телефон
						</label>
						<input
							id="thank-phone"
							className="journal-input"
							inputMode="tel"
							autoComplete="tel"
							placeholder="+7 (999) 123-45-67"
							value={phone}
							onChange={(e) => setPhone(formatPhoneMask(e.target.value))}
							required
						/>
						<label className="journal-label" htmlFor="thank-pin">
							PIN
						</label>
						{mode === "register" ? (
							<p className="journal-hint">
								6 цифр — код входа с любого устройства.
							</p>
						) : null}
						<input
							id="thank-pin"
							className="journal-input"
							inputMode="numeric"
							autoComplete={mode === "register" ? "new-password" : "current-password"}
							placeholder="•••-•••"
							value={pin}
							onChange={(e) => setPin(formatPinMask(e.target.value))}
							required
						/>
						<PrivacyConsent className="privacy-consent--journal" />
						{mode === "register" && err.includes("уже зарегистрирован") ? (
							<button
								type="button"
								className="journal-switch"
								onClick={() => switchMode("login")}
							>
								Войти с этим номером
							</button>
						) : null}
						<button
							type="submit"
							className="journal-btn journal-btn--primary"
							disabled={saving}
						>
							{saving
								? mode === "register"
									? "Сохраняем…"
									: "Вход…"
								: mode === "register"
									? "Сохранить профиль"
									: "Войти"}
						</button>
					</form>
				</>
			) : null}

			{showFitting ? (
				<section className="journal-panel">
					<p className="journal-section">Примерка</p>
					<p className="journal-line">{copy.fittingLine}</p>
					{fittingRequested ? (
						<p className="journal-success">Заявка принята. Скоро позвоним.</p>
					) : (
						<>
							<PrivacyConsent className="privacy-consent--journal" />
							<button
								type="button"
								className="journal-btn journal-btn--primary"
								disabled={fittingBusy}
								onClick={onFittingRequest}
							>
								{fittingBusy ? "Отправляем…" : "Заявка на примерку"}
							</button>
						</>
					)}
					<JournalContacts />
				</section>
			) : null}

			<button
				type="button"
				className={
					homeIsPrimary
						? "journal-btn journal-btn--primary journal-home"
						: "journal-btn journal-btn--quiet journal-home"
				}
				onClick={() => navigate("/")}
			>
				На главную
			</button>

			{isAuthenticated && !copy.hasLikes ? (
				<JournalContacts title="Нужна подборка от стилиста?" />
			) : null}
		</JournalScreen>
	);
}
