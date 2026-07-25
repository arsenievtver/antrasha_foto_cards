import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createPayment,
  deletePayment,
  fetchBrandOrders,
  fetchPayments,
  fetchProcurementRefs,
} from "../api.js";
import { dateRu, eur, num, paymentKindLabel, rate as fmtRate, rub } from "../utils/money.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

const EMPTY_FORM = {
  season_id: "",
  brand_id: "",
  order_id: "",
  paid_on: today(),
  kind: "main",
  amount_eur: "",
  eur_rub_rate: "",
  comment: "",
};

export default function Payments() {
  const [refs, setRefs] = useState(null);
  const [orders, setOrders] = useState([]);
  const [data, setData] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({ season_id: "", brand_id: "", kind: "" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setData(await fetchPayments(filters));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    fetchProcurementRefs()
      .then((res) => {
        setRefs(res);
        setForm((prev) => ({
          ...prev,
          eur_rub_rate: prev.eur_rub_rate || res.latest_fx_rate?.eur_rub || "",
        }));
      })
      .catch((e) => setErr(e.message));
  }, []);

  /** Заказы для привязки платежа — только по выбранной паре сезон+бренд. */
  useEffect(() => {
    if (!form.season_id || !form.brand_id) {
      setOrders([]);
      return;
    }
    fetchBrandOrders({ season_id: form.season_id, brand_id: form.brand_id, limit: 200 })
      .then((res) => setOrders(res.items || []))
      .catch((e) => setErr(e.message));
  }, [form.season_id, form.brand_id]);

  const amountRub = useMemo(() => {
    if (!form.amount_eur || !form.eur_rub_rate) return null;
    return num(form.amount_eur) * num(form.eur_rub_rate);
  }, [form.amount_eur, form.eur_rub_rate]);

  function set(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value };
      // Заказ привязан к конкретной паре сезон+бренд — при их смене сбрасываем.
      if (field === "season_id" || field === "brand_id") next.order_id = "";
      return next;
    });
  }

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await createPayment({
        season_id: form.season_id,
        brand_id: form.brand_id,
        order_id: form.order_id || null,
        paid_on: form.paid_on,
        kind: form.kind,
        amount_eur: form.amount_eur,
        eur_rub_rate: form.eur_rub_rate || null,
        comment: form.comment.trim() || null,
      });
      setForm({
        ...EMPTY_FORM,
        season_id: form.season_id,
        brand_id: form.brand_id,
        eur_rub_rate: refs?.latest_fx_rate?.eur_rub || "",
      });
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(row) {
    if (!window.confirm(`Удалить оплату ${eur(row.amount_eur)} от ${dateRu(row.paid_on)}?`))
      return;
    setErr("");
    try {
      await deletePayment(row.id);
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  const canSubmit = form.season_id && form.brand_id && num(form.amount_eur) > 0;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Оплаты</h2>
      <p style={{ color: "var(--muted)", maxWidth: 760 }}>
        Сумма в евро пересчитывается в рубли по курсу на дату оплаты и сохраняется в
        документе. Привязка к заказу необязательна, но именно она показывает, сколько
        ещё должны по конкретному заказу.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новая оплата</h3>
        <form className="form-stack" onSubmit={onCreate}>
          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <label style={{ flex: "1 1 200px" }}>
              Сезон
              <select
                value={form.season_id}
                onChange={(e) => set("season_id", e.target.value)}
                required
              >
                <option value="">— выберите —</option>
                {(refs?.seasons || []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ flex: "1 1 200px" }}>
              Бренд
              <select
                value={form.brand_id}
                onChange={(e) => set("brand_id", e.target.value)}
                required
              >
                <option value="">— выберите —</option>
                {(refs?.brands || []).map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ flex: "1 1 220px" }}>
              Заказ
              <select
                value={form.order_id}
                onChange={(e) => set("order_id", e.target.value)}
                disabled={!orders.length}
              >
                <option value="">Без привязки</option>
                {orders.map((o) => (
                  <option key={o.id} value={o.id}>
                    {dateRu(o.ordered_on)} · {eur(o.amount_eur)} · остаток{" "}
                    {eur(o.balance_to_pay_eur)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <label style={{ flex: "1 1 150px" }}>
              Дата оплаты
              <input
                type="date"
                value={form.paid_on}
                onChange={(e) => set("paid_on", e.target.value)}
                required
              />
            </label>
            <label style={{ flex: "1 1 150px" }}>
              Категория
              <select value={form.kind} onChange={(e) => set("kind", e.target.value)}>
                <option value="main">Основная</option>
                <option value="prepayment">Предоплата</option>
              </select>
            </label>
            <label style={{ flex: "1 1 150px" }}>
              Сумма, €
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.amount_eur}
                onChange={(e) => set("amount_eur", e.target.value)}
                required
              />
            </label>
            <label style={{ flex: "1 1 150px" }}>
              Курс EUR/RUB
              <input
                type="number"
                step="0.0001"
                min="0"
                value={form.eur_rub_rate}
                onChange={(e) => set("eur_rub_rate", e.target.value)}
              />
              <span className="field-hint">
                {amountRub !== null ? `Будет ${rub(amountRub)}` : "Пусто — возьмём из справочника"}
              </span>
            </label>
          </div>

          <label>
            Комментарий
            <input
              value={form.comment}
              onChange={(e) => set("comment", e.target.value)}
              placeholder="Назначение платежа, банк"
            />
          </label>

          <button type="submit" disabled={busy || !canSubmit}>
            {busy ? "Сохранение…" : "Добавить оплату"}
          </button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Фильтры</h3>
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          <label style={{ flex: "1 1 200px" }}>
            Сезон
            <select
              value={filters.season_id}
              onChange={(e) => setFilters((p) => ({ ...p, season_id: e.target.value }))}
            >
              <option value="">Все</option>
              {(refs?.seasons || []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label style={{ flex: "1 1 200px" }}>
            Бренд
            <select
              value={filters.brand_id}
              onChange={(e) => setFilters((p) => ({ ...p, brand_id: e.target.value }))}
            >
              <option value="">Все</option>
              {(refs?.brands || []).map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
          <label style={{ flex: "1 1 160px" }}>
            Категория
            <select
              value={filters.kind}
              onChange={(e) => setFilters((p) => ({ ...p, kind: e.target.value }))}
            >
              <option value="">Все</option>
              <option value="main">Основная</option>
              <option value="prepayment">Предоплата</option>
            </select>
          </label>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Оплаты ({data.total})</h3>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !data.items.length ? (
          <p style={{ color: "var(--muted)" }}>Оплат нет.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сезон</th>
                <th>Бренд</th>
                <th>Категория</th>
                <th>Сумма, €</th>
                <th>Курс</th>
                <th>В рублях</th>
                <th>Заказ</th>
                <th>Комментарий</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td>{dateRu(row.paid_on)}</td>
                  <td>{row.season_name}</td>
                  <td>{row.brand_name}</td>
                  <td>{paymentKindLabel(row.kind)}</td>
                  <td>{eur(row.amount_eur)}</td>
                  <td>{fmtRate(row.eur_rub_rate)}</td>
                  <td>{rub(row.amount_rub)}</td>
                  <td>{row.order_id ? "Привязана" : "—"}</td>
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
