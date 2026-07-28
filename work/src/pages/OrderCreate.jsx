import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createBrandOrder, fetchProcurementRefs } from "../api.js";
import BrandSelect from "../components/BrandSelect.jsx";
import { eur, num, rub, today } from "../utils/money.js";

const EMPTY = {
  season_id: "",
  brand_id: "",
  gender: "",
  ordered_on: today(),
  eur_rub_rate: "",
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
      .then((res) => {
        setRefs(res);
        setForm((prev) => ({
          ...prev,
          eur_rub_rate: prev.eur_rub_rate || res.latest_fx_rate?.eur_rub || "",
        }));
      })
      .catch((e) => setErr(e.message));
  }, []);

  const formCategories = useMemo(() => {
    const all = refs?.categories || [];
    if (!form.gender || form.gender === "mixed") return all;
    return all.filter((c) => c.gender === form.gender || c.gender === "unisex");
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
      const row = await createBrandOrder({
        season_id: form.season_id,
        brand_id: form.brand_id,
        gender: form.gender || null,
        ordered_on: form.ordered_on || null,
        eur_rub_rate: form.eur_rub_rate || null,
        has_prepayment: form.has_prepayment,
        prepayment_amount_eur: form.has_prepayment
          ? form.prepayment_amount_eur || null
          : null,
        prepayment_due_on: form.has_prepayment ? form.prepayment_due_on || null : null,
        comment: form.comment.trim() || null,
        lines: filledLines.map((ln) => ({
          category_id: ln.category_id,
          amount_eur: ln.amount_eur,
          comment: ln.comment.trim() || null,
        })),
      });
      nav(`/orders/${row.id}`, { replace: true });
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = form.season_id && form.brand_id && filledLines.length > 0;
  const brands = refs?.brands || [];

  return (
    <div>
      <Link to="/orders" className="back-link">
        ← Заказы
      </Link>
      <div className="page-head">
        <h1>Новый заказ</h1>
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
        </label>

        <p className="section-title" style={{ marginTop: 0 }}>
          Категории
        </p>
        {lines.map((ln) => (
          <div key={ln.key} className="line-card">
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
              disabled={lines.length === 1}
              onClick={() => setLines((prev) => prev.filter((x) => x.key !== ln.key))}
            >
              Убрать
            </button>
          </div>
        ))}
        <button
          type="button"
          className="secondary"
          onClick={() => setLines((prev) => [...prev, newLine()])}
        >
          + Категория
        </button>
        <p className="field-hint">
          Сумма заказа: <strong>{eur(linesTotal)}</strong>
          {form.eur_rub_rate ? ` ≈ ${rub(linesTotal * num(form.eur_rub_rate))}` : ""}
        </p>

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
            Нужны сезон, бренд и хотя бы одна категория с суммой.
          </span>
        ) : null}
      </form>
    </div>
  );
}
