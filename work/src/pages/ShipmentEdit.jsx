import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  fetchBrandOrders,
  fetchProcurementRefs,
  fetchShipment,
  updateShipment,
} from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import { dateRu, eur, num, rub } from "../utils/money.js";

export default function ShipmentEdit() {
  const { id } = useParams();
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
  const [orders, setOrders] = useState([]);
  const [form, setForm] = useState({
    season_id: "",
    brand_id: "",
    order_id: "",
    shipped_on: "",
    amount_eur: "",
    weight_kg: "",
    eur_rub_rate: "",
    comment: "",
  });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([fetchProcurementRefs(), fetchShipment(id)])
      .then(([refsRes, row]) => {
        if (!active) return;
        setRefs(refsRes);
        setForm({
          season_id: row.season_id || "",
          brand_id: row.brand_id || "",
          order_id: row.order_id || "",
          shipped_on: row.shipped_on || "",
          amount_eur: row.amount_eur || "",
          weight_kg: row.weight_kg || "",
          eur_rub_rate: row.eur_rub_rate || "",
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
      const row = await updateShipment(id, {
        season_id: form.season_id,
        brand_id: form.brand_id,
        order_id: form.order_id || null,
        clear_order: !form.order_id,
        shipped_on: form.shipped_on,
        amount_eur: form.amount_eur,
        weight_kg: form.weight_kg || null,
        eur_rub_rate: form.eur_rub_rate || null,
        comment: form.comment,
      });
      nav(`/shipments/${row.id}`, { replace: true });
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
      <Link to={`/shipments/${id}`} className="back-link">
        ← К поставке
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
                {dateRu(o.ordered_on)} · {eur(o.amount_eur)} · осталось {eur(o.balance_to_ship_eur)}
              </option>
            ))}
          </select>
        </label>

        <label>
          Дата поставки
          <input
            type="date"
            value={form.shipped_on}
            onChange={(e) => set("shipped_on", e.target.value)}
            required
          />
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
          Вес, кг
          <input
            type="number"
            step="0.001"
            min="0"
            inputMode="decimal"
            value={form.weight_kg}
            onChange={(e) => set("weight_kg", e.target.value)}
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
          <input value={form.comment} onChange={(e) => set("comment", e.target.value)} />
        </label>

        <button type="submit" disabled={busy || !canSubmit}>
          {busy ? "Сохранение…" : "Сохранить изменения"}
        </button>
      </form>
    </div>
  );
}
