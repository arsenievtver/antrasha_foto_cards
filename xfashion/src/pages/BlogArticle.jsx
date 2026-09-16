import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Link, Navigate, useParams } from "react-router-dom";
import { getArticle } from "../content/articles.js";
import PageMeta from "../components/PageMeta.jsx";
import SiteFooter from "../components/SiteFooter.jsx";
import SiteHeader from "../components/SiteHeader.jsx";

export default function BlogArticle() {
  const { slug } = useParams();
  const article = getArticle(slug);

  if (!article) return <Navigate to="/blog" replace />;

  return (
    <div className="xf-page">
      <PageMeta
        title={`${article.title} — Xfashion`}
        description={article.description}
        canonicalPath={`/blog/${article.slug}`}
      />
      <SiteHeader onCta={() => (window.location.href = "/#xf-lead")} />
      <main className="xf-article">
        <Link to="/blog" className="xf-back">
          ← Блог
        </Link>
        <h1>{article.title}</h1>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{article.body}</ReactMarkdown>
        <p className="xf-article__cta">
          <Link to="/#xf-lead">Запросить демо Xfashion →</Link>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
