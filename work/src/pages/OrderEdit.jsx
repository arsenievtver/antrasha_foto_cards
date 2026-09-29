import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchBrandOrder, fetchProcurementRefs, updateBrandOrder } from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import OrderLinesEditor, {
  filledOrderLines,
  newOrderLine,
  orderLinesPayload,
} from "../components/OrderLinesEditor.jsx";
import { eur, num } from "../utils/money.js";

export default function OrderEdit() {
  const { id } = useParams();
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
  const [form, setForm] = useState({
    season_id: "",
    brand_id: "",
    ordered_on: "",
    amount_eur: "",
    has_prepayment: false,
    prepayment_amount_eur: "",
    prepayment_due_on: "",
    comment: "",
  });
  const [lines, setLines] = useState([newOrderLine()]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    Promise.all([fetchProcurementRefs(), fetchBrandOrder(id)])
      .then(([refsRes, row]) => {
        if (!active) return;
        setRefs(refsRes);
        setForm({
          season_id: row.season_id || "",
          brand_id: row.brand_id || "",
          ordered_on: row.ordered_on || "",
          amount_eur: row.lines?.length ? "" : row.amount_eur || "",
          has_prepayment: Boolean(row.has_prepayment),
          prepayment_amount_eur: row.prepayment_amount_eur || "",
          prepayment_due_on: row.prepayment_due_on || "",
          comment: row.comment || "",
        });
        setLines(row.lines?.length ? row.lines.map((ln) => newOrderLine(ln)) : []);
      })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
    return () => {
      active = false;
    };
  }, [id]);

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
        prepayment_amount_eur: form.has_prepayment ? form.prepayment_amount_eur || null : null,
        prepayment_due_on: form.has_prepayment ? form.prepayment_due_on || null : null,
        comment: form.comment,
        lines: orderLinesPayload(lines),
      };
      if (!filledLines.length) {
        payload.amount_eur = form.amount_eur;
      }
      const row = await updateBrandOrder(id, payload);
      nav(`/orders/${row.id}`, { replace: true });
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="loading">Загрузка…</p>;

  const canSubmit =
    form.season_id && form.brand_id && (filledLines.length > 0 || num(form.amount_eur) > 0);
  const brands = refs?.brands || [];

  return (
    <div>
      <Link to={`/orders/${id}`} className="back-link">
        ← К заказу
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

        <label className="check-row">
          <input
            type="checkbox"
            checked={form.has_prepayment}
            onChange={(e) => set("has_prepayment", e.target.checked)}
          />
          Нужна предоплата
        </label>

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
          <input value={form.comment} onChange={(e) => set("comment", e.target.value)} />
        </label>

        <button type="submit" disabled={busy || !canSubmit}>
          {busy ? "Сохранение…" : "Сохранить изменения"}
        </button>
        {!canSubmit ? (
          <span className="field-hint">
            Нужны сезон, бренд и либо строки с суммами, либо общая сумма заказа.
          </span>
        ) : null}
      </form>
    </div>
  );
}
