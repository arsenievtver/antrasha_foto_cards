import { NavLink, Outlet } from "react-router-dom";
import { clearSession } from "../api.js";

const TABS = [
  { to: "/orders", label: "Заказы", ico: "◇" },
  { to: "/payments", label: "Оплаты", ico: "◎" },
  { to: "/shipments", label: "Поставки", ico: "▣" },
];

export default function Shell() {
  return (
    <div className="app-shell">
      <main className="app-main">
        <Outlet />
      </main>
      <nav className="bottom-nav" aria-label="Разделы">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            <span className="nav-ico" aria-hidden>
              {t.ico}
            </span>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <button
        type="button"
        className="secondary"
        style={{
          position: "fixed",
          top: "calc(0.5rem + var(--safe-top))",
          right: "0.75rem",
          zIndex: 30,
          padding: "0.35rem 0.65rem",
          fontSize: "0.75rem",
          opacity: 0.7,
        }}
        onClick={() => {
          clearSession();
          window.location.replace("/login");
        }}
      >
        Выйти
      </button>
    </div>
  );
}
