import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import {
  createBrandOrder,
  deleteBrandOrder,
  fetchBrandOrders,
  fetchProcurementRefs,
} from "../api.js";
import { balanceStyle, dateRu, eur, genderLabel, num, rate as fmtRate, rub } from "../utils/money.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

const EMPTY_FORM = {
  season_id: "",
  brand_id: "",
  ordered_on: today(),
  eur_rub_rate: "",
  amount_eur: "",
  has_prepayment: false,
  prepayment_amount_eur: "",
  prepayment_due_on: "",
  comment: "",
};

const LINE_GENDER_GROUPS = [
  { gender: "men", label: "Мужская коллекция", unsplitLabel: "Муж — без разбивки" },
  { gender: "women", label: "Женская коллекция", unsplitLabel: "Жен — без разбивки" },
];

function newLine() {
  return { key: crypto.randomUUID(), choice: "", amount_eur: "", comment: "" };
}

/** Значение select строки: `<gender>|<category_id>`; пустой id — «без разбивки». */
function lineChoicePayload(choice) {
  const [gender, categoryId] = choice.split("|");
  return { category_id: categoryId || null, gender };
}

export default function BrandOrders() {
  const [refs, setRefs] = useState(null);
  const [data, setData] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({ season_id: "", brand_id: "", gender: "" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [lines, setLines] = useState([newLine()]);
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setData(await fetchBrandOrders(filters));
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

  /** Категории по коллекциям: свои + универсальные (аксессуары). */
  const categoryGroups = useMemo(() => {
    const all = refs?.categories || [];
    return LINE_GENDER_GROUPS.map((group) => ({
      ...group,
      items: all.filter((c) => c.gender === group.gender || c.gender === "unisex"),
    }));
  }, [refs]);

  const [existingOrder, setExistingOrder] = useState(null);

  useEffect(() => {
    setExistingOrder(null);
    if (!form.season_id || !form.brand_id) return;
    let cancelled = false;
    fetchBrandOrders({ season_id: form.season_id, brand_id: form.brand_id, limit: 1 })
      .then((res) => {
        if (!cancelled) setExistingOrder(res.items?.[0] || null);
      })
      .catch((e) => setErr(e.message));
    return () => {
      cancelled = true;
    };
  }, [form.season_id, form.brand_id]);

  const sortedItems = useMemo(
    () => [...data.items].sort((a, b) => num(b.balance_to_pay_eur) - num(a.balance_to_pay_eur)),
    [data.items],
  );

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

  function resetForm() {
    setForm({
      ...EMPTY_FORM,
      eur_rub_rate: refs?.latest_fx_rate?.eur_rub || "",
    });
    setLines([newLine()]);
  }

  const filledLines = lines.filter((ln) => ln.choice && num(ln.amount_eur) > 0);
  const orderAmount = filledLines.length > 0 ? linesTotal : num(form.amount_eur);

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const payload = {
        season_id: form.season_id,
        brand_id: form.brand_id,
        ordered_on: form.ordered_on || null,
        eur_rub_rate: form.eur_rub_rate || null,
        has_prepayment: form.has_prepayment,
        prepayment_amount_eur: form.has_prepayment
          ? form.prepayment_amount_eur || null
          : null,
        prepayment_due_on: form.has_prepayment ? form.prepayment_due_on || null : null,
        comment: form.comment.trim() || null,
        lines: filledLines.map((ln) => ({
          ...lineChoicePayload(ln.choice),
          amount_eur: ln.amount_eur,
          comment: ln.comment.trim() || null,
        })),
      };
      if (!filledLines.length) {
        payload.amount_eur = form.amount_eur;
      }
      await createBrandOrder(payload);
      resetForm();
      setShowForm(false);
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onDelete(row) {
    if (!window.confirm(`Удалить заказ ${row.brand_name} / ${row.season_name}?`)) return;
    setErr("");
    try {
      await deleteBrandOrder(row.id);
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  const canSubmit =
    form.season_id &&
    form.brand_id &&
    !existingOrder &&
    (filledLines.length > 0 || num(form.amount_eur) > 0);

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Заказы брендам</h2>
      <p style={{ color: "var(--muted)", maxWidth: 760 }}>
        Один заказ на бренд и сезон. Мужская и женская коллекции — строки внутри заказа:
        категория или «без разбивки», сумма заказа равна сумме строк. Оплаты и поставки
        считаются по бренду и сезону и сами привязываются к заказу. Предоплата здесь —
        план: сколько и к какому сроку должны. Фактические платежи заводятся в разделе
        «Оплаты».
      </p>

      {err ? <p className="error">{err}</p> : null}

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
          <label style={{ flex: "1 1 160px" }}>
            Пол
            <select
              value={filters.gender}
              onChange={(e) => setFilters((p) => ({ ...p, gender: e.target.value }))}
            >
              <option value="">Все</option>
              <option value="men">Мужской</option>
              <option value="women">Женский</option>
              <option value="mixed">Смешанный</option>
            </select>
          </label>
        </div>
      </div>

      <button
        type="button"
        style={{ marginBottom: "1rem" }}
        onClick={() => setShowForm((v) => !v)}
      >
        {showForm ? "Скрыть форму" : "Новый заказ"}
      </button>

      {showForm ? (
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ marginTop: 0 }}>Новый заказ</h3>
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
            </div>
            {existingOrder ? (
              <p className="error" style={{ margin: 0 }}>
                Заказ этого бренда на сезон уже есть ({dateRu(existingOrder.ordered_on)} ·{" "}
                {eur(existingOrder.amount_eur)}). Добавьте строки в него в приложении Work.
              </p>
            ) : null}

            <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
              <label style={{ flex: "1 1 160px" }}>
                Дата заказа
                <input
                  type="date"
                  value={form.ordered_on}
                  onChange={(e) => set("ordered_on", e.target.value)}
                />
              </label>
              <label style={{ flex: "1 1 160px" }}>
                Курс EUR/RUB
                <input
                  type="number"
                  step="0.0001"
                  min="0"
                  value={form.eur_rub_rate}
                  onChange={(e) => set("eur_rub_rate", e.target.value)}
                />
                <span className="field-hint">Плановый курс для оценки заказа в рублях.</span>
              </label>
            </div>

            <fieldset style={{ border: "1px solid var(--border, #333)", borderRadius: 8, padding: "0.75rem" }}>
              <legend style={{ padding: "0 0.4rem", fontSize: "0.85rem" }}>
                Строки заказа
              </legend>
              {lines.length === 0 ? (
                <p className="field-hint">
                  Строк нет — укажите общую сумму заказа ниже.
                </p>
              ) : null}
              {lines.map((ln) => (
                <div
                  key={ln.key}
                  style={{
                    display: "flex",
                    gap: "0.5rem",
                    flexWrap: "wrap",
                    alignItems: "flex-end",
                    marginBottom: "0.6rem",
                  }}
                >
                  <label style={{ flex: "2 1 220px" }}>
                    Категория
                    <select
                      value={ln.choice}
                      onChange={(e) => setLine(ln.key, "choice", e.target.value)}
                    >
                      <option value="">— выберите —</option>
                      {categoryGroups.map((group) => (
                        <optgroup key={group.gender} label={group.label}>
                          <option value={`${group.gender}|`}>{group.unsplitLabel}</option>
                          {group.items.map((c) => (
                            <option key={c.id} value={`${group.gender}|${c.id}`}>
                              {c.name}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </label>
                  <label style={{ flex: "1 1 120px" }}>
                    Сумма, €
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={ln.amount_eur}
                      onChange={(e) => setLine(ln.key, "amount_eur", e.target.value)}
                    />
                  </label>
                  <label style={{ flex: "2 1 200px" }}>
                    Комментарий
                    <input
                      value={ln.comment}
                      onChange={(e) => setLine(ln.key, "comment", e.target.value)}
                      placeholder="Глубина, особенности"
                    />
                  </label>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      setLines((prev) => prev.filter((x) => x.key !== ln.key))
                    }
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
                + Строка
              </button>
              {filledLines.length > 0 ? (
                <p className="field-hint" style={{ marginBottom: 0 }}>
                  Сумма заказа: <strong>{eur(linesTotal)}</strong>
                  {form.eur_rub_rate
                    ? ` ≈ ${rub(linesTotal * num(form.eur_rub_rate))}`
                    : ""}
                </p>
              ) : null}
            </fieldset>

            {filledLines.length === 0 ? (
              <label style={{ maxWidth: 240 }}>
                Сумма заказа, €
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.amount_eur}
                  onChange={(e) => set("amount_eur", e.target.value)}
                  required
                />
                <span className="field-hint">
                  Можно сохранить без строк — только общую сумму (архив / исключения).
                  {form.eur_rub_rate && num(form.amount_eur) > 0
                    ? ` ≈ ${rub(orderAmount * num(form.eur_rub_rate))}`
                    : ""}
                </span>
              </label>
            ) : null}

            <label style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <input
                type="checkbox"
                checked={form.has_prepayment}
                onChange={(e) => set("has_prepayment", e.target.checked)}
                style={{ width: "auto" }}
              />
              Нужна предоплата
            </label>

            {form.has_prepayment ? (
              <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
                <label style={{ flex: "1 1 160px" }}>
                  Сумма предоплаты, €
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={form.prepayment_amount_eur}
                    onChange={(e) => set("prepayment_amount_eur", e.target.value)}
                    required
                  />
                </label>
                <label style={{ flex: "1 1 160px" }}>
                  Срок предоплаты
                  <input
                    type="date"
                    value={form.prepayment_due_on}
                    onChange={(e) => set("prepayment_due_on", e.target.value)}
                  />
                </label>
              </div>
            ) : null}

            <label>
              Комментарий к заказу
              <input
                value={form.comment}
                onChange={(e) => set("comment", e.target.value)}
                placeholder="Условия, сроки отгрузки"
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
      ) : null}

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Заказы ({data.total})</h3>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !data.items.length ? (
          <p style={{ color: "var(--muted)" }}>Заказов нет.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Сезон</th>
                <th>Бренд</th>
                <th>Пол</th>
                <th>Дата</th>
                <th>Сумма</th>
                <th>Предоплата</th>
                <th>Оплачено</th>
                <th>Поставлено</th>
                <th>Остаток к оплате</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((row) => (
                <Fragment key={row.id}>
                  <tr>
                    <td>{row.season_name}</td>
                    <td>{row.brand_name}</td>
                    <td>{genderLabel(row.gender)}</td>
                    <td>{dateRu(row.ordered_on)}</td>
                    <td>
                      {eur(row.amount_eur)}
                      <div className="field-hint" style={{ margin: 0 }}>
                        {rub(row.amount_rub)}
                      </div>
                    </td>
                    <td>
                      {row.has_prepayment ? (
                        <>
                          {eur(row.prepayment_amount_eur)}
                          <div className="field-hint" style={{ margin: 0 }}>
                            до {dateRu(row.prepayment_due_on)}
                          </div>
                        </>
                      ) : (
                        "Нет"
                      )}
                    </td>
                    <td>{eur(row.paid_eur)}</td>
                    <td>{eur(row.shipped_eur)}</td>
                    <td style={balanceStyle(row.balance_to_pay_eur)}>
                      {eur(row.balance_to_pay_eur)}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setExpanded(expanded === row.id ? "" : row.id)}
                      >
                        {expanded === row.id ? "Скрыть" : "Строки"}
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        style={{ marginLeft: "0.4rem" }}
                        onClick={() => onDelete(row)}
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                  {expanded === row.id ? (
                    <tr>
                      <td colSpan={10}>
                        <div style={{ padding: "0.5rem 0" }}>
                          <strong>Строки заказа</strong>
                          {!row.lines.length ? (
                            <p style={{ color: "var(--muted)" }}>Строки не заданы.</p>
                          ) : (
                            <table>
                              <thead>
                                <tr>
                                  <th>Категория</th>
                                  <th>Сумма</th>
                                  <th>Комментарий</th>
                                </tr>
                              </thead>
                              <tbody>
                                {LINE_GENDER_GROUPS.map((group) => {
                                  const groupLines = row.lines.filter(
                                    (ln) => ln.category_gender === group.gender,
                                  );
                                  if (!groupLines.length) return null;
                                  const subtotal = groupLines.reduce(
                                    (acc, ln) => acc + num(ln.amount_eur),
                                    0,
                                  );
                                  return (
                                    <Fragment key={group.gender}>
                                      <tr>
                                        <th>{group.label}</th>
                                        <th>{eur(subtotal)}</th>
                                        <th />
                                      </tr>
                                      {groupLines.map((ln) => (
                                        <tr key={ln.id}>
                                          <td>{ln.category_name}</td>
                                          <td>{eur(ln.amount_eur)}</td>
                                          <td>{ln.comment || "—"}</td>
                                        </tr>
                                      ))}
                                    </Fragment>
                                  );
                                })}
                              </tbody>
                            </table>
                          )}
                          <p className="field-hint" style={{ marginBottom: 0 }}>
                            Курс заказа: {fmtRate(row.eur_rub_rate)} · Остаток к поставке:{" "}
                            {eur(row.balance_to_ship_eur)} · Предоплата не закрыта:{" "}
                            {eur(row.prepayment_outstanding_eur)}
                            {row.comment ? ` · ${row.comment}` : ""}
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
