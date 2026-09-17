import { Link } from "react-router-dom";

export default function SiteFooter() {
  return (
    <footer className="xf-footer">
      <div className="xf-footer__inner">
        <div className="xf-footer__main">
          <div className="xf-footer__brand">
            <Link to="/" className="xf-logo xf-logo--footer">
              <span className="xf-logo__mark">X</span>
              <span className="xf-logo__text">fashion</span>
            </Link>
            <p className="xf-footer__tagline">Технологическое решение для fashion-ритейла</p>
          </div>

          <nav className="xf-footer__nav" aria-label="Подвал">
            <Link to="/blog" className="xf-footer__link">
              Блог
            </Link>
            <Link to="/#xf-lead" className="xf-footer__link">
              Запросить демо
            </Link>
            <a href="mailto:i@aarsenev.ru" className="xf-footer__link xf-footer__link--email">
              i@aarsenev.ru
            </a>
            <a
              href="https://antrasha.ru/privacy"
              target="_blank"
              rel="noopener noreferrer"
              className="xf-footer__link"
            >
              Конфиденциальность
            </a>
          </nav>
        </div>

        <p className="xf-footer__legal">
          <span>Разработка: ИП, проект ANTRASHA</span>
          <span className="xf-footer__legal-sep" aria-hidden="true">
            ·
          </span>
          <span>Оплата в рублях · работает в России</span>
        </p>
      </div>
    </footer>
  );
}
