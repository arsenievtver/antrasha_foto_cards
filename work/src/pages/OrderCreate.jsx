import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createBrandOrder, fetchBrandOrders, fetchProcurementRefs } from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import OrderLinesEditor, {
  filledOrderLines,
  newOrderLine,
  orderLinesPayload,
} from "../components/OrderLinesEditor.jsx";
import { eur, num, today } from "../utils/money.js";

const EMPTY = {
  season_id: "",
  brand_id: "",
  ordered_on: today(),
  amount_eur: "",
  has_prepayment: false,
  prepayment_amount_eur: "",
  prepayment_due_on: "",
  comment: "",
};

export default function OrderCreate() {
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [lines, setLines] = useState([newOrderLine()]);
  const [existingOrder, setExistingOrder] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchProcurementRefs()
      .then(setRefs)
      .catch((e) => setErr(e.message));
  }, []);

  useEffect(() => {
    if (!form.season_id || !form.brand_id) {
      setExistingOrder(null);
      return;
    }
    let active = true;
    fetchBrandOrders({ season_id: form.season_id, brand_id: form.brand_id, limit: 1 })
      .then((res) => active && setExistingOrder(res.items?.[0] || null))
      .catch((e) => active && setErr(e.message));
    return () => {
      active = false;
    };
  }, [form.season_id, form.brand_id]);

  const filledLines = filledOrderLines(lines);
  const linesTotal = filledLines.reduce((acc, ln) => acc + num(ln.amount_eur), 0);

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const payload = {
        season_id: form.season_id,
        brand_id: form.brand_id,
        ordered_on: form.ordered_on || null,
        has_prepayment: form.has_prepayment,
        prepayment_amount_eur: form.has_prepayment
          ? form.prepayment_amount_eur || null
          : null,
        prepayment_due_on: form.has_prepayment ? form.prepayment_due_on || null : null,
        comment: form.comment.trim() || null,
        lines: orderLinesPayload(lines),
      };
      if (!filledLines.length) {
        payload.amount_eur = form.amount_eur;
      }
      const row = await createBrandOrder(payload);
      nav(`/orders/${row.id}`, { replace: true });
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  const canSubmit =
    !existingOrder &&
    form.season_id &&
    form.brand_id &&
    (filledLines.length > 0 || num(form.amount_eur) > 0);
  const brands = refs?.brands || [];

  return (
    <div>
      <Link to="/orders" className="back-link">
        ← Заказы
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

        {existingOrder ? (
          <p className="field-hint">
            Заказ этого бренда на сезон уже есть ({eur(existingOrder.amount_eur)}).
            Мужское и женское — строки одного заказа:{" "}
            <Link to={`/orders/${existingOrder.id}/edit`}>дополнить заказ</Link>
          </p>
        ) : null}

        <label>
          Дата заказа
          <input
            type="date"
            value={form.ordered_on}
            onChange={(e) => set("ordered_on", e.target.value)}
          />
        </label>

        <p className="section-title" style={{ marginTop: 0 }}>
          Строки заказа
        </p>
        {lines.length === 0 ? (
          <p className="field-hint">
            Строк нет — укажите общую сумму заказа ниже.
          </p>
        ) : null}
        <OrderLinesEditor
          categories={refs?.categories || []}
          seasonId={form.season_id}
          lines={lines}
          setLines={setLines}
        />
        {filledLines.length > 0 ? (
          <p className="field-hint">
            Сумма заказа: <strong>{eur(linesTotal)}</strong>
          </p>
        ) : (
          <label>
            Сумма заказа, €
            <input
              type="number"
              step="0.01"
              min="0"
              inputMode="decimal"
              value={form.amount_eur}
              onChange={(e) => set("amount_eur", e.target.value)}
              required
            />
            <span className="field-hint">
              Можно сохранить без строк — только общую сумму (архив / исключения).
            </span>
          </label>
        )}

        <div className="form-switch-row">
          <div className="form-switch-row__text">
            <div className="form-switch-row__label">Нужна предоплата</div>
          </div>
          <button
            type="button"
            className="switch-toggle"
            role="switch"
            aria-checked={form.has_prepayment}
            aria-label="Нужна предоплата"
            onClick={() => set("has_prepayment", !form.has_prepayment)}
          >
            <span className="switch-thumb" aria-hidden />
          </button>
        </div>

        {form.has_prepayment ? (
          <>
            <label>
              Сумма предоплаты, €
              <input
                type="number"
                step="0.01"
                min="0"
                inputMode="decimal"
                value={form.prepayment_amount_eur}
                onChange={(e) => set("prepayment_amount_eur", e.target.value)}
                required
              />
            </label>
            <label>
              Срок предоплаты
              <input
                type="date"
                value={form.prepayment_due_on}
                onChange={(e) => set("prepayment_due_on", e.target.value)}
              />
            </label>
          </>
        ) : null}

        <label>
          Комментарий к заказу
          <input
            value={form.comment}
            onChange={(e) => set("comment", e.target.value)}
            placeholder="Условия, сроки"
          />
        </label>

        <button type="submit" disabled={busy || !canSubmit}>
          {busy ? "Создание…" : "Создать заказ"}
        </button>
        {!canSubmit && !existingOrder ? (
          <span className="field-hint">
            Нужны сезон, бренд и либо строки с суммами, либо общая сумма заказа.
          </span>
        ) : null}
      </form>
    </div>
  );
}
