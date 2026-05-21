import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import { clearSession, getRole, getToken } from "../api.js";

export default function Layout() {
  const nav = useNavigate();
  const role = getRole();
  const hasToken = !!getToken();
  const isSuperuser = role === "superuser";
  const isWorker = role === "worker";
  const hasAdminAccess = isSuperuser || isWorker;

  if (!hasToken || !hasAdminAccess) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>Админка</h1>
        {isSuperuser && (
          <NavLink end to="/" className={({ isActive }) => (isActive ? "active" : "")}>
            Статистика
          </NavLink>
        )}
        {isSuperuser && (
          <NavLink to="/campaigns" className={({ isActive }) => (isActive ? "active" : "")}>
            Рекламные ссылки
          </NavLink>
        )}
        <NavLink to="/photos" className={({ isActive }) => (isActive ? "active" : "")}>
          Фото и теги
        </NavLink>
        <NavLink to="/photo-ratings" className={({ isActive }) => (isActive ? "active" : "")}>
          Рейтинг фото
        </NavLink>
        <NavLink to="/tags" className={({ isActive }) => (isActive ? "active" : "")}>
          Справочник тегов
        </NavLink>
        <NavLink to="/tagging" className={({ isActive }) => (isActive ? "active" : "")}>
          Разметка тегов
        </NavLink>
        {isSuperuser && (
          <NavLink to="/users" className={({ isActive }) => (isActive ? "active" : "")}>
            Пользователи
          </NavLink>
        )}
        {isSuperuser && (
          <NavLink to="/fitting-requests" className={({ isActive }) => (isActive ? "active" : "")}>
            Заявки на примерку
          </NavLink>
        )}
        {(isSuperuser || isWorker) && (
          <NavLink to="/ai-ingest" className={({ isActive }) => (isActive ? "active" : "")}>
            ИИ: телефон → каталог
          </NavLink>
        )}
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
