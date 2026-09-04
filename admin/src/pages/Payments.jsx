import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createPayment,
  deletePayment,
  fetchBrandOrders,
  fetchPayments,
  fetchProcurementRefs,
  updatePayment,
} from "../api.js";
import {
  dateRu,
  eur,
  num,
  paymentKindLabel,
  rateShort,
  rub,
} from "../utils/money.js";

function today() {
  return new Date().toISOString().slice(0, 10);
}

const EMPTY_FORM = {
  season_id: "",
  brand_id: "",
  order_id: "",
  paid_on: today(),
  kind: "main",
  amount_eur: "",
  eur_rub_rate: "",
  comment: "",
};

function CellStack({ primary, secondary }) {
  return (
    <div className="cell-stack">
      <div className="cell-stack__primary">{primary}</div>
      <div className="cell-stack__secondary">{secondary}</div>
    </div>
  );
}

function PaymentFields({ form, setField, orders, amountRub, refs }) {
  return (
    <>
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <label style={{ flex: "1 1 200px" }}>
          Сезон
          <select
            value={form.season_id}
            onChange={(e) => setField("season_id", e.target.value)}
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
            onChange={(e) => setField("brand_id", e.target.value)}
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
        <label style={{ flex: "1 1 220px" }}>
          Заказ
          <select
            value={form.order_id}
            onChange={(e) => setField("order_id", e.target.value)}
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
      </div>

      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <label style={{ flex: "1 1 150px" }}>
          Дата оплаты
          <input
            type="date"
            value={form.paid_on}
            onChange={(e) => setField("paid_on", e.target.value)}
            required
          />
        </label>
        <label style={{ flex: "1 1 150px" }}>
          Категория
          <select value={form.kind} onChange={(e) => setField("kind", e.target.value)}>
            <option value="main">Основная</option>
            <option value="prepayment">Предоплата</option>
          </select>
        </label>
        <label style={{ flex: "1 1 150px" }}>
          Сумма, €
          <input
            type="number"
            step="0.01"
            min="0"
            value={form.amount_eur}
            onChange={(e) => setField("amount_eur", e.target.value)}
            required
          />
        </label>
        <label style={{ flex: "1 1 150px" }}>
          Курс EUR/RUB
          <input
            type="number"
            step="0.0001"
            min="0"
            value={form.eur_rub_rate}
            onChange={(e) => setField("eur_rub_rate", e.target.value)}
          />
          <span className="field-hint">
            {amountRub !== null ? `Будет ${rub(amountRub)}` : "Пусто — возьмём из справочника"}
          </span>
        </label>
      </div>

      <label>
        Комментарий
        <input
          value={form.comment}
          onChange={(e) => setField("comment", e.target.value)}
          placeholder="Назначение платежа, банк"
        />
      </label>
    </>
  );
}

function formFromRow(row) {
  return {
    season_id: row.season_id,
    brand_id: row.brand_id,
    order_id: row.order_id || "",
    paid_on: row.paid_on,
    kind: row.kind || "main",
    amount_eur: row.amount_eur != null ? String(row.amount_eur) : "",
    eur_rub_rate: row.eur_rub_rate != null ? String(row.eur_rub_rate) : "",
    comment: row.comment || "",
  };
}

function payloadFromForm(form) {
  return {
    season_id: form.season_id,
    brand_id: form.brand_id,
    order_id: form.order_id || null,
    paid_on: form.paid_on,
    kind: form.kind,
    amount_eur: form.amount_eur,
    eur_rub_rate: form.eur_rub_rate || null,
    comment: form.comment.trim() || null,
  };
}

export default function Payments() {
  const [refs, setRefs] = useState(null);
  const [orders, setOrders] = useState([]);
  const [data, setData] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({ season_id: "", brand_id: "", kind: "" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editRow, setEditRow] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [editOrders, setEditOrders] = useState([]);
  const [editBusy, setEditBusy] = useState(false);
  const [infoRow, setInfoRow] = useState(null);
  const [infoOrder, setInfoOrder] = useState(null);
  const [infoLoading, setInfoLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setData(await fetchPayments(filters));
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

  useEffect(() => {
    if (!form.season_id || !form.brand_id) {
      setOrders([]);
      return;
    }
    fetchBrandOrders({ season_id: form.season_id, brand_id: form.brand_id, limit: 200 })
      .then((res) => setOrders(res.items || []))
      .catch((e) => setErr(e.message));
  }, [form.season_id, form.brand_id]);

  useEffect(() => {
    if (!editForm?.season_id || !editForm?.brand_id) {
      setEditOrders([]);
      return;
    }
    fetchBrandOrders({
      season_id: editForm.season_id,
      brand_id: editForm.brand_id,
      limit: 200,
    })
      .then((res) => setEditOrders(res.items || []))
      .catch((e) => setErr(e.message));
  }, [editForm?.season_id, editForm?.brand_id]);

  const amountRub = useMemo(() => {
    if (!form.amount_eur || !form.eur_rub_rate) return null;
    return num(form.amount_eur) * num(form.eur_rub_rate);
  }, [form.amount_eur, form.eur_rub_rate]);

  const editAmountRub = useMemo(() => {
    if (!editForm?.amount_eur || !editForm?.eur_rub_rate) return null;
    return num(editForm.amount_eur) * num(editForm.eur_rub_rate);
  }, [editForm?.amount_eur, editForm?.eur_rub_rate]);

  function set(field, value) {
    setForm((prev) => {
      const next = { ...prev, [field]: value };
      if (field === "season_id" || field === "brand_id") next.order_id = "";
      return next;
    });
  }

  function setEditField(field, value) {
    setEditForm((prev) => {
      if (!prev) return prev;
      const next = { ...prev, [field]: value };
      if (field === "season_id" || field === "brand_id") next.order_id = "";
      return next;
    });
  }

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await createPayment(payloadFromForm(form));
      setForm({
        ...EMPTY_FORM,
        season_id: form.season_id,
        brand_id: form.brand_id,
        eur_rub_rate: refs?.latest_fx_rate?.eur_rub || "",
      });
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  function openEdit(row) {
    setEditRow(row);
    setEditForm(formFromRow(row));
  }

  function closeEdit() {
    setEditRow(null);
    setEditForm(null);
    setEditOrders([]);
  }

  async function onSaveEdit(e) {
    e.preventDefault();
    if (!editRow || !editForm) return;
    setEditBusy(true);
    setErr("");
    try {
      await updatePayment(editRow.id, {
        ...payloadFromForm(editForm),
        clear_order: !editForm.order_id,
      });
      closeEdit();
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setEditBusy(false);
    }
  }

  async function openInfo(row) {
    setInfoRow(row);
    setInfoOrder(null);
    if (!row.order_id) return;
    setInfoLoading(true);
    try {
      const res = await fetchBrandOrders({
        season_id: row.season_id,
        brand_id: row.brand_id,
        limit: 200,
      });
      setInfoOrder((res.items || []).find((o) => o.id === row.order_id) || null);
    } catch (e) {
      setErr(e.message);
    } finally {
      setInfoLoading(false);
    }
  }

  function closeInfo() {
    setInfoRow(null);
    setInfoOrder(null);
    setInfoLoading(false);
  }

  async function onDelete(row) {
    if (!window.confirm(`Удалить оплату ${eur(row.amount_eur)} от ${dateRu(row.paid_on)}?`))
      return;
    setErr("");
    try {
      await deletePayment(row.id);
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  const canSubmit = form.season_id && form.brand_id && num(form.amount_eur) > 0;
  const canSaveEdit =
    editForm?.season_id && editForm?.brand_id && num(editForm?.amount_eur) > 0;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Оплаты</h2>
      <p style={{ color: "var(--muted)", maxWidth: 760 }}>
        Сумма в евро пересчитывается в рубли по курсу на дату оплаты и сохраняется в
        документе. Привязка к заказу необязательна, но именно она показывает, сколько
        ещё должны по конкретному заказу.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новая оплата</h3>
        <form className="form-stack" onSubmit={onCreate}>
          <PaymentFields
            form={form}
            setField={set}
            orders={orders}
            amountRub={amountRub}
            refs={refs}
          />
          <button type="submit" disabled={busy || !canSubmit}>
            {busy ? "Сохранение…" : "Добавить оплату"}
          </button>
        </form>
      </div>

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
            Категория
            <select
              value={filters.kind}
              onChange={(e) => setFilters((p) => ({ ...p, kind: e.target.value }))}
            >
              <option value="">Все</option>
              <option value="main">Основная</option>
              <option value="prepayment">Предоплата</option>
            </select>
          </label>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Оплаты ({data.total})</h3>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !data.items.length ? (
          <p style={{ color: "var(--muted)" }}>Оплат нет.</p>
        ) : (
          <table className="shipments-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Бренд</th>
                <th>Категория</th>
                <th>₽</th>
                <th className="col-info" aria-label="Подробнее" />
                <th className="col-actions" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td>
                    <CellStack primary={dateRu(row.paid_on)} secondary={row.season_name} />
                  </td>
                  <td>
                    <CellStack primary={row.brand_name} secondary={eur(row.amount_eur)} />
                  </td>
                  <td>{paymentKindLabel(row.kind)}</td>
                  <td>
                    <CellStack
                      primary={rub(row.amount_rub)}
                      secondary={rateShort(row.eur_rub_rate)}
                    />
                  </td>
                  <td className="col-info">
                    <button
                      type="button"
                      className="shipments-info-btn"
                      aria-label="Заказ и комментарий"
                      title="Заказ и комментарий"
                      onClick={() => openInfo(row)}
                    >
                      !
                    </button>
                  </td>
                  <td className="col-actions">
                    <div className="shipments-actions">
                      <button type="button" className="secondary" onClick={() => openEdit(row)}>
                        Изменить
                      </button>
                      <button type="button" className="secondary" onClick={() => onDelete(row)}>
                        Удалить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {editRow && editForm ? (
        <div className="modal-backdrop" role="presentation" onClick={closeEdit}>
          <div
            className="modal"
            role="dialog"
            aria-labelledby="payment-edit-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="payment-edit-title" style={{ marginTop: 0 }}>
              Изменить оплату
            </h3>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>
              {dateRu(editRow.paid_on)} · {editRow.brand_name}
            </p>
            <form className="form-stack" onSubmit={onSaveEdit}>
              <PaymentFields
                form={editForm}
                setField={setEditField}
                orders={editOrders}
                amountRub={editAmountRub}
                refs={refs}
              />
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <button type="submit" disabled={editBusy || !canSaveEdit}>
                  {editBusy ? "Сохранение…" : "Сохранить"}
                </button>
                <button type="button" className="secondary" disabled={editBusy} onClick={closeEdit}>
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}

      {infoRow ? (
        <div className="modal-backdrop" role="presentation" onClick={closeInfo}>
          <div
            className="modal"
            role="dialog"
            aria-labelledby="payment-info-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="payment-info-title" style={{ marginTop: 0 }}>
              Оплата · {dateRu(infoRow.paid_on)}
            </h3>
            <dl style={{ margin: "0 0 1rem", lineHeight: 1.5 }}>
              <dt style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Заказ</dt>
              <dd style={{ margin: "0.15rem 0 0.75rem" }}>
                {infoLoading ? (
                  "Загрузка…"
                ) : infoRow.order_id ? (
                  infoOrder ? (
                    <>
                      {dateRu(infoOrder.ordered_on)} · {eur(infoOrder.amount_eur)} · остаток{" "}
                      {eur(infoOrder.balance_to_pay_eur)}
                    </>
                  ) : (
                    "Привязан (заказ не найден в списке)"
                  )
                ) : (
                  "Без привязки"
                )}
              </dd>
              <dt style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Комментарий</dt>
              <dd style={{ margin: "0.15rem 0 0", whiteSpace: "pre-wrap" }}>
                {infoRow.comment?.trim() || "—"}
              </dd>
            </dl>
            <button type="button" className="secondary" onClick={closeInfo}>
              Закрыть
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
