import { Children, useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import {
  clearSession,
  fetchAdminMe,
  getRole,
  getToken,
  hasPermission,
  hasValidSession,
  setSession,
} from "../api.js";

function NavItem({ to, end, children }) {
  return (
    <NavLink to={to} end={end} className={({ isActive }) => (isActive ? "active" : "")}>
      {children}
    </NavLink>
  );
}

function NavGroup({ title, children }) {
  const items = Children.toArray(children).filter(Boolean);
  if (items.length === 0) return null;
  return (
    <div className="nav-group">
      <div className="nav-group__title">{title}</div>
      <div className="nav-group__links">{items}</div>
    </div>
  );
}

export default function Layout() {
  const nav = useNavigate();
  const role = getRole();
  const isSuperuser = role === "superuser";
  const isWorker = role === "worker";
  const hasAdminAccess = isSuperuser || isWorker;
  const [, setPermTick] = useState(0);

  useEffect(() => {
    if (!hasValidSession() || !hasAdminAccess) return;
    let cancelled = false;
    (async () => {
      try {
        const me = await fetchAdminMe();
        if (cancelled) return;
        setSession(getToken(), me.role, me.permissions || []);
        setPermTick((n) => n + 1);
      } catch {
        /* оставляем права из логина */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [hasAdminAccess]);

  if (!hasValidSession() || !hasAdminAccess) {
    return <Navigate to="/login" replace />;
  }

  const can = (perm) => isSuperuser || hasPermission(perm);

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar__brand">Админка</div>

        <nav className="sidebar__nav">
          <NavGroup title="Обзор">
            {can("stats") && (
              <NavItem end to="/">
                Статистика
              </NavItem>
            )}
          </NavGroup>

          <NavGroup title="Клиенты">
            {isSuperuser && <NavItem to="/users">Клиенты и сотрудники</NavItem>}
            {can("clients") && <NavItem to="/fitting-requests">Заявки на примерку</NavItem>}
          </NavGroup>

          <NavGroup title="Фото">
            {can("photos") && <NavItem to="/photos">Фото и теги</NavItem>}
            {can("photos") && <NavItem to="/photo-ratings">Рейтинг фото</NavItem>}
            {can("photos") && <NavItem to="/tags">Справочник тегов</NavItem>}
            {can("photos") && <NavItem to="/tagging">Разметка тегов</NavItem>}
            {can("photos") && <NavItem to="/ai-ingest">ИИ: телефон → каталог</NavItem>}
          </NavGroup>

          <NavGroup title="Реклама">
            {can("ads") && <NavItem to="/campaigns">Рекламные ссылки</NavItem>}
            {can("ads") && <NavItem to="/promo-banners">Баннеры на главной</NavItem>}
            {can("ads") && <NavItem to="/hero-banners">Hero-баннеры (/v2)</NavItem>}
            {can("ads") && <NavItem to="/home-v2-gender-cards">MEN / WOMEN (/v2)</NavItem>}
            {can("ads") && <NavItem to="/push">Push-уведомления</NavItem>}
          </NavGroup>

          <NavGroup title="Товар">
            {can("product") && <NavItem to="/seasons">Сезоны</NavItem>}
            {can("product") && <NavItem to="/brands">Бренды</NavItem>}
            {can("product") && <NavItem to="/brand-orders">Заказы брендам</NavItem>}
            {can("product") && <NavItem to="/payments">Оплаты</NavItem>}
            {can("product") && <NavItem to="/shipments">Поставки</NavItem>}
            {can("product") && <NavItem to="/fx-rates">Курс EUR</NavItem>}
          </NavGroup>
        </nav>

        <div className="meta">
          <div>Роль: {isSuperuser ? "суперпользователь" : isWorker ? "сотрудник" : role || "—"}</div>
          <button
            type="button"
            className="secondary"
            style={{ marginTop: "0.75rem", width: "100%" }}
            onClick={() => {
              clearSession();
              nav("/login", { replace: true });
            }}
          >
            Выйти
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
