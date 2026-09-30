import { useCallback, useEffect, useState } from "react";
import { fetchShipments } from "../api.js";
import EntityRow from "../components/EntityRow.jsx";
import SeasonSlotBar, { useVisibleSeasons } from "../components/SeasonSlotBar.jsx";
import { dateRu, eur, kg, rub } from "../utils/money.js";
import { shipmentStatusMeta } from "../utils/shipment.js";

export default function ShipmentsList() {
  const slots = useVisibleSeasons();
  const [data, setData] = useState({ items: [], total: 0 });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (!slots.ready) return;
    setLoading(true);
    setErr("");
    try {
      setData(await fetchShipments({ season_id: slots.seasonId, limit: 200 }));
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
        <p className="empty">Поставок нет</p>
      ) : (
        <div className="entity-list">
          {data.items.map((row) => {
            const status = shipmentStatusMeta(row.is_delivered);
            const parts = [
              dateRu(row.shipped_on),
              row.season_name || null,
              row.weight_kg != null && row.weight_kg !== "" ? kg(row.weight_kg) : null,
              row.logistics_amount_rub != null && row.logistics_amount_rub !== ""
                ? `лог. ${rub(row.logistics_amount_rub)}`
                : null,
            ].filter(Boolean);

            return (
              <EntityRow
                key={row.id}
                to={`/shipments/${row.id}`}
                title={row.brand_name}
                subtitle={parts.join(" · ")}
                metric={eur(row.amount_eur)}
                badges={[status]}
                noOrderHint={!row.order_id}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
