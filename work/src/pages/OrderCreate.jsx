import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createBrandOrder, fetchProcurementRefs } from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import CategoryInsightControl from "../components/CategoryInsightControl.jsx";
import { eur, num, today } from "../utils/money.js";
import { getFormCategories, normalizeCategoryId } from "../utils/procurementCategories.js";

const EMPTY = {
  season_id: "",
  brand_id: "",
  gender: "",
  ordered_on: today(),
  amount_eur: "",
  has_prepayment: false,
  prepayment_amount_eur: "",
  prepayment_due_on: "",
  comment: "",
};

function newLine() {
  return { key: crypto.randomUUID(), category_id: "", amount_eur: "", comment: "" };
}

export default function OrderCreate() {
  const nav = useNavigate();
  const [refs, setRefs] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [lines, setLines] = useState([newLine()]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchProcurementRefs()
      .then(setRefs)
      .catch((e) => setErr(e.message));
  }, []);

  const formCategories = useMemo(() => {
    return getFormCategories(refs?.categories || [], form.gender);
  }, [refs, form.gender]);

  const linesTotal = useMemo(
    () => lines.reduce((acc, ln) => acc + num(ln.amount_eur), 0),
    [lines],
  );

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function setLine(key, field, value) {
    setLines((prev) =>
      prev.map((ln) => (ln.key === key ? { ...ln, [field]: value } : ln)),
    );
  }

  const filledLines = lines.filter((ln) => ln.category_id && num(ln.amount_eur) > 0);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const payload = {
        season_id: form.season_id,
        brand_id: form.brand_id,
        gender: form.gender || null,
        ordered_on: form.ordered_on || null,
        has_prepayment: form.has_prepayment,
        prepayment_amount_eur: form.has_prepayment
          ? form.prepayment_amount_eur || null
          : null,
        prepayment_due_on: form.has_prepayment ? form.prepayment_due_on || null : null,
        comment: form.comment.trim() || null,
        lines: filledLines.map((ln) => ({
          category_id: normalizeCategoryId(ln.category_id, form.gender),
          amount_eur: ln.amount_eur,
          comment: ln.comment.trim() || null,
        })),
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
    form.season_id && form.brand_id && (filledLines.length > 0 || num(form.amount_eur) > 0);
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

        <label>
          Пол
          <select value={form.gender} onChange={(e) => set("gender", e.target.value)}>
            <option value="">Не указан</option>
            <option value="men">Мужской</option>
            <option value="women">Женский</option>
            <option value="mixed">Смешанный</option>
          </select>
          <span className="field-hint">Фильтрует список категорий ниже</span>
        </label>

        <label>
          Дата заказа
          <input
            type="date"
            value={form.ordered_on}
            onChange={(e) => set("ordered_on", e.target.value)}
          />
        </label>

        <p className="section-title" style={{ marginTop: 0 }}>
          Категории
        </p>
        {lines.length === 0 ? (
          <p className="field-hint">
            Категории не выбраны — укажите общую сумму заказа ниже.
          </p>
        ) : null}
        {lines.map((ln) => {
          const selectedCat = formCategories.find((c) => String(c.id) === String(ln.category_id));
          return (
          <div key={ln.key} className="line-card">
            <CategoryInsightControl
              categoryId={ln.category_id}
              seasonId={form.season_id}
              categoryName={selectedCat?.name}
            />
            <label>
              Категория
              <select
                value={ln.category_id}
                onChange={(e) => setLine(ln.key, "category_id", e.target.value)}
              >
                <option value="">— выберите —</option>
                {formCategories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Сумма, €
              <input
                type="number"
                step="0.01"
                min="0"
                inputMode="decimal"
                value={ln.amount_eur}
                onChange={(e) => setLine(ln.key, "amount_eur", e.target.value)}
              />
            </label>
            <label>
              Комментарий
              <input
                value={ln.comment}
                onChange={(e) => setLine(ln.key, "comment", e.target.value)}
              />
            </label>
            <button
              type="button"
              className="secondary"
              onClick={() => setLines((prev) => prev.filter((x) => x.key !== ln.key))}
            >
              Убрать
            </button>
          </div>
          );
        })}
        <button
          type="button"
          className="secondary"
          onClick={() => setLines((prev) => [...prev, newLine()])}
        >
          + Категория
        </button>
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
              Можно сохранить без категорий — только общую сумму (архив / исключения).
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
          <input
            value={form.comment}
            onChange={(e) => set("comment", e.target.value)}
            placeholder="Условия, сроки"
          />
        </label>

        <button type="submit" disabled={busy || !canSubmit}>
          {busy ? "Создание…" : "Создать заказ"}
        </button>
        {!canSubmit ? (
          <span className="field-hint">
            Нужны сезон, бренд и либо категории с суммами, либо общая сумма заказа.
          </span>
        ) : null}
      </form>
    </div>
  );
}
