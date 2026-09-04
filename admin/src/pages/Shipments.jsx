import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createShipment,
  deleteShipment,
  fetchBrandOrders,
  fetchProcurementRefs,
  fetchShipments,
  updateShipment,
} from "../api.js";
import { dateRu, eur, kg, num, rate as fmtRate, rub } from "../utils/money.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

const EMPTY_FORM = {
  season_id: "",
  brand_id: "",
  order_id: "",
  shipped_on: today(),
  amount_eur: "",
  weight_kg: "",
  eur_rub_rate: "",
  comment: "",
  logistics_amount_rub: "",
  logistics_paid_on: "",
  is_delivered: true,
};

export default function Shipments() {
  const [refs, setRefs] = useState(null);
  const [orders, setOrders] = useState([]);
  const [data, setData] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({ season_id: "", brand_id: "" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toggleId, setToggleId] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setData(await fetchShipments(filters));
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
      if (field === "season_id" || field === "brand_id") next.order_id = "";
      return next;
    });
  }

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await createShipment({
        season_id: form.season_id,
        brand_id: form.brand_id,
        order_id: form.order_id || null,
        shipped_on: form.shipped_on,
        amount_eur: form.amount_eur,
        weight_kg: form.weight_kg || null,
        eur_rub_rate: form.eur_rub_rate || null,
        comment: form.comment.trim() || null,
        logistics_amount_rub: form.logistics_amount_rub || null,
        logistics_paid_on: form.logistics_paid_on || null,
        is_delivered: form.is_delivered,
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

  async function onToggleDelivered(row) {
    setToggleId(row.id);
    setErr("");
    try {
      await updateShipment(row.id, { is_delivered: !row.is_delivered });
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setToggleId(null);
    }
  }

  async function onDelete(row) {
    if (
      !window.confirm(
        `Удалить поставку ${eur(row.amount_eur)} от ${dateRu(row.shipped_on)}?`,
      )
    )
      return;
    setErr("");
    try {
      await deleteShipment(row.id);
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  const canSubmit = form.season_id && form.brand_id && num(form.amount_eur) > 0;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Поставки</h2>
      <p style={{ color: "var(--muted)", maxWidth: 760 }}>
        Что и когда бренд отгрузил: сумма в евро и вес. Логистика (рубли и дата оплаты) хранится
        здесь отдельно от оплат бренду. Пока поставка «в пути», она не уменьшает «осталось
        поставить» по заказу.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новая поставка</h3>
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
                    {dateRu(o.ordered_on)} · {eur(o.amount_eur)} · осталось{" "}
                    {eur(o.balance_to_ship_eur)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
            <label style={{ flex: "1 1 150px" }}>
              Дата поставки
              <input
                type="date"
                value={form.shipped_on}
                onChange={(e) => set("shipped_on", e.target.value)}
                required
              />
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
              Вес, кг
              <input
                type="number"
                step="0.001"
                min="0"
                value={form.weight_kg}
                onChange={(e) => set("weight_kg", e.target.value)}
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

          <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
            <label style={{ flex: "1 1 150px" }}>
              Сумма логистики, ₽
              <input
                type="number"
                step="0.01"
                min="0"
                value={form.logistics_amount_rub}
                onChange={(e) => set("logistics_amount_rub", e.target.value)}
              />
            </label>
            <label style={{ flex: "1 1 150px" }}>
              Дата оплаты логистики
              <input
                type="date"
                value={form.logistics_paid_on}
                onChange={(e) => set("logistics_paid_on", e.target.value)}
              />
            </label>
            <div style={{ flex: "1 1 180px", paddingBottom: "0.35rem" }}>
              <span
                style={{
                  display: "block",
                  fontSize: "0.85rem",
                  color: "var(--muted)",
                  marginBottom: "0.35rem",
                }}
              >
                Статус
              </span>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <button
                  type="button"
                  className="switch-toggle"
                  role="switch"
                  aria-checked={form.is_delivered}
                  aria-label={form.is_delivered ? "Поставлено" : "В пути"}
                  onClick={() => set("is_delivered", !form.is_delivered)}
                >
                  <span className="switch-thumb" aria-hidden />
                </button>
                <span>{form.is_delivered ? "Поставлено" : "В пути"}</span>
              </div>
            </div>
          </div>

          <label>
            Комментарий
            <input
              value={form.comment}
              onChange={(e) => set("comment", e.target.value)}
              placeholder="Номер инвойса, перевозчик"
            />
          </label>

          <button type="submit" disabled={busy || !canSubmit}>
            {busy ? "Сохранение…" : "Добавить поставку"}
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
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Поставки ({data.total})</h3>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !data.items.length ? (
          <p style={{ color: "var(--muted)" }}>Поставок нет.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Сезон</th>
                <th>Бренд</th>
                <th>Сумма, €</th>
                <th>Вес</th>
                <th>Курс</th>
                <th>В рублях</th>
                <th>Логистика</th>
                <th>Оплата лог.</th>
                <th>Статус</th>
                <th>Заказ</th>
                <th>Комментарий</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td>{dateRu(row.shipped_on)}</td>
                  <td>{row.season_name}</td>
                  <td>{row.brand_name}</td>
                  <td>{eur(row.amount_eur)}</td>
                  <td>{kg(row.weight_kg)}</td>
                  <td>{fmtRate(row.eur_rub_rate)}</td>
                  <td>{rub(row.amount_rub)}</td>
                  <td>{rub(row.logistics_amount_rub)}</td>
                  <td>{row.logistics_paid_on ? dateRu(row.logistics_paid_on) : "—"}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                      <button
                        type="button"
                        className="switch-toggle"
                        role="switch"
                        aria-checked={row.is_delivered}
                        aria-label={row.is_delivered ? "Поставлено" : "В пути"}
                        disabled={toggleId === row.id}
                        onClick={() => onToggleDelivered(row)}
                      >
                        <span className="switch-thumb" aria-hidden />
                      </button>
                      <span style={{ fontSize: "0.85rem" }}>
                        {row.is_delivered ? "Поставлено" : "В пути"}
                      </span>
                    </div>
                  </td>
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
