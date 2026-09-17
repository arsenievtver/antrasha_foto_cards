export default function BlogArticleJsonLd({ article }) {
  if (!article) return null;
  const url = `https://xfashion.pro/blog/${article.slug}`;
  const data = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: article.title,
    description: article.description,
    url,
    mainEntityOfPage: url,
    inLanguage: "ru-RU",
    author: {
      "@type": "Organization",
      name: "Xfashion",
      url: "https://xfashion.pro/",
    },
    publisher: {
      "@type": "Organization",
      name: "Xfashion",
      url: "https://xfashion.pro/",
    },
  };
  return <script type="application/ld+json">{JSON.stringify(data)}</script>;
}
