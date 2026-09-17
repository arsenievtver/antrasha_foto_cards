import { useCallback } from "react";
import { Link } from "react-router-dom";
import BenefitCards from "../components/BenefitCards.jsx";
import FaqSection from "../components/FaqSection.jsx";
import HowItWorks from "../components/HowItWorks.jsx";
import LandingSeoIntro from "../components/LandingSeoIntro.jsx";
import LandingJsonLd from "../components/LandingJsonLd.jsx";
import LeadForm from "../components/LeadForm.jsx";
import PageMeta from "../components/PageMeta.jsx";
import SiteFooter from "../components/SiteFooter.jsx";
import SiteHeader from "../components/SiteHeader.jsx";
import VideoHero from "../components/VideoHero.jsx";

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
        <LandingSeoIntro />
        <HowItWorks />
        <BenefitCards />
        <FaqSection />
        <section className="xf-blog-teaser" aria-labelledby="xf-blog-teaser-title">
          <div className="xf-blog-teaser__inner">
            <header className="xf-blog-teaser__head">
              <p className="xf-eyebrow">Блог</p>
              <h2 id="xf-blog-teaser-title">Гайды для владельцев магазинов</h2>
              <p className="xf-blog-teaser__lead">
                Лукбуки, маркетплейсы и mobile app без Instagram.
              </p>
              <Link to="/blog" className="xf-link xf-blog-teaser__link">
                Читать гайды →
              </Link>
            </header>
          </div>
        </section>
        <section className="xf-lead-section">
          <div className="xf-lead-section__inner">
            <LeadForm />
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
