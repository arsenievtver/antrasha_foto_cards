import { Children } from "react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { clearSession, getRole, hasValidSession } from "../api.js";

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

  if (!hasValidSession() || !hasAdminAccess) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar__brand">Админка</div>

        <nav className="sidebar__nav">
          {isSuperuser && (
            <NavGroup title="Обзор">
              <NavItem end to="/">
                Статистика
              </NavItem>
            </NavGroup>
          )}

          <NavGroup title="Клиенты">
            {isSuperuser && <NavItem to="/users">Пользователи</NavItem>}
            {isSuperuser && <NavItem to="/fitting-requests">Заявки на примерку</NavItem>}
          </NavGroup>

          <NavGroup title="Фото">
            <NavItem to="/photos">Фото и теги</NavItem>
            <NavItem to="/photo-ratings">Рейтинг фото</NavItem>
            <NavItem to="/tags">Справочник тегов</NavItem>
            <NavItem to="/tagging">Разметка тегов</NavItem>
            {(isSuperuser || isWorker) && (
              <NavItem to="/ai-ingest">ИИ: телефон → каталог</NavItem>
            )}
          </NavGroup>

          <NavGroup title="Реклама">
            {isSuperuser && <NavItem to="/campaigns">Рекламные ссылки</NavItem>}
            {isSuperuser && <NavItem to="/promo-banners">Баннеры на главной</NavItem>}
          </NavGroup>

          <NavGroup title="Товар">
            {isSuperuser && <NavItem to="/seasons">Сезоны</NavItem>}
            {isSuperuser && <NavItem to="/brands">Бренды</NavItem>}
            {isSuperuser && <NavItem to="/brand-orders">Заказы брендам</NavItem>}
            {isSuperuser && <NavItem to="/payments">Оплаты</NavItem>}
            {isSuperuser && <NavItem to="/shipments">Поставки</NavItem>}
            {isSuperuser && <NavItem to="/fx-rates">Курс EUR</NavItem>}
          </NavGroup>
        </nav>

        <div className="meta">
          <div>Роль: {role || "—"}</div>
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
