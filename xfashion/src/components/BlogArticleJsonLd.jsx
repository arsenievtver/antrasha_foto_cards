import { getSiteOrigin } from "../config/siteOrigin.js";

export default function BlogArticleJsonLd({ article }) {
  if (!article) return null;
  const origin = getSiteOrigin();
  const url = `${origin}/blog/${article.slug}`;
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
      url: `${origin}/`,
    },
    publisher: {
      "@type": "Organization",
      name: "Xfashion",
      url: `${origin}/`,
    },
  };
  return <script type="application/ld+json">{JSON.stringify(data)}</script>;
}
