import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchBrandOrder } from "../api.js";
import {
  balanceStyle,
  dateRu,
  eur,
  genderLabel,
  rate as fmtRate,
  rub,
} from "../utils/money.js";

export default function OrderDetail() {
  const { id } = useParams();
  const [row, setRow] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchBrandOrder(id)
      .then(setRow)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="loading">Загрузка…</p>;
  if (err) {
    return (
      <div>
        <Link to="/orders" className="back-link">
          ← Заказы
        </Link>
        <p className="error">{err}</p>
      </div>
    );
  }
  if (!row) return null;

  return (
    <div>
      <Link to="/orders" className="back-link">
        ← Заказы
      </Link>
      <div className="detail-card">
        <h2>{row.brand_name}</h2>
        <p className="sub" style={{ margin: 0, color: "var(--muted)" }}>
          {row.season_name}
          {row.gender ? ` · ${genderLabel(row.gender)}` : ""}
        </p>
        <div className="detail-metric">{eur(row.amount_eur)}</div>
        <div className="detail-grid">
          <div className="detail-item">
            <span>Дата</span>
            <span>{dateRu(row.ordered_on)}</span>
          </div>
          <div className="detail-item">
            <span>В рублях</span>
            <span>{rub(row.amount_rub)}</span>
          </div>
          <div className="detail-item">
            <span>Курс</span>
            <span>{fmtRate(row.eur_rub_rate)}</span>
          </div>
          <div className="detail-item">
            <span>Оплачено</span>
            <span>{eur(row.paid_eur)}</span>
          </div>
          <div className="detail-item">
            <span>Поставлено</span>
            <span>{eur(row.shipped_eur)}</span>
          </div>
          <div className="detail-item">
            <span>Остаток к оплате</span>
            <span style={balanceStyle(row.balance_to_pay_eur)}>
              {eur(row.balance_to_pay_eur)}
            </span>
          </div>
          <div className="detail-item">
            <span>Остаток к поставке</span>
            <span style={balanceStyle(row.balance_to_ship_eur)}>
              {eur(row.balance_to_ship_eur)}
            </span>
          </div>
          {row.has_prepayment ? (
            <>
              <div className="detail-item">
                <span>Предоплата (план)</span>
                <span>{eur(row.prepayment_amount_eur)}</span>
              </div>
              <div className="detail-item">
                <span>Срок предоплаты</span>
                <span>{dateRu(row.prepayment_due_on)}</span>
              </div>
              <div className="detail-item">
                <span>Не закрыто</span>
                <span>{eur(row.prepayment_outstanding_eur)}</span>
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

      <p className="section-title">Категории</p>
      {!row.lines?.length ? (
        <p className="empty" style={{ padding: "1rem 0" }}>
          Категории не заданы
        </p>
      ) : (
        <div className="entity-list">
          {row.lines.map((ln) => (
            <div key={ln.id} className="entity-row" style={{ cursor: "default" }}>
              <div className="entity-row__body">
                <div className="entity-row__title">{ln.category_name}</div>
                <div className="entity-row__sub">
                  {genderLabel(ln.category_gender)}
                  {ln.comment ? ` · ${ln.comment}` : ""}
                </div>
              </div>
              <div className="entity-row__right">
                <div className="entity-row__metric">{eur(ln.amount_eur)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
