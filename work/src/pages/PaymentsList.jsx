import { useCallback, useEffect, useState } from "react";
import { fetchPayments } from "../api.js";
import EntityRow from "../components/EntityRow.jsx";
import SeasonSlotBar, { useVisibleSeasons } from "../components/SeasonSlotBar.jsx";
import { dateRu, eur, paymentKindLabel } from "../utils/money.js";

export default function PaymentsList() {
  const slots = useVisibleSeasons();
  const [data, setData] = useState({ items: [], total: 0 });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!slots.ready) return;
    setLoading(true);
    setErr("");
    try {
      setData(await fetchPayments({ season_id: slots.seasonId, limit: 200 }));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [slots.ready, slots.seasonId]);

  useEffect(() => {
    reload();
  }, [reload]);

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
        <p className="empty">Оплат нет</p>
      ) : (
        <div className="entity-list">
          {data.items.map((row) => (
            <EntityRow
              key={row.id}
              to={`/payments/${row.id}`}
              title={row.brand_name}
              subtitle={`${dateRu(row.paid_on)} · ${paymentKindLabel(row.kind)}${
                row.season_name ? ` · ${row.season_name}` : ""
              }`}
              metric={eur(row.amount_eur)}
              noOrderHint={!row.order_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
