import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  fetchBrandOrders,
  fetchPayment,
  fetchProcurementRefs,
  updatePayment,
} from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import { dateRu, eur, num } from "../utils/money.js";

export default function PaymentEdit() {
  const { id } = useParams();
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
  const [orders, setOrders] = useState([]);
  const [form, setForm] = useState({
    season_id: "",
    brand_id: "",
    order_id: "",
    paid_on: "",
    kind: "main",
    amount_eur: "",
    comment: "",
  });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([fetchProcurementRefs(), fetchPayment(id)])
      .then(([refsRes, row]) => {
        if (!active) return;
        setRefs(refsRes);
        setForm({
          season_id: row.season_id || "",
          brand_id: row.brand_id || "",
          order_id: row.order_id || "",
          paid_on: row.paid_on || "",
          kind: row.kind || "main",
          amount_eur: row.amount_eur || "",
          comment: row.comment || "",
        });
      })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
    return () => {
      active = false;
    };
  }, [id]);

  useEffect(() => {
    if (!form.season_id || !form.brand_id) {
      setOrders([]);
      return;
    }
    fetchBrandOrders({ season_id: form.season_id, brand_id: form.brand_id, limit: 200 })
      .then((res) => setOrders(res.items || []))
      .catch((e) => setErr(e.message));
  }, [form.season_id, form.brand_id]);

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
      const row = await updatePayment(id, {
        season_id: form.season_id,
        brand_id: form.brand_id,
        order_id: form.order_id || null,
        clear_order: !form.order_id,
        paid_on: form.paid_on,
        kind: form.kind,
        amount_eur: form.amount_eur,
        comment: form.comment,
      });
      nav(`/payments/${row.id}`, { replace: true });
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="loading">Загрузка…</p>;

  const canSubmit = form.season_id && form.brand_id && num(form.amount_eur) > 0;
  const brands = refs?.brands || [];

  return (
    <div>
      <Link to={`/payments/${id}`} className="back-link">
        ← К оплате
      </Link>
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
          onChange={(brandId) => set("brand_id", brandId)}
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
                {dateRu(o.ordered_on)} · {eur(o.amount_eur)} · остаток {eur(o.balance_to_pay_eur)}
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
          Комментарий
          <input value={form.comment} onChange={(e) => set("comment", e.target.value)} />
        </label>

        <button type="submit" disabled={busy || !canSubmit}>
          {busy ? "Сохранение…" : "Сохранить изменения"}
        </button>
      </form>
    </div>
  );
}
