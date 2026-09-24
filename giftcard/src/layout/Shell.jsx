import { Outlet, useNavigate } from "react-router-dom";
import { clearSession } from "../api.js";

export default function Shell() {
  const nav = useNavigate();

  function logout() {
    clearSession();
    nav("/login", { replace: true });
  }

  return (
    <div className="desk-shell">
      <header className="desk-header">
        <h1>Сертификаты ANTRASHA</h1>
        <div className="desk-header-actions">
          <button type="button" className="secondary" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>
      <main className="desk-main">
        <Outlet />
      </main>
    </div>
  );
}
