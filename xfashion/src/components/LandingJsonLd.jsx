import { getSiteOrigin } from "../config/siteOrigin.js";

export default function LandingJsonLd() {
  const origin = getSiteOrigin();
  const org = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Xfashion",
    url: `${origin}/`,
    description:
      "ИИ-лукбук и мобильное приложение для магазинов одежды: фото с вешалки, образы на модели, заявка на примерку.",
  };
  const website = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "Xfashion",
    url: `${origin}/`,
    inLanguage: "ru-RU",
    publisher: { "@type": "Organization", name: "Xfashion", url: `${origin}/` },
  };
  const product = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Xfashion",
    url: `${origin}/`,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    description:
      "Сервис для магазинов одежды: нейросеть создаёт lookbook из фото на вешалке, контент попадает в mobile app магазина и в карточки Wildberries и Ozon.",
    featureList: [
      "Генерация фото одежды на модели из снимка на вешалке",
      "Выдача lookbook в мобильном приложении магазина",
      "Заявка на примерку в приложении",
      "Контент для карточек Wildberries и Ozon",
      "Интеграция с «МойСklad»",
    ],
    offers: {
      "@type": "Offer",
      price: "5000",
      priceCurrency: "RUB",
      priceSpecification: {
        "@type": "UnitPriceSpecification",
        price: "5000",
        priceCurrency: "RUB",
        unitText: "MONTH",
      },
    },
  };
  return (
    <>
      <script type="application/ld+json">{JSON.stringify(org)}</script>
      <script type="application/ld+json">{JSON.stringify(website)}</script>
      <script type="application/ld+json">{JSON.stringify(product)}</script>
    </>
  );
}
