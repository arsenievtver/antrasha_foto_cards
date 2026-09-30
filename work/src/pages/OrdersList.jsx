import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchBrandOrders } from "../api.js";
import EntityRow from "../components/EntityRow.jsx";
import SeasonSlotBar, { useVisibleSeasons } from "../components/SeasonSlotBar.jsx";
import { balanceStyle, dateRu, eur, genderLabel, num } from "../utils/money.js";

export default function OrdersList() {
  const slots = useVisibleSeasons();
  const [data, setData] = useState({ items: [], total: 0 });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!slots.ready) return;
    setLoading(true);
    setErr("");
    try {
      setData(await fetchBrandOrders({ season_id: slots.seasonId, limit: 200 }));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [slots.ready, slots.seasonId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const sortedItems = useMemo(
    () => [...data.items].sort((a, b) => num(b.balance_to_pay_eur) - num(a.balance_to_pay_eur)),
    [data.items],
  );

  return (
    <div>
      <SeasonSlotBar
        seasons={slots.seasons}
        seasonId={slots.seasonId}
        onChange={slots.setSeasonId}
        ready={slots.ready}
      />

      {slots.err || err ? <p className="error">{slots.err || err}</p> : null}

      {loading ? (
        <p className="loading">Загрузка…</p>
      ) : !data.items.length ? (
        <p className="empty">Заказов нет</p>
      ) : (
        <div className="entity-list">
          {sortedItems.map((row) => (
            <EntityRow
              key={row.id}
              to={`/orders/${row.id}`}
              title={row.brand_name}
              subtitle={`${dateRu(row.ordered_on)} · ${row.season_name}${
                row.gender ? ` · ${genderLabel(row.gender)}` : ""
              }`}
              metric={eur(row.amount_eur)}
              metricSub={`к оплате ${eur(row.balance_to_pay_eur)}`}
              style={balanceStyle(row.balance_to_pay_eur)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
