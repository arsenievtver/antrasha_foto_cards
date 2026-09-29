import { useEffect, useState } from "react";
import { fetchBrandOrders } from "../api.js";
import { eur } from "../utils/money.js";

/** Заказ пары сезон + бренд, к которому сам привяжется документ. balance: "pay" | "ship". */
export default function PairOrderHint({ seasonId, brandId, balance }) {
  const [order, setOrder] = useState(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    setOrder(null);
    setLoaded(false);
    if (!seasonId || !brandId) return undefined;
    let active = true;
    fetchBrandOrders({ season_id: seasonId, brand_id: brandId, limit: 1 })
      .then((res) => active && setOrder(res.items?.[0] || null))
      .catch(() => active && setOrder(null))
      .finally(() => active && setLoaded(true));
    return () => {
      active = false;
    };
  }, [seasonId, brandId]);

  if (!seasonId || !brandId || !loaded) return null;
  if (!order) {
    return (
      <p className="field-hint" style={{ margin: 0 }}>
        Заказа этого бренда на сезон пока нет — документ привяжется, когда заказ создадут.
      </p>
    );
  }
  const rest = balance === "ship" ? order.balance_to_ship_eur : order.balance_to_pay_eur;
  return (
    <p className="field-hint" style={{ margin: 0 }}>
      Заказ {eur(order.amount_eur)}
      {balance === "ship" ? " · осталось поставить " : " · остаток к оплате "}
      {eur(rest)}
    </p>
  );
}
