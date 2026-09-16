import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export default function SiteHeader({ onCta, overlay = false }) {
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menuOpen]);

  useEffect(() => {
    document.body.classList.toggle("xf-nav-open", menuOpen);
    return () => document.body.classList.remove("xf-nav-open");
  }, [menuOpen]);

  function handleDemo() {
    setMenuOpen(false);
    onCta?.();
  }

  return (
    <header className={overlay ? "xf-header xf-header--overlay" : "xf-header"}>
      <Link to="/" className="xf-logo">
        <span className="xf-logo__mark">X</span>
        <span className="xf-logo__text">fashion</span>
      </Link>
      <nav className="xf-nav" aria-label="Основное">
        <Link to="/blog" className="xf-nav__link">
          Блог
        </Link>
        <button type="button" className="xf-btn xf-btn--ghost xf-btn--sm xf-nav__demo" onClick={handleDemo}>
          Демо
        </button>
        <button
          type="button"
          className="xf-nav__burger"
          aria-expanded={menuOpen}
          aria-controls="xf-nav-drawer"
          aria-label={menuOpen ? "Закрыть меню" : "Открыть меню"}
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span />
          <span />
          <span />
        </button>
      </nav>
      {menuOpen ? (
        <div id="xf-nav-drawer" className="xf-nav-drawer" role="dialog" aria-modal="true" aria-label="Меню">
          <Link to="/blog" className="xf-nav-drawer__link" onClick={() => setMenuOpen(false)}>
            Блог
          </Link>
          <button type="button" className="xf-nav-drawer__link" onClick={handleDemo}>
            Запросить демо
          </button>
          <a href="#xf-lead" className="xf-nav-drawer__link" onClick={() => setMenuOpen(false)}>
            Форма заявки
          </a>
          <a href="#xf-after-hero" className="xf-nav-drawer__link" onClick={() => setMenuOpen(false)}>
            Как это работает
          </a>
        </div>
      ) : null}
    </header>
  );
}
