import { useCallback } from "react";
import { Link } from "react-router-dom";
import BenefitCards from "../components/BenefitCards.jsx";
import FaqSection from "../components/FaqSection.jsx";
import HowItWorks from "../components/HowItWorks.jsx";
import LandingJsonLd from "../components/LandingJsonLd.jsx";
import LeadForm from "../components/LeadForm.jsx";
import PageMeta from "../components/PageMeta.jsx";
import SiteFooter from "../components/SiteFooter.jsx";
import SiteHeader from "../components/SiteHeader.jsx";
import VideoHero from "../components/VideoHero.jsx";

const SEO_BLOCKS = [
  {
    title: "Фото на моделях без съёмок",
    text: "Кадры для сайта, карточек Wildberries и Ozon и клиентского приложения — из одного пайплайна.",
  },
  {
    title: "ИИ-лукбук и приложение в одной подписке",
    text: "Отдельные генераторы фото не отдают результат в ваш mobile app — Xfashion закрывает цикл «контент → приложение».",
  },
];

export default function Landing() {
  const scrollToLead = useCallback(() => {
    document.getElementById("xf-lead")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  return (
    <div className="xf-page xf-page--home">
      <PageMeta
        title="Xfashion — lookbook из фото с телефона, приложение для клиентов"
        description="Готовое решение для магазинов одежды: стильный lookbook из фото с телефона и своё приложение для клиентов. От 5 000 ₽/мес."
        canonicalPath="/"
      />
      <LandingJsonLd />

      <div className="xf-hero-shell">
        <SiteHeader onCta={scrollToLead} overlay />
        <VideoHero onCta={scrollToLead} />
      </div>

      <main id="xf-after-hero">
        <HowItWorks />
        <BenefitCards />
        {SEO_BLOCKS.map((s) => (
          <section key={s.title} className="xf-section xf-block xf-block--compact">
            <h2>{s.title}</h2>
            <p>{s.text}</p>
          </section>
        ))}
        <section className="xf-section xf-blog-teaser">
          <h2>Гайды для владельцев магазинов</h2>
          <p>Лукбуки, маркетплейсы и mobile app без Instagram.</p>
          <Link to="/blog" className="xf-link">
            Блог →
          </Link>
        </section>
        <FaqSection />
        <section className="xf-section xf-lead-wrap">
          <LeadForm />
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
