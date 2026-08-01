import { useEffect, useState } from "react";
import {
	formatPhoneMask,
	formatPinMask,
	normalizePhoneRu,
	pinDigits,
} from "../utils/masks";
import {
	getRememberedPhone,
	loginUser,
	setRememberedPhone,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import PrivacyConsent from "./PrivacyConsent";
import "./UserMenu.css";

export default function UserMenu({
	hideTrigger = false,
	open: controlledOpen,
	onOpenChange,
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
	const [phone, setPhone] = useState(() => getRememberedPhone());
	const [pin, setPin] = useState("");
	const [loginErr, setLoginErr] = useState("");
	const [loginBusy, setLoginBusy] = useState(false);

	const showInitial =
		profile?.display_name?.trim()?.[0] ||
		profile?.phone?.replace(/\D/g, "")?.slice(-1) ||
		"?";

	useEffect(() => {
		if (open && !profile) {
			const saved = getRememberedPhone();
			if (saved) setPhone(saved);
		}
	}, [open, profile]);

	function close() {
		setOpen(false);
		setLoginErr("");
		setPin("");
		if (!profile) setPhone(getRememberedPhone());
	}

	function resetPhoneField() {
		setPhone(getRememberedPhone());
	}

	async function onLogin(e) {
		e.preventDefault();
		setLoginErr("");
		const norm = normalizePhoneRu(phone);
		const p = pinDigits(pin);
		if (!norm || p.length < 4) {
			setLoginErr("Укажите телефон и PIN");
			return;
		}
		setLoginBusy(true);
		try {
			const data = await loginUser({ phone: norm, pin: p });
			setRememberedPhone(norm);
			loginWithToken(data.access_token, data.refresh_token);
			await refreshProfile();
			close();
		} catch (err) {
			setLoginErr(err.message || "Ошибка входа");
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
					aria-label="Меню пользователя"
				>
					<span className="user-menu-avatar">{showInitial}</span>
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
							<p className="user-menu-meta" style={{ marginTop: 8 }}>
								Загрузка…
							</p>
						) : token && !profile ? (
							<>
								<h3 className="user-menu-title">Профиль</h3>
								<p className="user-menu-meta">
									Не удалось загрузить данные. Проверьте сеть.
								</p>
								<button
									type="button"
									className="thank-button user-menu-action"
									onClick={() => refreshProfile()}
								>
									Повторить
								</button>
								<button
									type="button"
									className="thank-button user-menu-action"
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
								<h3 className="user-menu-title">
									{profile.display_name?.trim() || "Профиль"}
								</h3>
								<p className="user-menu-meta">{profile.phone}</p>
								<button
									type="button"
									className="thank-button user-menu-action"
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
								<h3 className="user-menu-title">Вход</h3>
								<form className="user-menu-form" onSubmit={onLogin}>
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
									<label className="user-menu-label">PIN</label>
									<input
										className="user-menu-input"
										inputMode="numeric"
										autoComplete="current-password"
										placeholder="•••-•••"
										value={pin}
										onChange={(e) =>
											setPin(formatPinMask(e.target.value))
										}
									/>
									{loginErr && (
										<p className="user-menu-error">{loginErr}</p>
									)}
									<PrivacyConsent className="privacy-consent--left" />
									<button
										type="submit"
										className="thank-button user-menu-action"
										disabled={loginBusy}
									>
										{loginBusy ? "Вход…" : "Войти"}
									</button>
								</form>
							</>
						)}
					</div>
				</div>
			)}
		</>
	);
}
