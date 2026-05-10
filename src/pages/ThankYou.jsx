import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { createFittingRequest, registerUser } from "../api/client";
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
	const likedPhotoIds = Array.isArray(state?.likedPhotoIds) ? state.likedPhotoIds : [];

	const [name, setName] = useState("");
	const [phone, setPhone] = useState("");
	const [pin, setPin] = useState("");
	const [err, setErr] = useState("");
	const [saving, setSaving] = useState(false);
	const [doneRegister, setDoneRegister] = useState(false);
	const [fittingRequested, setFittingRequested] = useState(false);
	const [fittingBusy, setFittingBusy] = useState(false);

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
	const likeRate = total > 0 ? likes / total : 0;
	const isHighMatch = total > 0 && likeRate >= 0.5;
	const hasAnyLikes = likes > 0;
	const pct = Math.round(likeRate * 100);

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

	const titleMain = namePart
		? `${namePart}, спасибо за внимание к деталям`
		: !isAuthenticated
			? !hasAnyLikes
				? "Нам очень жаль — в этот раз без совпадений"
				: isHighMatch
					? "Ваш ритм совпал с коллекцией"
					: "Хороший старт — уже есть на что опереться"
			: !hasAnyLikes
				? "Нам очень жаль — в этот раз без совпадений"
				: isHighMatch
					? "Ваш ритм совпал с коллекцией"
					: "Хороший старт — уже есть на что опереться";

	const statsRegistered = (
		<p className="thank-stats">
			По итогам просмотра: <strong>{likes}</strong> из <strong>{total}</strong>{" "}
			образов совпали с вашим вкусом — это сигнал для персональной подборки и приоритета
			на новинки под ваш стиль.
		</p>
	);

	const statsGuest = !hasAnyLikes ? (
		<p className="thank-stats">
			По итогам просмотра: <strong>{likes}</strong> из <strong>{total}</strong> — ни
			один образ не получил лайк. Бывает: и мимо кнопки промахнулись, и настроение не
			то. Нам всё равно приятно, что заглянули.
		</p>
	) : isHighMatch ? (
		<p className="thank-stats">
			По итогам просмотра: <strong>{likes}</strong> из <strong>{total}</strong> —{" "}
			<strong>{pct}%</strong> лайков. Сильное совпадение со стилем коллекции: после
			регистрации сможете оставить заявку на персональную примерку, как у участников
			программы.
		</p>
	) : (
		<p className="thank-stats">
			По итогам просмотра: <strong>{likes}</strong> из <strong>{total}</strong> — пока{" "}
			<strong>{pct}%</strong> лайков, и это нормальный старт для точной персональной
			подборки. Закрепите профиль — и после регистрации сможете запросить примерку, если
			захотите.
		</p>
	);

	const guestLead = !hasAnyLikes ? (
		<>
			Если всё же хотите быть в курсе — вступите в программу Antrasha: зарегистрированным
			первыми показываем новинки и персональные акции, а не общую рассылку.
		</>
	) : (
		<>
			Вступите в программу Antrasha: сохраним ваши лайки и предпочтения в профиле, чтобы
			показывать подборки и поступления не «для всех», а под вашу эстетику — и открыть
			заявку на примерку после регистрации.
		</>
	);

	const fittingMatchTitle = isHighMatch
		? `У вас сильное совпадение со стилем коллекции — ${pct}% лайков.`
		: `Пока совпадение ${pct}%, и это нормальный старт для точной персональной подборки.`;

	const fittingPositiveBlock = (
		<>
			<p className="thank-fitting-title">{fittingMatchTitle}</p>
			<p className="thank-fitting-text">
				{isHighMatch
					? "Приглашаем на персональную примерку в магазин ANTRASHA: г. Тверь, б-р Радищева, д. 37."
					: "Мы уже зафиксировали ваши предпочтения и в следующих подборках покажем больше образов, близких именно вашему вкусу."}
			</p>
			<p className="thank-fitting-text">
				Нажмите кнопку ниже, и мы свяжемся с вами по номеру из профиля:
				уточним размеры и удобное время, подготовим образы под ваш вкус.
				Можем организовать примерку в магазине или подобрать образы и
				выехать к вам домой, чтобы вы спокойно примерили их в привычной
				обстановке и приняли решение о покупке.
			</p>
			{fittingRequested ? (
				<p className="thank-note thank-success">
					Заявка принята. Скоро позвоним вам для согласования примерки.
				</p>
			) : (
				<button
					type="button"
					className="thank-button thank-submit"
					disabled={fittingBusy}
					onClick={onFittingRequest}
				>
					{fittingBusy ? "Отправляем…" : "Заявка на примерку"}
				</button>
			)}
		</>
	);

	const showFittingAfterRegister = doneRegister && hasAnyLikes;

	return (
		<div className="thank-container thank-scroll">
			<p className="thank-kicker">
				<span>Antrasha</span>
				<span>программа лояльности вкуса</span>
			</p>
			<h2 className="thank-heading">{titleMain}</h2>
			{isAuthenticated ? statsRegistered : statsGuest}
			{err ? <p className="thank-error">{err}</p> : null}

			{isAuthenticated && !doneRegister && (
				<>
					<p className="thank-note">
						Вы уже в программе как{" "}
						<strong>
							{namePart || profile?.phone}
						</strong>
						. Мы добавили результаты этой сессии в ваш профиль, чтобы персональные
						подборки становились точнее с каждым визитом.
					</p>
					<div className="thank-fitting">
						{hasAnyLikes ? fittingPositiveBlock : (
							<>
								<p className="thank-fitting-title">
									В этот раз совпадений не нашлось — и это тоже полезный результат.
								</p>
								<p className="thank-fitting-text">
									Очень жаль, что ни один образ не откликнулся сейчас. В следующий раз
									подборка будет точнее: мы учли вашу сессию и продолжим улучшать
									рекомендации под ваш вкус.
								</p>
							</>
						)}
					</div>
				</>
			)}

			{!isAuthenticated && (
				<>
					<p className="thank-section-title">Закрепите свой стиль</p>
					<p className="thank-lead">{guestLead}</p>
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
						<label className="thank-label">
							PIN — код для входа в личный кабинет
						</label>
						<p className="thank-label-hint">
							Вместо пароля: придумайте 6 цифр — по ним вы войдёте в профиль с этого
							или другого устройства.
						</p>
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

			{showFittingAfterRegister ? (
				<div className="thank-fitting">{fittingPositiveBlock}</div>
			) : null}

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
