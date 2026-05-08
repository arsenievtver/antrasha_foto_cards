import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { getToken, loginSuperuser, loginWorker, setSession } from "../api.js";
import {
	formatPhoneMask,
	formatPinMask,
	normalizePhoneRu,
	pinDigits,
} from "../utils/masks.js";

export default function Login() {
  const nav = useNavigate();
  const [mode, setMode] = useState("superuser");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (getToken()) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (mode === "superuser") {
        const data = await loginSuperuser(username.trim(), password);
        setSession(data.access_token, data.role);
      } else {
        const norm = normalizePhoneRu(phone);
        const p = pinDigits(pin);
        if (!norm) {
          setError("Укажите корректный номер телефона");
          setLoading(false);
          return;
        }
        if (p.length !== 6) {
          setError("PIN — 6 цифр (формат •••-•••)");
          setLoading(false);
          return;
        }
        const data = await loginWorker(norm, p);
        setSession(data.access_token, data.role);
      }
      nav("/", { replace: true });
    } catch (err) {
      setError(err.message || "Ошибка входа");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Вход в админку</h2>
        <div className="tabs">
          <button
            type="button"
            className={mode === "superuser" ? "active" : ""}
            onClick={() => setMode("superuser")}
          >
            Суперпользователь
          </button>
          <button
            type="button"
            className={mode === "worker" ? "active" : ""}
            onClick={() => setMode("worker")}
          >
            Сотрудник
          </button>
        </div>
        <form className="form-stack" onSubmit={onSubmit}>
          {mode === "superuser" ? (
            <>
              <div>
                <label htmlFor="u">Логин</label>
                <input
                  id="u"
                  autoComplete="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div>
                <label htmlFor="p">Пароль</label>
                <input
                  id="p"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label htmlFor="ph">Телефон</label>
                <input
                  id="ph"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="+7 (999) 123-45-67"
                  value={phone}
                  onChange={(e) => setPhone(formatPhoneMask(e.target.value))}
                  required
                />
              </div>
              <div>
                <label htmlFor="pin">PIN (6 цифр)</label>
                <input
                  id="pin"
                  inputMode="numeric"
                  autoComplete="current-password"
                  placeholder="•••-•••"
                  value={pin}
                  onChange={(e) => setPin(formatPinMask(e.target.value))}
                  required
                />
              </div>
            </>
          )}
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={loading}>
            {loading ? "…" : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
