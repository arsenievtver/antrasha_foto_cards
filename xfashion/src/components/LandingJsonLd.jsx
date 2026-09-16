export default function LandingJsonLd() {
  const org = {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "Xfashion",
    url: "https://xfashion.pro/",
    description:
      "ИИ-контент и mobile app для магазинов одежды: лукбук нейросетью без фотостудии.",
  };
  const product = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Xfashion",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
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
      <script type="application/ld+json">{JSON.stringify(product)}</script>
    </>
  );
}
