import { useCallback, useEffect, useState } from "react";
import { createFxRate, deleteFxRate, fetchFxRates, updateFxRate } from "../api.js";
import { dateRu, rate as fmtRate } from "../utils/money.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function periodLabel(row) {
  const from = dateRu(row.valid_from);
  if (!row.valid_to) return `${from} — ∞`;
  return `${from} — ${dateRu(row.valid_to)}`;
}

function emptyForm() {
  return {
    validFrom: today(),
    validTo: "",
    value: "",
    comment: "",
  };
}

export default function FxRates() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
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

  function resetForm() {
    setEditingId(null);
    setForm(emptyForm());
  }

  function startEdit(row) {
    setEditingId(row.id);
    setForm({
      validFrom: row.valid_from,
      validTo: row.valid_to || "",
      value: String(row.eur_rub),
      comment: row.comment || "",
    });
    setErr("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      if (editingId) {
        const body = {
          valid_from: form.validFrom,
          eur_rub: form.value,
          // Пустая строка сбрасывает комментарий (null на PATCH игнорируется).
          comment: form.comment.trim(),
        };
        if (form.validTo) {
          body.valid_to = form.validTo;
        } else {
          body.clear_valid_to = true;
        }
        await updateFxRate(editingId, body);
      } else {
        await createFxRate({
          valid_from: form.validFrom,
          valid_to: form.validTo || null,
          eur_rub: form.value,
          comment: form.comment.trim() || null,
        });
      }
      resetForm();
      await reload();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(row) {
    if (!window.confirm(`Удалить курс за период ${periodLabel(row)}?`)) return;
    setErr("");
    try {
      await deleteFxRate(row.id);
      if (editingId === row.id) resetForm();
      await reload();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  const isEditing = Boolean(editingId);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Курс EUR/RUB</h2>
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Курс задаётся на период. При создании заказа, оплаты или поставки в форму
        подставляется курс, чей период покрывает дату документа. Сам документ
        сохраняет свой курс — правка справочника не меняет уже посчитанные рубли.
        Периоды не должны пересекаться; пустой «по» = бессрочно. Чтобы повысить
        курс: закройте текущий период датой «по», затем добавьте новый со следующего
        дня.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ maxWidth: 560, marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>
          {isEditing ? "Редактировать период" : "Новый курс на период"}
        </h3>
        <form className="form-stack" onSubmit={onSubmit}>
          <label>
            С даты
            <input
              type="date"
              value={form.validFrom}
              onChange={(e) => setForm((f) => ({ ...f, validFrom: e.target.value }))}
              required
            />
          </label>
          <label>
            По дату
            <input
              type="date"
              value={form.validTo}
              onChange={(e) => setForm((f) => ({ ...f, validTo: e.target.value }))}
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
              value={form.value}
              onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
              placeholder="105.5"
              required
            />
          </label>
          <label>
            Комментарий
            <input
              value={form.comment}
              onChange={(e) => setForm((f) => ({ ...f, comment: e.target.value }))}
              placeholder="Курс банка на сезон / месяц"
            />
          </label>
          <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            <button type="submit" disabled={busy || !form.value || !form.validFrom}>
              {busy ? "Сохранение…" : isEditing ? "Сохранить" : "Добавить курс"}
            </button>
            {isEditing ? (
              <button type="button" className="secondary" disabled={busy} onClick={resetForm}>
                Отмена
              </button>
            ) : null}
          </div>
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
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => startEdit(row)}
                      disabled={busy}
                      style={{ marginRight: "0.35rem" }}
                    >
                      Изменить
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => onDelete(row)}
                      disabled={busy}
                    >
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
