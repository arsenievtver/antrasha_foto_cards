const CARDS = [
  {
    title: "Меньше трат на маркетинг",
    text: "Студия и фотограф съедают маржу. ИИ-визуал и клиентское приложение — фиксированная подписка от 5 000 ₽/мес.",
  },
  {
    title: "Свой DTC-канал",
    text: "Не только маркетплейс: собственное app удерживает клиента у бренда — как у сильных direct-to-consumer брендов.",
  },
  {
    title: "Fashion-tech из коробки",
    text: "Новые коллекции быстрее доходят до покупателя: генерация контента и выдача в app в одном продукте, без VPN и в рублях.",
  },
];

export default function BenefitCards() {
  return (
    <section className="xf-benefits" aria-labelledby="xf-benefits-title">
      <h2 id="xf-benefits-title" className="xf-visually-hidden">
        Почему Xfashion
      </h2>
      <ul className="xf-benefits__grid">
        {CARDS.map((c) => (
          <li key={c.title} className="xf-benefits__card">
            <h3>{c.title}</h3>
            <p>{c.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
