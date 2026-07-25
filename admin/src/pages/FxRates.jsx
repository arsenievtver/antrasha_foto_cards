import { useCallback, useEffect, useState } from "react";
import { createFxRate, deleteFxRate, fetchFxRates } from "../api.js";
import { dateRu, rate as fmtRate } from "../utils/money.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function periodLabel(row) {
  const from = dateRu(row.valid_from);
  if (!row.valid_to) return `${from} — ∞`;
  return `${from} — ${dateRu(row.valid_to)}`;
}

export default function FxRates() {
  const [items, setItems] = useState([]);
  const [validFrom, setValidFrom] = useState(today());
  const [validTo, setValidTo] = useState("");
  const [value, setValue] = useState("");
  const [comment, setComment] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const res = await fetchFxRates();
      setItems(res.items || []);
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
    try {
      await createFxRate({
        valid_from: validFrom,
        valid_to: validTo || null,
        eur_rub: value,
        comment: comment.trim() || null,
      });
      setValue("");
      setComment("");
      setValidTo("");
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(row) {
    if (!window.confirm(`Удалить курс за период ${periodLabel(row)}?`)) return;
    setErr("");
    try {
      await deleteFxRate(row.id);
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Курс EUR/RUB</h2>
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Курс задаётся на период. При создании заказа, оплаты или поставки в форму
        подставляется курс, чей период покрывает дату документа. Сам документ
        сохраняет свой курс — правка справочника не меняет уже посчитанные рубли.
        Периоды не должны пересекаться; пустой «по» = бессрочно.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ maxWidth: 560, marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новый курс на период</h3>
        <form className="form-stack" onSubmit={onSubmit}>
          <label>
            С даты
            <input
              type="date"
              value={validFrom}
              onChange={(e) => setValidFrom(e.target.value)}
              required
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
              Можно оставить пустым — курс действует с даты начала без срока.
            </span>
          </label>
          <label>
            Рублей за 1 евро
            <input
              type="number"
              step="0.0001"
              min="0"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="105.5"
              required
            />
          </label>
          <label>
            Комментарий
            <input
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Курс банка на сезон / месяц"
            />
          </label>
          <button type="submit" disabled={busy || !value || !validFrom}>
            {busy ? "Сохранение…" : "Добавить курс"}
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Периоды курсов</h3>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !items.length ? (
          <p style={{ color: "var(--muted)" }}>Курсы пока не заданы.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Период</th>
                <th>EUR/RUB</th>
                <th>Комментарий</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id}>
                  <td>{periodLabel(row)}</td>
                  <td>{fmtRate(row.eur_rub)}</td>
                  <td>{row.comment || "—"}</td>
                  <td>
                    <button type="button" className="secondary" onClick={() => onDelete(row)}>
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
