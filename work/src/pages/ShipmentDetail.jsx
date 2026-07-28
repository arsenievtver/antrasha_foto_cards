import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchShipment } from "../api.js";
import { dateRu, eur, kg, rate as fmtRate, rub } from "../utils/money.js";

export default function ShipmentDetail() {
  const { id } = useParams();
  const [row, setRow] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchShipment(id)
      .then(setRow)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="loading">Загрузка…</p>;
  if (err) {
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

  return (
    <div>
      <Link to="/shipments" className="back-link">
        ← Поставки
      </Link>
      <div className="detail-card">
        <h2>{row.brand_name}</h2>
        <p className="sub" style={{ margin: 0, color: "var(--muted)" }}>
          {row.season_name}
        </p>
        <div className="detail-metric">{eur(row.amount_eur)}</div>
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
