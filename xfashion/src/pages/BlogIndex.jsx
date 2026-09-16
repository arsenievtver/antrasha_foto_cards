import { Link } from "react-router-dom";
import { ARTICLES } from "../content/articles.js";
import PageMeta from "../components/PageMeta.jsx";
import SiteFooter from "../components/SiteFooter.jsx";
import SiteHeader from "../components/SiteHeader.jsx";

export default function BlogIndex() {
  return (
    <div className="xf-page">
      <PageMeta
        title="Блог Xfashion — нейросеть, лукбук и app для магазина одежды"
        description="Статьи про фото без фотосессии, Wildberries и mobile app для fashion-бренда в России."
        canonicalPath="/blog"
      />
      <SiteHeader onCta={() => (window.location.href = "/#xf-lead")} />
      <main className="xf-blog">
        <h1>Блог</h1>
        <p className="xf-intro">Практика для магазинов одежды и локальных брендов.</p>
        <ul className="xf-blog__list">
          {ARTICLES.map((a) => (
            <li key={a.slug}>
              <Link to={`/blog/${a.slug}`}>{a.title}</Link>
              <p>{a.description}</p>
            </li>
          ))}
        </ul>
      </main>
      <SiteFooter />
    </div>
  );
}
