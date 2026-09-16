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
    q: "Как контент попадает к клиенту?",
    a: "После генерации образы сразу доступны в мобильном приложении вашего магазина — клиент листает новинки как в ленте.",
  },
  {
    q: "Сколько стоит Xfashion?",
    a: "Подписка от 5 000 ₽ в месяц; оплата российскими картами.",
  },
  {
    q: "Как быстро я получу результат?",
    a: "Первый лукбук и выдача в приложении настраиваются за минуты, а не недели.",
  },
];

export default function FaqSection() {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: FAQ.map((item) => ({
      "@type": "Question",
      name: item.q,
      acceptedAnswer: { "@type": "Answer", text: item.a },
    })),
  };

  return (
    <section className="xf-section xf-faq" aria-labelledby="xf-faq-title">
      <script type="application/ld+json">{JSON.stringify(jsonLd)}</script>
      <h2 id="xf-faq-title">Частые вопросы</h2>
      <dl className="xf-faq__list">
        {FAQ.map((item) => (
          <div key={item.q} className="xf-faq__item">
            <dt>{item.q}</dt>
            <dd>{item.a}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
