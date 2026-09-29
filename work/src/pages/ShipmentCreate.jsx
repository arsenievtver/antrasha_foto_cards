import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createShipment, fetchProcurementRefs } from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import PairOrderHint from "../components/PairOrderHint.jsx";
import ShipmentLogisticsSection from "../components/ShipmentLogisticsSection.jsx";
import { num, rub, today } from "../utils/money.js";

const EMPTY = {
  season_id: "",
  brand_id: "",
  shipped_on: today(),
  amount_eur: "",
  weight_kg: "",
  eur_rub_rate: "",
  comment: "",
  logistics_amount_rub: "",
  logistics_paid_on: "",
  is_delivered: true,
};

export default function ShipmentCreate() {
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
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

  const amountRub = useMemo(() => {
    if (!form.amount_eur || !form.eur_rub_rate) return null;
    return num(form.amount_eur) * num(form.eur_rub_rate);
  }, [form.amount_eur, form.eur_rub_rate]);

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const row = await createShipment({
        season_id: form.season_id,
        brand_id: form.brand_id,
        shipped_on: form.shipped_on,
        amount_eur: form.amount_eur,
        weight_kg: form.weight_kg || null,
        eur_rub_rate: form.eur_rub_rate || null,
        comment: form.comment.trim() || null,
        logistics_amount_rub: form.logistics_amount_rub || null,
        logistics_paid_on: form.logistics_paid_on || null,
        is_delivered: form.is_delivered,
      });
      nav(`/shipments/${row.id}`, { replace: true });
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
      <Link to="/shipments" className="back-link">
        ← Поставки
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
          onChange={(id) => set("brand_id", id)}
          onBrandsChange={(next) => setRefs((r) => (r ? { ...r, brands: next } : r))}
          required
        />

        <PairOrderHint seasonId={form.season_id} brandId={form.brand_id} balance="ship" />

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

        <ShipmentLogisticsSection form={form} setField={set} />

        <label>
          Комментарий
          <input
            value={form.comment}
            onChange={(e) => set("comment", e.target.value)}
            placeholder="Инвойс, перевозчик"
          />
        </label>

        <button type="submit" disabled={busy || !canSubmit}>
          {busy ? "Сохранение…" : "Сохранить"}
        </button>
      </form>
    </div>
  );
}
