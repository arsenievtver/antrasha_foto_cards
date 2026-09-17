import { useEffect, useRef } from "react";

const CARDS = [
  {
    n: "01",
    title: "Экономия",
    text: "До 90% экономии на производстве контента — без студии, моделей и отдельного продакшена.",
  },
  {
    n: "02",
    title: "Скорость",
    text: "От поставки до lookbook у клиента — несколько минут, а не недели после съёмок.",
  },
  {
    n: "03",
    title: "Коммуникации",
    text: "Мобильное приложение магазина: уведомления, статистика по вкусу, персональные предложения и приглашения.",
  },
  {
    n: "04",
    title: "Простота",
    text: "Внедрение без специальных знаний — всё настроим за вас. Без VPN и оплат зарубежными картами, с закрывающими документами.",
  },
];

export default function BenefitCards() {
  const rootRef = useRef(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const nodes = root.querySelectorAll("[data-benefit-anim]");
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) e.target.classList.add("is-in");
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -5% 0px" },
    );
    nodes.forEach((n) => {
      const rect = n.getBoundingClientRect();
      if (rect.top < window.innerHeight * 0.9) n.classList.add("is-in");
      io.observe(n);
    });
    return () => io.disconnect();
  }, []);

  return (
    <section className="xf-benefits" aria-labelledby="xf-benefits-title" ref={rootRef}>
      <div className="xf-benefits__inner">
        <header className="xf-benefits__head" data-benefit-anim>
          <p className="xf-eyebrow">Выгоды</p>
          <h2 id="xf-benefits-title">Почему магазинам выгодно Xfashion</h2>
        </header>

        <ul className="xf-benefits__grid">
          {CARDS.map((c, i) => (
            <li key={c.n}>
              <article
                className="xf-benefits__card"
                data-benefit-anim
                style={{ "--d": `${i * 0.08}s` }}
              >
                <span className="xf-benefits__n">{c.n}</span>
                <h3>{c.title}</h3>
                <p>{c.text}</p>
              </article>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
