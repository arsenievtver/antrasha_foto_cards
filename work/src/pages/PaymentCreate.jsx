import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createPayment, fetchProcurementRefs } from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import PairOrderHint from "../components/PairOrderHint.jsx";
import { num, today } from "../utils/money.js";

const EMPTY = {
  season_id: "",
  brand_id: "",
  paid_on: today(),
  kind: "main",
  amount_eur: "",
  comment: "",
};

export default function PaymentCreate() {
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchProcurementRefs()
      .then(setRefs)
      .catch((e) => setErr(e.message));
  }, []);

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const row = await createPayment({
        season_id: form.season_id,
        brand_id: form.brand_id,
        paid_on: form.paid_on,
        kind: form.kind,
        amount_eur: form.amount_eur,
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

        <PairOrderHint seasonId={form.season_id} brandId={form.brand_id} balance="pay" />

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
