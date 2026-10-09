import { useCallback, useEffect, useState } from "react";
import { fetchWelcomeGiftSettings, saveWelcomeGiftSettings } from "../api.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

export default function WelcomeGift() {
  const [enabled, setEnabled] = useState(false);
  const [validFrom, setValidFrom] = useState(today());
  const [validTo, setValidTo] = useState("");
  const [nominal, setNominal] = useState("");
  const [periodDays, setPeriodDays] = useState("30");
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const res = await fetchWelcomeGiftSettings();
      setEnabled(Boolean(res.enabled));
      setValidFrom(res.valid_from || "");
      setValidTo(res.valid_to || "");
      setNominal(res.nominal ? String(res.nominal) : "");
      setPeriodDays(String(res.period_days || 30));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    setSaved("");
    try {
      await saveWelcomeGiftSettings({
        enabled,
        valid_from: validFrom || null,
        valid_to: validTo || null,
        nominal: Number(nominal || 0),
        period_days: Number(periodDays || 30),
      });
      setSaved("Сохранено");
      await reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Сертификат за приложение</h2>
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Новому клиенту один раз выписывается сертификат, если он зарегистрировался
        в период акции, открыл установленное приложение и включил уведомления.
        Пустая дата «по» — акция без конца, пока свитч включён. Уже зарегистрированные
        до начала периода сертификат не получают. Ссылка уходит push-уведомлением
        и появляется в профиле.
      </p>

      {err ? <p className="error">{err}</p> : null}
      {saved ? <p style={{ color: "var(--muted)" }}>{saved}</p> : null}

      <div className="card" style={{ maxWidth: 560 }}>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : (
          <form className="form-stack" onSubmit={onSubmit}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <button
                type="button"
                className="switch-toggle"
                role="switch"
                aria-checked={enabled}
                aria-label="Автоматическая выписка"
                onClick={() => setEnabled((v) => !v)}
              >
                <span className="switch-thumb" aria-hidden />
              </button>
              <span>{enabled ? "Автоматическая выписка включена" : "Автоматическая выписка выключена"}</span>
            </div>
            <label>
              С даты
              <input
                type="date"
                value={validFrom}
                onChange={(e) => setValidFrom(e.target.value)}
                required={enabled}
              />
            </label>
            <label>
              По дату
              <input
                type="date"
                value={validTo}
                onChange={(e) => setValidTo(e.target.value)}
              />
              <span className="field-hint">
                Можно оставить пустым — акция действует с даты начала, пока её не выключат.
              </span>
            </label>
            <label>
              Сумма, ₽
              <input
                type="number"
                min="0"
                step="1"
                value={nominal}
                onChange={(e) => setNominal(e.target.value)}
                placeholder="3000"
                required={enabled}
              />
            </label>
            <label>
              Срок действия, дней
              <input
                type="number"
                min="1"
                step="1"
                value={periodDays}
                onChange={(e) => setPeriodDays(e.target.value)}
                required
              />
            </label>
            <button type="submit" disabled={busy}>
              {busy ? "Сохранение…" : "Сохранить"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
