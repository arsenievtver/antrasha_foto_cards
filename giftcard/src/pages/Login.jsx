import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import {
  fetchAdminMe,
  hasGiftAccess,
  hasValidSession,
  loginWorker,
  setSession,
} from "../api.js";
import { formatPhoneMask, formatPinMask, normalizePhoneRu, pinDigits } from "../utils/masks.js";

export default function Login() {
  const nav = useNavigate();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (hasValidSession() && hasGiftAccess()) {
    return <Navigate to="/" replace />;
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const normalized = normalizePhoneRu(phone);
      const pinValue = pinDigits(pin);
      if (!normalized) {
        setError("Укажите корректный номер телефона");
        return;
      }
      if (pinValue.length !== 6) {
        setError("PIN — 6 цифр");
        return;
      }
      const data = await loginWorker(normalized, pinValue);
      setSession(data.access_token, data.role, data.permissions);
      try {
        const me = await fetchAdminMe();
        if (me.display_name) setSession(data.access_token, data.role, data.permissions, me.display_name);
      } catch {
        /* имя подставится пустым, сотрудник введёт сам */
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
      <div className="login-card">
        <h1>Сертификаты</h1>
        <p className="lead">Вход для сотрудников</p>
        <form className="form-stack" onSubmit={onSubmit}>
          <label>
            Телефон
            <input
              inputMode="tel"
              autoComplete="tel"
              placeholder="+7 (999) 123-45-67"
              value={phone}
              onChange={(event) => setPhone(formatPhoneMask(event.target.value))}
              required
            />
          </label>
          <label>
            PIN (6 цифр)
            <input
              inputMode="numeric"
              autoComplete="current-password"
              placeholder="•••-•••"
              value={pin}
              onChange={(event) => setPin(formatPinMask(event.target.value))}
              required
            />
          </label>
          {error ? <p className="error">{error}</p> : null}
          <button type="submit" disabled={loading}>
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
