import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { registerUser } from "../api/client";
import { useAuth } from "../context/AuthContext";
import {
	formatPhoneMask,
	formatPinMask,
	normalizePhoneRu,
	pinDigits,
} from "../utils/masks";
import "./ThankYou.css";

export default function ThankYou() {
	const { state } = useLocation();
	const navigate = useNavigate();
	const { isAuthenticated, profile, loginWithToken, refreshProfile } =
		useAuth();

	const likes = state?.likes ?? 0;
	const total = state?.total ?? 0;

	const [name, setName] = useState("");
	const [phone, setPhone] = useState("");
	const [pin, setPin] = useState("");
	const [err, setErr] = useState("");
	const [saving, setSaving] = useState(false);
	const [doneRegister, setDoneRegister] = useState(false);

	async function onRegister(e) {
		e.preventDefault();
		setErr("");
		const norm = normalizePhoneRu(phone);
		const p = pinDigits(pin);
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
		setSaving(true);
		try {
			const data = await registerUser({
				displayName: nm,
				phone: norm,
				pin: p,
			});
			loginWithToken(data.access_token);
			await refreshProfile();
			setDoneRegister(true);
		} catch (ex) {
			setErr(ex.message || "Не удалось сохранить");
		} finally {
			setSaving(false);
		}
	}

	const namePart = profile?.display_name?.trim();

	const titleMain = namePart
		? `${namePart}, спасибо за внимание к деталям`
		: "Ваш ритм совпал с коллекцией";

	return (
		<div className="thank-container thank-scroll">
			<p className="thank-kicker">Antrasha · программа лояльности вкуса</p>
			<h2 className="thank-heading">{titleMain}</h2>
			<p className="thank-stats">
				По итогам просмотра: <strong>{likes}</strong> из <strong>{total}</strong>{" "}
				образов совпали с вашим вкусом — это сигнал для персональной подборки и приоритета
				на новинки под ваш стиль.
			</p>

			{isAuthenticated && !doneRegister && (
				<p className="thank-note">
					Вы уже в программе как{" "}
					<strong>
						{namePart || profile?.phone}
					</strong>
					. Отметки из этой сессии учтены в вашем профиле — дальше рекомендации
					становятся точнее.
				</p>
			)}

			{!isAuthenticated && (
				<>
					<p className="thank-section-title">Закрепите свой стиль</p>
					<p className="thank-lead">
						Вступите в программу Antrasha: сохраним ваши лайки и предпочтения в
						профиле, чтобы показывать подборки и поступления не «для всех», а под
						вашу эстетику.
					</p>
					<form className="thank-form" onSubmit={onRegister}>
						<label className="thank-label">Как к вам обращаться</label>
						<input
							className="thank-input"
							value={name}
							onChange={(e) => setName(e.target.value)}
							autoComplete="name"
							placeholder="Имя"
							required
						/>
						<label className="thank-label">Телефон</label>
						<input
							className="thank-input"
							inputMode="tel"
							autoComplete="tel"
							placeholder="+7 (999) 123-45-67"
							value={phone}
							onChange={(e) =>
								setPhone(formatPhoneMask(e.target.value))
							}
							required
						/>
						<label className="thank-label">PIN</label>
						<input
							className="thank-input"
							inputMode="numeric"
							autoComplete="new-password"
							placeholder="•••-•••"
							value={pin}
							onChange={(e) =>
								setPin(formatPinMask(e.target.value))
							}
							required
						/>
						{err && <p className="thank-error">{err}</p>}
						<button
							type="submit"
							className="thank-button thank-submit"
							disabled={saving}
						>
							{saving ? "Сохранение…" : "Вступить в программу"}
						</button>
					</form>
				</>
			)}

			{doneRegister && (
				<p className="thank-note thank-success">
					Добро пожаловать в программу Antrasha. Отметки из этой сессии сохранены —
					рекомендации и новинки будем подстраивать под вас.
				</p>
			)}

			<button
				type="button"
				className="thank-button thank-secondary"
				onClick={() => navigate("/")}
			>
				К новым образам
			</button>
		</div>
	);
}
