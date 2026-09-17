import { useId, useState } from "react";

const FAQ = [
  {
    q: "Как сделать лукбук без фотосессии?",
    a: "Загрузите фото вещей в Xfashion — нейросеть за минуты сгенерирует изображения одежды на моделях. Студия, фотограф и модели не нужны.",
  },
  {
    q: "Работает ли Xfashion в России без VPN?",
    a: "Да. Интерфейс на русском, сервис и оплата доступны в РФ без VPN, оплата в рублях.",
  },
  {
    q: "Подходят ли фото для Wildberries и Ozon?",
    a: "Да, изображения подходят для карточек на Wildberries, Ozon, Lamoda и для вашего сайта.",
  },
  {
    q: "Чем Xfashion отличается от «Виртуальной фотостудии» Wildberries?",
    a: "Фотостудия WB генерирует кадры только внутри маркетплейса. Xfashion даёт lookbook для карточек WB/Ozon, сайта и сразу выводит образы в мобильное приложение вашего магазина — с заявкой на примерку.",
  },
  {
    q: "Как контент попадает к клиенту?",
    a: "После генерации образы сразу доступны в мобильном приложении вашего магазина — клиент листает новинки как в ленте и может оставить заявку на примерку.",
  },
  {
    q: "Чем заменить Instagram для продвижения магазина одежды?",
    a: "Своё mobile app и маркетплейсы — рабочая связка в РФ: клиент возвращается к бренду в приложении, а не в запрещённой рекламе Meta. Xfashion ускоряет выпуск визуала под этот цикл.",
  },
  {
    q: "Нужны ли навыки дизайнера или фотографа?",
    a: "Нет. Достаточно снять вещь на телефон в магазине — дальше генерация и публикация в app настраиваются без отдельного продакшена.",
  },
  {
    q: "Сколько стоит Xfashion?",
    a: "Подписка от 5 000 ₽ в месяц; оплата российскими картами.",
  },
  {
    q: "Как быстро я получу результат?",
    a: "Первый лукбук и выдача в приложении настраиваются за минуты, а не недели.",
  },
  {
    q: "Есть интеграция с системами товароучёта?",
    a: "Да. Подключаем Xfashion к разным учётным системам — есть готовое интеграционное решение для «Мой Склад».",
  },
];

export default function FaqSection() {
  const baseId = useId();
  const [open, setOpen] = useState(() => new Set());

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };

  function toggle(i) {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  return (
    <section className="xf-faq" aria-labelledby="xf-faq-title">
      <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      <div className="xf-faq__inner">
        <header className="xf-faq__head">
          <p className="xf-eyebrow">FAQ</p>
          <h2 id="xf-faq-title">Частые вопросы</h2>
        </header>

        <div className="xf-faq__list">
          {FAQ.map((item, i) => {
            const isOpen = open.has(i);
            const panelId = `${baseId}-panel-${i}`;
            const triggerId = `${baseId}-trigger-${i}`;
            return (
              <article key={item.q} className={`xf-faq__item${isOpen ? " is-open" : ""}`}>
                <h3 className="xf-faq__question">
                  <button
                    type="button"
                    id={triggerId}
                    className="xf-faq__trigger"
                    aria-expanded={isOpen}
                    aria-controls={panelId}
                    onClick={() => toggle(i)}
                  >
                    <span className="xf-faq__trigger-text">{item.q}</span>
                    <span className="xf-faq__icon" aria-hidden="true" />
                  </button>
                </h3>
                <div
                  id={panelId}
                  className="xf-faq__panel"
                  role="region"
                  aria-labelledby={triggerId}
                  hidden={!isOpen}
                >
                  <p className="xf-faq__answer">{item.a}</p>
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
