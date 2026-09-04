import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createShipment,
  deleteShipment,
  fetchBrandOrders,
  fetchProcurementRefs,
  fetchShipments,
  updateShipment,
} from "../api.js";
import {
  dateRu,
  eur,
  kgShort,
  num,
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
  shipped_on: today(),
  amount_eur: "",
  weight_kg: "",
  eur_rub_rate: "",
  comment: "",
  logistics_amount_rub: "",
  logistics_paid_on: "",
  is_delivered: true,
};

function CellStack({ primary, secondary }) {
  return (
    <div className="cell-stack">
      <div className="cell-stack__primary">{primary}</div>
      <div className="cell-stack__secondary">{secondary}</div>
    </div>
  );
}

function ShipmentFields({ form, setField, orders, amountRub, refs }) {
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
                {dateRu(o.ordered_on)} · {eur(o.amount_eur)} · осталось{" "}
                {eur(o.balance_to_ship_eur)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <label style={{ flex: "1 1 150px" }}>
          Дата поставки
          <input
            type="date"
            value={form.shipped_on}
            onChange={(e) => setField("shipped_on", e.target.value)}
            required
          />
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
          Вес, кг
          <input
            type="number"
            step="0.001"
            min="0"
            value={form.weight_kg}
            onChange={(e) => setField("weight_kg", e.target.value)}
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

      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "flex-end" }}>
        <label style={{ flex: "1 1 150px" }}>
          Сумма логистики, ₽
          <input
            type="number"
            step="0.01"
            min="0"
            value={form.logistics_amount_rub}
            onChange={(e) => setField("logistics_amount_rub", e.target.value)}
          />
        </label>
        <label style={{ flex: "1 1 150px" }}>
          Дата оплаты логистики
          <input
            type="date"
            value={form.logistics_paid_on}
            onChange={(e) => setField("logistics_paid_on", e.target.value)}
          />
        </label>
        <div style={{ flex: "1 1 180px", paddingBottom: "0.35rem" }}>
          <span
            style={{
              display: "block",
              fontSize: "0.85rem",
              color: "var(--muted)",
              marginBottom: "0.35rem",
            }}
          >
            Статус
          </span>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              type="button"
              className="switch-toggle"
              role="switch"
              aria-checked={form.is_delivered}
              aria-label={form.is_delivered ? "Поставлено" : "В пути"}
              onClick={() => setField("is_delivered", !form.is_delivered)}
            >
              <span className="switch-thumb" aria-hidden />
            </button>
            <span>{form.is_delivered ? "Поставлено" : "В пути"}</span>
          </div>
        </div>
      </div>

      <label>
        Комментарий
        <input
          value={form.comment}
          onChange={(e) => setField("comment", e.target.value)}
          placeholder="Номер инвойса, перевозчик"
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
    shipped_on: row.shipped_on,
    amount_eur: row.amount_eur != null ? String(row.amount_eur) : "",
    weight_kg: row.weight_kg != null ? String(row.weight_kg) : "",
    eur_rub_rate: row.eur_rub_rate != null ? String(row.eur_rub_rate) : "",
    comment: row.comment || "",
    logistics_amount_rub:
      row.logistics_amount_rub != null ? String(row.logistics_amount_rub) : "",
    logistics_paid_on: row.logistics_paid_on || "",
    is_delivered: !!row.is_delivered,
  };
}

function payloadFromForm(form) {
  return {
    season_id: form.season_id,
    brand_id: form.brand_id,
    order_id: form.order_id || null,
    shipped_on: form.shipped_on,
    amount_eur: form.amount_eur,
    weight_kg: form.weight_kg || null,
    eur_rub_rate: form.eur_rub_rate || null,
    comment: form.comment.trim() || null,
    logistics_amount_rub: form.logistics_amount_rub || null,
    logistics_paid_on: form.logistics_paid_on || null,
    is_delivered: form.is_delivered,
  };
}

export default function Shipments() {
  const [refs, setRefs] = useState(null);
  const [orders, setOrders] = useState([]);
  const [data, setData] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({ season_id: "", brand_id: "" });
  const [form, setForm] = useState(EMPTY_FORM);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toggleId, setToggleId] = useState(null);
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
      setData(await fetchShipments(filters));
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
      await createShipment(payloadFromForm(form));
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
      await updateShipment(editRow.id, {
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

  async function onToggleDelivered(row) {
    setToggleId(row.id);
    setErr("");
    try {
      await updateShipment(row.id, { is_delivered: !row.is_delivered });
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setToggleId(null);
    }
  }

  async function onDelete(row) {
    if (
      !window.confirm(
        `Удалить поставку ${eur(row.amount_eur)} от ${dateRu(row.shipped_on)}?`,
      )
    )
      return;
    setErr("");
    try {
      await deleteShipment(row.id);
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
      <h2 style={{ marginTop: 0 }}>Поставки</h2>
      <p style={{ color: "var(--muted)", maxWidth: 760 }}>
        Что и когда бренд отгрузил: сумма в евро и вес. Логистика (рубли и дата оплаты) хранится
        здесь отдельно от оплат бренду. Пока поставка «в пути», она не уменьшает «осталось
        поставить» по заказу.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новая поставка</h3>
        <form className="form-stack" onSubmit={onCreate}>
          <ShipmentFields
            form={form}
            setField={set}
            orders={orders}
            amountRub={amountRub}
            refs={refs}
          />
          <button type="submit" disabled={busy || !canSubmit}>
            {busy ? "Сохранение…" : "Добавить поставку"}
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
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Поставки ({data.total})</h3>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !data.items.length ? (
          <p style={{ color: "var(--muted)" }}>Поставок нет.</p>
        ) : (
          <table className="shipments-table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Бренд</th>
                <th className="col-weight">Вес</th>
                <th>₽</th>
                <th>Логист.</th>
                <th className="col-status" aria-label="Статус" />
                <th className="col-info" aria-label="Подробнее" />
                <th className="col-actions" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id}>
                  <td>
                    <CellStack primary={dateRu(row.shipped_on)} secondary={row.season_name} />
                  </td>
                  <td>
                    <CellStack primary={row.brand_name} secondary={eur(row.amount_eur)} />
                  </td>
                  <td className="col-weight">{kgShort(row.weight_kg)}</td>
                  <td>
                    <CellStack
                      primary={rub(row.amount_rub)}
                      secondary={rateShort(row.eur_rub_rate)}
                    />
                  </td>
                  <td>
                    <CellStack
                      primary={rub(row.logistics_amount_rub)}
                      secondary={
                        row.logistics_paid_on ? dateRu(row.logistics_paid_on) : "—"
                      }
                    />
                  </td>
                  <td className="col-status">
                    <button
                      type="button"
                      className="switch-toggle"
                      role="switch"
                      aria-checked={row.is_delivered}
                      aria-label={row.is_delivered ? "Поставлено" : "В пути"}
                      title={row.is_delivered ? "Поставлено" : "В пути"}
                      disabled={toggleId === row.id}
                      onClick={() => onToggleDelivered(row)}
                    >
                      <span className="switch-thumb" aria-hidden />
                    </button>
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
            aria-labelledby="shipment-edit-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="shipment-edit-title" style={{ marginTop: 0 }}>
              Изменить поставку
            </h3>
            <p style={{ color: "var(--muted)", marginTop: 0 }}>
              {dateRu(editRow.shipped_on)} · {editRow.brand_name}
            </p>
            <form className="form-stack" onSubmit={onSaveEdit}>
              <ShipmentFields
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
            aria-labelledby="shipment-info-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="shipment-info-title" style={{ marginTop: 0 }}>
              Поставка · {dateRu(infoRow.shipped_on)}
            </h3>
            <dl style={{ margin: "0 0 1rem", lineHeight: 1.5 }}>
              <dt style={{ color: "var(--muted)", fontSize: "0.85rem" }}>Заказ</dt>
              <dd style={{ margin: "0.15rem 0 0.75rem" }}>
                {infoLoading ? (
                  "Загрузка…"
                ) : infoRow.order_id ? (
                  infoOrder ? (
                    <>
                      {dateRu(infoOrder.ordered_on)} · {eur(infoOrder.amount_eur)} · осталось{" "}
                      {eur(infoOrder.balance_to_ship_eur)}
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
