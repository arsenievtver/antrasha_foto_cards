import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
	formatPhoneMask,
	formatPinMask,
	normalizePhoneRu,
	pinDigits,
} from "../utils/masks";
import {
	getRememberedPhone,
	loginUser,
	registerUser,
	setRememberedPhone,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import { isPushPermissionMissing } from "../push/notifications.js";
import NotifySettingsPanel from "./home-v2/NotifySettingsModal.jsx";
import PrivacyConsent from "./PrivacyConsent";
import GiftMark from "./GiftMark";
import "./UserMenu.css";

export default function UserMenu({
	hideTrigger = false,
	open: controlledOpen,
	onOpenChange,
	onPushPermissionChange,
} = {}) {
	const {
		profile,
		loading,
		token,
		logout,
		loginWithToken,
		refreshProfile,
	} = useAuth();
	const [internalOpen, setInternalOpen] = useState(false);
	const isControlled = controlledOpen !== undefined;
	const open = isControlled ? controlledOpen : internalOpen;
	const setOpen = (next) => {
		if (!isControlled) setInternalOpen(next);
		onOpenChange?.(next);
	};
	const [phone, setPhone] = useState(() =>
		formatPhoneMask(getRememberedPhone()),
	);
	const [pin, setPin] = useState("");
	const [name, setName] = useState("");
	const [mode, setMode] = useState(() =>
		getRememberedPhone() ? "login" : "register",
	);
	const [loginErr, setLoginErr] = useState("");
	const [loginBusy, setLoginBusy] = useState(false);
	const [pushMissing, setPushMissing] = useState(isPushPermissionMissing);
	const navigate = useNavigate();

	function certificateHref(url) {
		const host = window.location.hostname;
		if (host !== "localhost" && host !== "127.0.0.1") return url;
		try {
			const parsed = new URL(url);
			return `http://localhost:5177${parsed.pathname}${parsed.search}`;
		} catch {
			return url;
		}
	}

	const showInitial =
		profile?.display_name?.trim()?.[0] ||
		profile?.phone?.replace(/\D/g, "")?.slice(-1) ||
		"?";

	function formatCertAmount(value) {
		const n = Number(value);
		if (!Number.isFinite(n) || n <= 0) return "";
		return (
			new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(
				Math.round(n),
			) + " ₽"
		);
	}

	useEffect(() => {
		if (open && token) refreshProfile();
	}, [open, token, refreshProfile]);

	useEffect(() => {
		setPushMissing(isPushPermissionMissing());
	}, [open]);

	function handlePushPermission(granted) {
		setPushMissing(!granted);
		onPushPermissionChange?.(granted);
	}

	useEffect(() => {
		if (open && !profile) {
			const saved = getRememberedPhone();
			if (saved) setPhone(formatPhoneMask(saved));
			setMode(saved ? "login" : "register");
		}
	}, [open, profile]);

	function close() {
		setOpen(false);
		setLoginErr("");
		setPin("");
		setName("");
		if (!profile) setPhone(formatPhoneMask(getRememberedPhone()));
	}

	function switchMode(next) {
		setMode(next);
		setLoginErr("");
		setPin("");
	}

	function authErrorText(err, fallback) {
		const msg = err?.message || "";
		if (/invalid phone or pin/i.test(msg)) return "Неверный телефон или PIN";
		return msg || fallback;
	}

	function resetPhoneField() {
		setPhone(formatPhoneMask(getRememberedPhone()));
	}

	async function onSubmit(e) {
		e.preventDefault();
		setLoginErr("");
		const norm = normalizePhoneRu(phone);
		const p = pinDigits(pin);
		if (mode === "register") {
			const nm = name.trim();
			if (!nm) {
				setLoginErr("Укажите имя");
				return;
			}
			if (!norm) {
				setLoginErr("Укажите корректный номер телефона");
				return;
			}
			if (p.length !== 6) {
				setLoginErr("PIN — 6 цифр (формат •••-•••)");
				return;
			}
		} else if (!norm || p.length < 4) {
			setLoginErr("Укажите телефон и PIN");
			return;
		}
		setLoginBusy(true);
		try {
			const data =
				mode === "register"
					? await registerUser({ displayName: name.trim(), phone: norm, pin: p })
					: await loginUser({ phone: norm, pin: p });
			setRememberedPhone(norm);
			loginWithToken(data.access_token, data.refresh_token);
			await refreshProfile();
			close();
		} catch (err) {
			setLoginErr(
				authErrorText(
					err,
					mode === "register" ? "Не удалось зарегистрироваться" : "Ошибка входа",
				),
			);
		} finally {
			setLoginBusy(false);
		}
	}

	return (
		<>
			{hideTrigger ? null : (
				<button
					type="button"
					className="user-menu-trigger"
					onClick={() => setOpen(true)}
					aria-label={
						(profile?.gift_certificates || []).length
							? "Меню пользователя, есть подарочный сертификат"
							: "Меню пользователя"
					}
				>
					<span
						className={
							profile ? "user-menu-avatar user-menu-avatar--named" : "user-menu-avatar"
						}
					>
						{showInitial}
						{profile && pushMissing ? (
							<span className="user-menu-avatar__dot" aria-hidden />
						) : null}
						{(profile?.gift_certificates || []).length > 0 ? (
							<GiftMark className="user-menu-avatar__gift" />
						) : null}
					</span>
				</button>
			)}

			{open && (
				<div
					className="user-menu-backdrop"
					role="presentation"
					onClick={close}
				>
					<div
						className="user-menu-modal"
						role="dialog"
						aria-modal
						onClick={(ev) => ev.stopPropagation()}
					>
						<button
							type="button"
							className="user-menu-close"
							onClick={close}
							aria-label="Закрыть"
						>
							×
						</button>

						{token && loading && !profile ? (
							<p className="user-menu-meta">Загрузка…</p>
						) : token && !profile ? (
							<>
								<p className="user-menu-kicker">Кабинет</p>
								<h3 className="user-menu-title">Профиль</h3>
								<p className="user-menu-meta">
									Не удалось загрузить данные. Проверьте сеть.
								</p>
								<button
									type="button"
									className="user-menu-submit"
									onClick={() => refreshProfile()}
								>
									Повторить
								</button>
								<button
									type="button"
									className="user-menu-logout"
									onClick={() => {
										logout();
										resetPhoneField();
									}}
								>
									Выйти
								</button>
							</>
						) : profile ? (
							<>
								<p className="user-menu-kicker">Кабинет</p>
								<h3 className="user-menu-title">
									{profile.display_name?.trim() || "Профиль"}
								</h3>
								<p className="user-menu-phone">
									{formatPhoneMask(profile.phone) || profile.phone}
								</p>
								{(profile.gift_certificates || []).length > 0 ? (
									<section
										className="user-menu-certs"
										aria-label="Сертификаты"
									>
										<p className="user-menu-section">Сертификаты</p>
										{(profile.gift_certificates || []).map((cert) => {
											const amount = formatCertAmount(cert.amount);
											const from = cert.giver_name?.trim();
											return (
												<a
													key={cert.url || cert.code}
													className="user-menu-cert"
													href={certificateHref(cert.url)}
													target="_blank"
													rel="noreferrer"
												>
													<span className="user-menu-cert__foil" aria-hidden />
													<span className="user-menu-cert__kicker">
														Подарочный сертификат
													</span>
													<span className="user-menu-cert__value">
														{amount || "Вам доступен"}
													</span>
													<span className="user-menu-cert__meta">
														{from ? `Дарит ${from}` : cert.code}
													</span>
													<span className="user-menu-cert__open">Открыть</span>
												</a>
											);
										})}
									</section>
								) : null}
								{profile.ranking_eval_enabled ? (
									<button
										type="button"
										className="user-menu-row"
										onClick={() => {
											close();
											navigate("/eval/ranking");
										}}
									>
										<span>Оценить подборку</span>
										<span aria-hidden>→</span>
									</button>
								) : null}
								<button
									type="button"
									className="user-menu-logout"
									onClick={() => {
										logout();
										close();
									}}
								>
									Выйти
								</button>
							</>
						) : (
							<>
								<p className="user-menu-kicker">Аккаунт</p>
								<div className="user-menu-tabs" role="tablist" aria-label="Аккаунт">
									<button
										type="button"
										role="tab"
										aria-selected={mode === "login"}
										className={
											mode === "login"
												? "user-menu-tab is-active"
												: "user-menu-tab"
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
											mode === "register"
												? "user-menu-tab is-active"
												: "user-menu-tab"
										}
										onClick={() => switchMode("register")}
									>
										Регистрация
									</button>
								</div>
								<p className="user-menu-meta">
									{mode === "register"
										? "Имя и телефон — чтобы узнавать вас и присылать новинки лично."
										: "Телефон и PIN, который вы задавали при регистрации."}
								</p>
								<form className="user-menu-form" onSubmit={onSubmit}>
									{mode === "register" ? (
										<>
											<label className="user-menu-label">Имя</label>
											<input
												className="user-menu-input"
												autoComplete="name"
												placeholder="Как к вам обращаться"
												value={name}
												onChange={(e) => setName(e.target.value)}
											/>
										</>
									) : null}
									<label className="user-menu-label">Телефон</label>
									<input
										className="user-menu-input"
										inputMode="tel"
										autoComplete="tel"
										placeholder="+7 (999) 123-45-67"
										value={phone}
										onChange={(e) =>
											setPhone(formatPhoneMask(e.target.value))
										}
									/>
									<label className="user-menu-label">
										{mode === "register" ? "PIN — 6 цифр" : "PIN"}
									</label>
									{mode === "register" ? (
										<p className="user-menu-hint">
											Придумайте код для входа с этого и другого устройства.
										</p>
									) : null}
									<input
										className="user-menu-input"
										inputMode="numeric"
										autoComplete={
											mode === "register" ? "new-password" : "current-password"
										}
										placeholder="•••-•••"
										value={pin}
										onChange={(e) =>
											setPin(formatPinMask(e.target.value))
										}
									/>
									{loginErr ? (
										<p className="user-menu-error">{loginErr}</p>
									) : null}
									{mode === "register" &&
									loginErr.includes("уже зарегистрирован") ? (
										<button
											type="button"
											className="user-menu-switch"
											onClick={() => switchMode("login")}
										>
											Войти с этим номером
										</button>
									) : null}
									<PrivacyConsent className="privacy-consent--left" />
									<button
										type="submit"
										className="user-menu-submit"
										disabled={loginBusy}
									>
										{loginBusy
											? mode === "register"
												? "Регистрация…"
												: "Вход…"
											: mode === "register"
												? "Зарегистрироваться"
												: "Войти"}
									</button>
								</form>
							</>
						)}
						<NotifySettingsPanel
							active={open}
							onPushStateChange={handlePushPermission}
						/>
					</div>
				</div>
			)}
		</>
	);
}
