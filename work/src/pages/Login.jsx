import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { hasProductAccess, hasValidSession, loginWorker, setSession } from "../api.js";
import {
  formatPhoneMask,
  formatPinMask,
  normalizePhoneRu,
  pinDigits,
} from "../utils/masks.js";

export default function Login() {
  const nav = useNavigate();
  const [phone, setPhone] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (hasValidSession() && hasProductAccess()) {
    return <Navigate to="/for-order" replace />;
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const norm = normalizePhoneRu(phone);
      const p = pinDigits(pin);
      if (!norm) {
        setError("Укажите корректный номер телефона");
        setLoading(false);
        return;
      }
      if (p.length !== 6) {
        setError("PIN — 6 цифр");
        setLoading(false);
        return;
      }
      const data = await loginWorker(norm, p);
      setSession(data.access_token, data.role, data.permissions);
      nav("/for-order", { replace: true });
    } catch (err) {
      setError(err.message || "Ошибка входа");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>Рабочее</h1>
        <p className="lead">Заказы, оплаты и поставки</p>
        <form className="form-stack" onSubmit={onSubmit}>
          <label>
            Телефон
            <input
              inputMode="tel"
              autoComplete="tel"
              placeholder="+7 (999) 123-45-67"
              value={phone}
              onChange={(e) => setPhone(formatPhoneMask(e.target.value))}
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
              onChange={(e) => setPin(formatPinMask(e.target.value))}
              required
            />
          </label>
          {error ? <p className="error">{error}</p> : null}
          <button type="submit" disabled={loading}>
            {loading ? "…" : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
}
