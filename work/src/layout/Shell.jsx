import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { clearSession } from "../api.js";

const TABS = [
  { to: "/orders", label: "Заказы", ico: "◇" },
  { to: "/payments", label: "Оплаты", ico: "◎" },
  { to: "/shipments", label: "Поставки", ico: "▣" },
];

export default function Shell() {
  const { pathname } = useLocation();
  const page = getPageMeta(pathname);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>{page.title}</h1>
        <button
          type="button"
          className="header-logout"
          aria-label="Выйти"
          title="Выйти"
          onClick={() => {
            clearSession();
            window.location.replace("/login");
          }}
        >
          🚪
        </button>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      {page.addTo ? (
        <Link to={page.addTo} className="fab-add" aria-label={page.addLabel}>
          +
        </Link>
      ) : null}
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
    </div>
  );
}

function getPageMeta(pathname) {
  if (pathname === "/orders") return { title: "Заказы", addTo: "/orders/new", addLabel: "Добавить заказ" };
  if (pathname === "/payments") return { title: "Оплаты", addTo: "/payments/new", addLabel: "Добавить оплату" };
  if (pathname === "/shipments") return { title: "Поставки", addTo: "/shipments/new", addLabel: "Добавить поставку" };
  if (pathname === "/orders/new") return { title: "Новый заказ" };
  if (pathname === "/payments/new") return { title: "Новая оплата" };
  if (pathname === "/shipments/new") return { title: "Новая поставка" };
  if (pathname.endsWith("/edit") && pathname.startsWith("/orders/")) return { title: "Редактировать заказ" };
  if (pathname.endsWith("/edit") && pathname.startsWith("/payments/")) return { title: "Редактировать оплату" };
  if (pathname.endsWith("/edit") && pathname.startsWith("/shipments/")) return { title: "Редактировать поставку" };
  if (pathname.startsWith("/orders/")) return { title: "Заказ" };
  if (pathname.startsWith("/payments/")) return { title: "Оплата" };
  if (pathname.startsWith("/shipments/")) return { title: "Поставка" };
  return { title: "Товар" };
}
