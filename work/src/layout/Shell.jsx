import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  clearSession,
  fetchAdminMe,
  getToken,
  hasProductAccess,
  hasWorkAccess,
  setSession,
} from "../api.js";

const PERMS_REFRESH_THROTTLE_MS = 60_000;

/** Таббар: только закупки (если есть «Товар») + Меню для остального. */
function buildTabs() {
  const tabs = [];
  if (hasProductAccess()) {
    tabs.push(
      { to: "/dashboard", label: "Дашборд", ico: "▣" },
      { to: "/orders", label: "Заказы", ico: "◇" },
      { to: "/payments", label: "Оплаты", ico: "◎" },
      { to: "/shipments", label: "Поставки", ico: "▢" },
    );
  }
  if (hasWorkAccess()) {
    tabs.push({ to: "/menu", label: "Меню", ico: "☰" });
  }
  return tabs;
}

export default function Shell() {
  const { pathname } = useLocation();
  const page = getPageMeta(pathname);
  const [, setPermTick] = useState(0);
  const lastRefreshAt = useRef(0);
  const tabs = buildTabs();

  useEffect(() => {
    let cancelled = false;

    async function refreshPermissions({ force = false } = {}) {
      const now = Date.now();
      if (!force && now - lastRefreshAt.current < PERMS_REFRESH_THROTTLE_MS) {
        return;
      }
      lastRefreshAt.current = now;
      try {
        const me = await fetchAdminMe();
        if (cancelled) return;
        setSession(getToken(), me.role, me.permissions || []);
        if (!hasWorkAccess()) {
          clearSession();
          window.location.replace("/login");
          return;
        }
        setPermTick((n) => n + 1);
      } catch {
        /* оставляем права из логина */
      }
    }

    refreshPermissions({ force: true });

    function onVisibility() {
      if (document.visibilityState === "visible") {
        refreshPermissions();
      }
    }
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

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
      {page.addTo && hasProductAccess() ? (
        <Link to={page.addTo} className="fab-add" aria-label={page.addLabel}>
          +
        </Link>
      ) : null}
      {tabs.length > 0 ? (
        <nav className="bottom-nav" aria-label="Разделы">
          {tabs.map((t) => (
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
      ) : null}
    </div>
  );
}

function getPageMeta(pathname) {
  if (pathname === "/dashboard") return { title: "Дашборд" };
  if (pathname === "/menu") return { title: "Меню" };
  if (pathname === "/outlet") return { title: "Аутлет: фото" };
  if (pathname === "/outlet-transfer") return { title: "Аутлет: перенос" };
  if (pathname === "/ai-assistant") return { title: "AI помощник" };
  if (pathname === "/orders") return { title: "Заказы", addTo: "/orders/new", addLabel: "Добавить заказ" };
  if (pathname === "/for-order") return { title: "Для заказа" };
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
  return { title: "Рабочее" };
}
