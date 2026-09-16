import { useEffect, useRef } from "react";

const STEPS = [
  {
    n: "01",
    title: "Сняли на вешалке",
    text: "Обычное фото с телефона прямо в магазине. Вещь как есть — без студии, моделей и отдельного продакшена.",
    img: "/how/hanger.jpg",
    alt: "Одежда на вешалке, снятая на телефон",
    kind: "photo",
  },
  {
    n: "02",
    title: "Собрали lookbook",
    text: "ИИ показывает, как та же одежда сидит на человеке. Готовые образы за минуты, а не после недели съёмок.",
    img: "/how/model.jpg",
    alt: "Та же одежда на модели",
    kind: "photo",
  },
  {
    n: "03",
    title: "Клиент уже листает",
    text: "Образы сразу в приложении вашего магазина. Покупатель выбирает лук у себя в телефоне — как в привычной ленте.",
    img: "/how/app-phone.png",
    alt: "Lookbook в мобильном приложении магазина",
    kind: "app",
  },
  {
    n: "04",
    title: "Заявка на примерку",
    text: "После ленты клиент сам оставляет заявку. Для магазина это обратная связь по вкусу и тёплый лид в воронке — без холодных касаний.",
    img: "/how/fitting-phone.png",
    alt: "Заявка на примерку в приложении магазина",
    kind: "app",
  },
];

function Arrow({ down = false }) {
  return (
    <div className={`xf-flow__arrow ${down ? "xf-flow__arrow--down" : ""}`} aria-hidden="true">
      <svg viewBox="0 0 48 48" width="36" height="36">
        {down ? (
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M24 8v28M14 26l10 10 10-10"
          />
        ) : (
          <path
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8 24h28M26 14l10 10-10 10"
          />
        )}
      </svg>
    </div>
  );
}

export default function HowItWorks() {
  const rootRef = useRef(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll("[data-flow-anim]");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add("is-in");
        });
      },
      { threshold: 0.18, rootMargin: "0px 0px -6% 0px" },
    );
    nodes.forEach((n) => {
      const rect = n.getBoundingClientRect();
      if (rect.top < window.innerHeight * 0.88) n.classList.add("is-in");
      io.observe(n);
    });
    return () => io.disconnect();
  }, []);

  return (
    <section className="xf-flow" aria-labelledby="xf-flow-title" ref={rootRef}>
      <div className="xf-flow__inner">
        <header className="xf-flow__head" data-flow-anim>
          <p className="xf-eyebrow">Как это работает</p>
          <h2 id="xf-flow-title">От фото на вешалке — до заявки на примерку</h2>
          <p className="xf-flow__lead">
            Сняли в магазине, собрали lookbook — клиент листает образы в приложении и сам двигается к примерке.
          </p>
        </header>

        <ol className="xf-flow__list">
          {STEPS.map((s, i) => (
            <li key={s.n} className="xf-flow__item">
              {i > 0 ? <Arrow down /> : null}
              <article className="xf-flow__step" data-flow-anim style={{ "--d": `${i * 0.1}s` }}>
                <div className={`xf-flow__visual xf-flow__visual--${s.kind}`}>
                  <figure className={s.kind === "app" ? "xf-flow__phone" : "xf-flow__shot"}>
                    <img src={s.img} alt={s.alt} />
                  </figure>
                </div>
                <div className="xf-flow__copy">
                  <span className="xf-flow__n">{s.n}</span>
                  <h3>{s.title}</h3>
                  <p>{s.text}</p>
                </div>
              </article>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
