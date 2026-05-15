import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion as Motion } from "framer-motion";
import { createFittingRequest, createGuestFittingRequest } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { formatPhoneMask, normalizePhoneRu } from "../utils/masks";
import PrivacyConsent from "../components/PrivacyConsent";
import "./About.css";
import "./ThankYou.css";

/**
 * Фото: положите файлы в src/assets/about/ и раскомментируйте импорты + теги <img> ниже.
 *
 * Рекомендуемые слоты:
 *   hero.jpg          — широкий кадр под первый экран (опционально)
 *   atmosphere-1.jpg — атмосфера / зал
 *   atmosphere-2.jpg — примерочные
 *   atmosphere-3.jpg — деталь / сервис
 */
import heroImg from "../assets/about/hero.jpg";
import atmosphere1 from "../assets/about/atmosphere-1.jpg";
import atmosphere2 from "../assets/about/atmosphere-2.jpg";
import atmosphere3 from "../assets/about/atmosphere-3.jpg";

const fadeUp = {
	initial: { opacity: 0, y: 20 },
	whileInView: { opacity: 1, y: 0 },
	viewport: { once: true, margin: "-60px" },
	transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] },
};

const fade = {
	initial: { opacity: 0 },
	whileInView: { opacity: 1 },
	viewport: { once: true, margin: "-40px" },
	transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
};

export default function About() {
	const navigate = useNavigate();
	const { isAuthenticated } = useAuth();
	const [fittingBusy, setFittingBusy] = useState(false);
	const [fittingDone, setFittingDone] = useState(false);
	const [fittingErr, setFittingErr] = useState("");
	const [guestPhone, setGuestPhone] = useState("");

	async function onFittingRequest() {
		setFittingErr("");
		setFittingBusy(true);
		try {
			if (isAuthenticated) {
				await createFittingRequest({
					likes: 0,
					total: 0,
					photoIds: [],
					note: "Страница «О ANTRASHA»",
				});
			} else {
				const norm = normalizePhoneRu(guestPhone);
				if (!norm) {
					setFittingErr("Укажите корректный номер телефона");
					return;
				}
				await createGuestFittingRequest({
					phone: norm,
					note: "Страница «О ANTRASHA»",
				});
			}
			setFittingDone(true);
		} catch (ex) {
			setFittingErr(ex.message || "Не удалось отправить заявку");
		} finally {
			setFittingBusy(false);
		}
	}

	return (
		<div className="about-page">
			<header className="about-topbar">
				<button
					type="button"
					className="about-back"
					onClick={() => navigate("/")}
					aria-label="На главную"
				>
					<span className="about-back__chevron" aria-hidden />
					<span className="about-back__label">назад</span>
				</button>
			</header>

			<main className="about-main">
				<Motion.section className="about-hero-screen" {...fade}>
					<div className="about-hero-screen__inner">
						<p className="about-eyebrow">ANTRASHA</p>
						<h1 className="about-hero__title">
							Безупречный стиль
							<span className="about-hero__title-break">
								персонально для Вас
							</span>
						</h1>
						<div
							className="about-hero__media about-media-slot"
							data-slot="hero"
						>
							<img
								src={heroImg}
								alt="ANTRASHA — бутик"
								className="about-media-slot__img"
							/>
							<span className="about-media-slot__hint">hero — 3∶4 или 16∶9</span>
						</div>
					</div>
				</Motion.section>

				<div className="about-body">
					<div className="about-body__inner">
						<Motion.section className="about-block" {...fadeUp}>
							<p className="about-prose">
								ANTRASHA — пространство одежды с более чем 20-летней историей в
								историческом центре Твери.
							</p>
							<p className="about-prose">
								Мы работаем с тщательно отобранными европейскими брендами
								(Германия, Италия, Нидерланды, Дания), для которых качество,
								крой и сдержанная элегантность — не тенденция, а стандарт.
							</p>
							<p className="about-brands" lang="en">
								Roy Robson · Riani · Marc Aurel · Seidensticker · Aeronautica
								Militare
							</p>
						</Motion.section>

						<Motion.section className="about-block about-block--quote" {...fade}>
							<blockquote className="about-quote">
								<p>
									Каждое решение здесь выверено: от подбора коллекций до
									персональной работы с клиентом. Мы не предлагаем случайные
									вещи — мы собираем образы, которые органично вписываются в
									ваш ритм жизни и подчеркивают статус без избыточности.
								</p>
							</blockquote>
							<p className="about-prose about-prose--tight">
								ANTRASHA — это выбор тех, кто ценит точность, приватность и
								уверенность в результате.
							</p>
						</Motion.section>

						<div className="about-rule" aria-hidden />

						<Motion.section className="about-block" {...fadeUp}>
							<h2 className="about-h2">Атмосфера бутика</h2>
							<p className="about-prose">
								Пространство, где время замедляется. Мы создали бутик ANTRASHA,
								чтобы Ваш шопинг был похож на отдых. Никакой спешки — только Вы,
								приятная музыка, идеальные силуэты и стилист, который работает
								лично с Вами.
							</p>
						</Motion.section>

						<section className="about-atmosphere-grid">
					<Motion.article
						className="about-atmo-card"
						{...fadeUp}
						transition={{
							...fadeUp.transition,
							delay: 0,
						}}
					>
						<div
							className="about-atmo-card__media about-media-slot"
							data-slot="atmosphere-1"
						>
							<img
								src={atmosphere1}
								alt="Комфортная атмосфера бутика ANTRASHA"
								className="about-media-slot__img"
							/>
							<span className="about-media-slot__hint">atmosphere-1</span>
						</div>
						<h3 className="about-h3">Комфортная атмосфера</h3>
						<p className="about-prose about-prose--small">
							Пространство, созданное для вашего удовольствия и расслабления.
						</p>
					</Motion.article>
					<Motion.article
						className="about-atmo-card"
						{...fadeUp}
						transition={{
							...fadeUp.transition,
							delay: 0.08,
						}}
					>
						<div
							className="about-atmo-card__media about-media-slot"
							data-slot="atmosphere-2"
						>
							<img
								src={atmosphere2}
								alt="Уютные примерочные ANTRASHA"
								className="about-media-slot__img"
							/>
							<span className="about-media-slot__hint">atmosphere-2</span>
						</div>
						<h3 className="about-h3">Уютные примерочные</h3>
						<p className="about-prose about-prose--small">
							Детали интерьера создают ощущение уюта и комфорта.
						</p>
					</Motion.article>
					<Motion.article
						className="about-atmo-card"
						{...fadeUp}
						transition={{
							...fadeUp.transition,
							delay: 0.16,
						}}
					>
						<div
							className="about-atmo-card__media about-media-slot"
							data-slot="atmosphere-3"
						>
							<img
								src={atmosphere3}
								alt="Детали сервиса ANTRASHA"
								className="about-media-slot__img"
							/>
							<span className="about-media-slot__hint">atmosphere-3</span>
						</div>
						<h3 className="about-h3">Бокал на столике</h3>
						<p className="about-prose about-prose--small">
							Маленькие детали, которые делают ваш визит особенным.
						</p>
					</Motion.article>
						</section>

						<div className="about-rule" aria-hidden />

						<Motion.section className="about-block" {...fadeUp}>
							<h2 className="about-h2">Как проходит персональный стайлинг</h2>
							<ol className="about-steps">
						<li className="about-step">
							<span className="about-step__num">01</span>
							<div>
								<h3 className="about-h3">Заявка</h3>
								<p className="about-prose about-prose--small">
									Вы оставляете заявку, и мы связываемся с Вами, чтобы уточнить
									пожелания, ваш ритм жизни и задачи гардероба.
								</p>
							</div>
						</li>
						<li className="about-step">
							<span className="about-step__num">02</span>
							<div>
								<h3 className="about-h3">Подготовка</h3>
								<p className="about-prose about-prose--small">
									Мы заранее отбираем вещи из коллекций европейских брендов и
									составляем для вас индивидуальные капсулы. Вы не тратите время
									на поиск нужного размера.
								</p>
							</div>
						</li>
						<li className="about-step">
							<span className="about-step__num">03</span>
							<div>
								<h3 className="about-h3">Примерка</h3>
								<p className="about-prose about-prose--muted about-prose--small">
									В бутике или у Вас дома
								</p>
								<p className="about-prose about-prose--small">
									Вы приезжаете в наше комфортное пространство в центре Твери,
									либо мы привозим готовые образы к вам домой или в офис.
									Идеальная посадка, советы стилиста и никакой суеты.
								</p>
							</div>
						</li>
							</ol>
						</Motion.section>

						<div className="about-rule" aria-hidden />

						<Motion.section className="about-block about-contacts" {...fadeUp}>
							<h2 className="about-h2">Адрес и контакты</h2>
						<p className="about-contact-brand">ANTRASHA</p>
						<div className="about-contact-lines">
							<a href="tel:+74822453557" className="about-contact-link">
								+7 (4822) 45-35-57
							</a>
							<a
								href="mailto:alexei@antrasha.ru"
								className="about-contact-link"
							>
								alexei@antrasha.ru
							</a>
							<p className="about-prose about-prose--small about-prose--contact">
								Тверь, б-р Радищева, 37
							</p>
							<p className="about-prose about-prose--small about-prose--contact">
								пн.–пт. 10:30–19:30
								<br />
								сб.–вс. 11:00–18:00
							</p>
						</div>
						<p className="about-social-title">Мессенджеры</p>
						<div className="about-social-links">
							<a
								href="https://t.me/AntrashaBot"
								target="_blank"
								rel="noopener noreferrer"
								className="about-contact-link about-contact-link--external"
							>
								Telegram — @AntrashaBot
							</a>
							<a
								href="https://max.ru/id690300316030_biz"
								target="_blank"
								rel="noopener noreferrer"
								className="about-contact-link about-contact-link--external"
							>
								MAX
							</a>
						</div>
						</Motion.section>

						<Motion.section className="about-block about-fitting-wrap" {...fadeUp}>
							<div className="thank-fitting">
						<p className="thank-fitting-title">
							Персональная примерка в ANTRASHA
						</p>
						<p className="thank-fitting-text">
							{isAuthenticated
								? "Нажмите кнопку ниже — мы свяжемся с вами по номеру из профиля: уточним размеры и удобное время, подготовим образы под ваш вкус. Примерка в бутике в центре Твери или выезд с подборкой к вам домой или в офис."
								: "Укажите телефон и нажмите кнопку — перезвоним, чтобы согласовать время и формат примерки: в бутике на бульваре Радищева или выезд с подборкой к вам домой или в офис."}
						</p>
						{!isAuthenticated && !fittingDone ? (
							<>
								<label className="thank-label" htmlFor="about-guest-phone">
									Телефон
								</label>
								<input
									id="about-guest-phone"
									className="thank-input"
									inputMode="tel"
									autoComplete="tel"
									placeholder="+7 (999) 123-45-67"
									value={guestPhone}
									onChange={(e) =>
										setGuestPhone(formatPhoneMask(e.target.value))
									}
								/>
							</>
						) : null}
						{fittingErr ? (
							<p className="thank-error">{fittingErr}</p>
						) : null}
						{fittingDone ? (
							<p className="thank-note thank-success">
								Заявка принята. Скоро позвоним для согласования примерки.
							</p>
						) : (
							<>
								<PrivacyConsent />
								<button
									type="button"
									className="thank-button thank-submit"
									disabled={fittingBusy}
									onClick={onFittingRequest}
								>
									{fittingBusy ? "Отправляем…" : "Заявка на примерку"}
								</button>
							</>
						)}
							</div>
						</Motion.section>

						<footer className="about-footer">
							<p className="about-footer__mark">ANTRASHA</p>
							<Link to="/privacy" className="about-footer__legal">
								Политика конфиденциальности
							</Link>
						</footer>
					</div>
				</div>
			</main>
		</div>
	);
}
