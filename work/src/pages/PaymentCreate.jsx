import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  createPayment,
  fetchBrandOrders,
  fetchProcurementRefs,
} from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import { dateRu, eur, num, rub, today } from "../utils/money.js";

const EMPTY = {
  season_id: "",
  brand_id: "",
  order_id: "",
  paid_on: today(),
  kind: "main",
  amount_eur: "",
  eur_rub_rate: "",
  comment: "",
};

export default function PaymentCreate() {
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
  const [orders, setOrders] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

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

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const row = await createPayment({
        season_id: form.season_id,
        brand_id: form.brand_id,
        order_id: form.order_id || null,
        paid_on: form.paid_on,
        kind: form.kind,
        amount_eur: form.amount_eur,
        eur_rub_rate: form.eur_rub_rate || null,
        comment: form.comment.trim() || null,
      });
      nav(`/payments/${row.id}`, { replace: true });
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = form.season_id && form.brand_id && num(form.amount_eur) > 0;
  const brands = refs?.brands || [];

  return (
    <div>
      <Link to="/payments" className="back-link">
        ← Оплаты
      </Link>
      <div className="page-head">
        <h1>Новая оплата</h1>
      </div>

      {err ? <p className="error">{err}</p> : null}

      <form className="form-stack" onSubmit={onSubmit}>
        <label>
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

        <BrandSelect
          brands={brands}
          value={form.brand_id}
          onChange={(id) => set("brand_id", id)}
          onBrandsChange={(next) => setRefs((r) => (r ? { ...r, brands: next } : r))}
          required
        />

        <label>
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

        <label>
          Дата оплаты
          <input
            type="date"
            value={form.paid_on}
            onChange={(e) => set("paid_on", e.target.value)}
            required
          />
        </label>

        <label>
          Категория
          <select value={form.kind} onChange={(e) => set("kind", e.target.value)}>
            <option value="main">Основная</option>
            <option value="prepayment">Предоплата</option>
          </select>
        </label>

        <label>
          Сумма, €
          <input
            type="number"
            step="0.01"
            min="0"
            inputMode="decimal"
            value={form.amount_eur}
            onChange={(e) => set("amount_eur", e.target.value)}
            required
          />
        </label>

        <label>
          Курс EUR/RUB
          <input
            type="number"
            step="0.0001"
            min="0"
            inputMode="decimal"
            value={form.eur_rub_rate}
            onChange={(e) => set("eur_rub_rate", e.target.value)}
          />
          <span className="field-hint">
            {amountRub !== null ? `Будет ${rub(amountRub)}` : "Пусто — из справочника"}
          </span>
        </label>

        <label>
          Комментарий
          <input
            value={form.comment}
            onChange={(e) => set("comment", e.target.value)}
            placeholder="Назначение, банк"
          />
        </label>

        <button type="submit" disabled={busy || !canSubmit}>
          {busy ? "Сохранение…" : "Сохранить"}
        </button>
      </form>
    </div>
  );
}
