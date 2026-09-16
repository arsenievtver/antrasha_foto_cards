const ITEMS = [
  {
    title: (
      <>
        Фото с
        <br />
        телефона
      </>
    ),
    sub: "Быстро и удобно",
    icon: (
      <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden>
        <rect x="10" y="3" width="12" height="26" rx="2.5" stroke="currentColor" strokeWidth="1.4" />
        <path d="M14 5.6h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="16" cy="25.6" r="1" fill="currentColor" />
      </svg>
    ),
  },
  {
    title: (
      <>
        Стилизация
        <br />с помощью ИИ
      </>
    ),
    sub: (
      <>
        Профессиональные
        <br />
        фото
      </>
    ),
    icon: (
      <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden>
        <path
          d="M16 4.5l1.35 6.4 6.4 1.35-6.4 1.35L16 20l-1.35-6.4-6.4-1.35 6.4-1.35L16 4.5z"
          stroke="currentColor"
          strokeWidth="1.3"
          strokeLinejoin="round"
        />
        <path
          d="M24.2 16.8l.7 2.95 2.95.7-2.95.7-.7 2.95-.7-2.95-2.95-.7 2.95-.7.7-2.95z"
          stroke="currentColor"
          strokeWidth="1.15"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    title: (
      <>
        Мобильное
        <br />
        приложение
      </>
    ),
    sub: (
      <>
        Для ваших
        <br />
        клиентов
      </>
    ),
    icon: (
      <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden>
        <rect x="10" y="3" width="12" height="26" rx="2.5" stroke="currentColor" strokeWidth="1.4" />
        <path
          d="M16 11.2c-.9-.85-2.45-.45-2.45.85 0 1.7 2.45 3.15 2.45 3.15s2.45-1.45 2.45-3.15c0-1.3-1.55-1.7-2.45-.85z"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinejoin="round"
        />
      </svg>
    ),
  },
  {
    title: (
      <>
        Больше
        <br />
        продаж
      </>
    ),
    sub: (
      <>
        С ярким
        <br />
        контентом
      </>
    ),
    icon: (
      <svg viewBox="0 0 32 32" width="28" height="28" fill="none" aria-hidden>
        <path d="M5 26V8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <path d="M5 26h22" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        <path d="M10 26v-6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M15.5 26V12.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M21 26V9.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <path d="M20 6.8h6.2v6.2" stroke="currentColor" strokeWidth="1.35" strokeLinejoin="round" />
        <path d="M26 7.2l-6.4 6.4" stroke="currentColor" strokeWidth="1.35" strokeLinecap="round" />
      </svg>
    ),
  },
];

export default function HeroHighlights() {
  return (
    <ul className="xf-hero-highlights" aria-label="Преимущества">
      {ITEMS.map((item, i) => (
        <li key={i} className="xf-hero-highlights__item">
          <span className="xf-hero-highlights__icon">{item.icon}</span>
          <span className="xf-hero-highlights__title">{item.title}</span>
          <span className="xf-hero-highlights__sub">{item.sub}</span>
        </li>
      ))}
    </ul>
  );
}
