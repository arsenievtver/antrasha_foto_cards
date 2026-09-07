import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchShipment, updateShipment } from "../api.js";
import { dateRu, eur, kg, rate as fmtRate, rub } from "../utils/money.js";
import { shipmentStatusMeta } from "../utils/shipment.js";

export default function ShipmentDetail() {
  const { id } = useParams();
  const [row, setRow] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [statusBusy, setStatusBusy] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchShipment(id)
      .then(setRow)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function onToggleDelivered() {
    if (!row || statusBusy) return;
    setStatusBusy(true);
    setErr("");
    try {
      const next = await updateShipment(row.id, { is_delivered: !row.is_delivered });
      setRow(next);
    } catch (e) {
      setErr(e.message);
    } finally {
      setStatusBusy(false);
    }
  }

  if (loading) return <p className="loading">Загрузка…</p>;
  if (err && !row) {
    return (
      <div>
        <Link to="/shipments" className="back-link">
          ← Поставки
        </Link>
        <p className="error">{err}</p>
      </div>
    );
  }
  if (!row) return null;

  const status = shipmentStatusMeta(row.is_delivered);
  const hasLogistics =
    row.logistics_amount_rub != null ||
    row.logistics_paid_on != null;

  return (
    <div>
      <Link to="/shipments" className="back-link">
        ← Поставки
      </Link>
      {err ? <p className="error">{err}</p> : null}
      <div className="detail-card">
        <div className="detail-card-head">
          <div>
            <h2>{row.brand_name}</h2>
            <p className="sub" style={{ margin: "0.2rem 0 0", color: "var(--muted)" }}>
              {row.season_name}
            </p>
          </div>
          <Link
            to={`/shipments/${row.id}/edit`}
            className="icon-edit"
            aria-label="Редактировать поставку"
          >
            ✏️
          </Link>
        </div>

        <div style={{ margin: "0.5rem 0 0.65rem" }}>
          <span className={`pp-badge pp-badge--${status.tone}`}>{status.label}</span>
        </div>

        <div className="detail-metric">{eur(row.amount_eur)}</div>

        <div className="detail-status-row">
          <div className="detail-status-row__text">
            <div className="detail-status-row__label">
              {row.is_delivered ? "Поставлено" : "В пути"}
            </div>
            <div className="detail-status-row__hint">
              {row.is_delivered
                ? "Учитывается в остатке по заказу"
                : "Не уменьшает остаток по заказу"}
            </div>
          </div>
          <button
            type="button"
            className="switch-toggle"
            role="switch"
            aria-checked={!!row.is_delivered}
            aria-label={row.is_delivered ? "Поставлено" : "В пути"}
            disabled={statusBusy}
            onClick={onToggleDelivered}
          >
            <span className="switch-thumb" aria-hidden />
          </button>
        </div>

        <div className="detail-grid">
          <div className="detail-item">
            <span>Дата</span>
            <span>{dateRu(row.shipped_on)}</span>
          </div>
          <div className="detail-item">
            <span>Вес</span>
            <span>{kg(row.weight_kg)}</span>
          </div>
          <div className="detail-item">
            <span>Курс</span>
            <span>{fmtRate(row.eur_rub_rate)}</span>
          </div>
          <div className="detail-item">
            <span>В рублях</span>
            <span>{rub(row.amount_rub)}</span>
          </div>
          <div className="detail-item">
            <span>Заказ</span>
            <span>
              {row.order_id ? (
                <Link to={`/orders/${row.order_id}`}>Открыть</Link>
              ) : (
                "Без привязки"
              )}
            </span>
          </div>
          {hasLogistics ? (
            <>
              <div className="detail-item">
                <span>Логистика</span>
                <span>{rub(row.logistics_amount_rub)}</span>
              </div>
              <div className="detail-item">
                <span>Оплата лог.</span>
                <span>
                  {row.logistics_paid_on ? dateRu(row.logistics_paid_on) : "—"}
                </span>
              </div>
            </>
          ) : null}
          {row.comment ? (
            <div className="detail-item">
              <span>Комментарий</span>
              <span>{row.comment}</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
