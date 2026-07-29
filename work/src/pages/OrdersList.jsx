import { useCallback, useEffect, useState } from "react";
import { fetchBrandOrders, fetchProcurementRefs } from "../api.js";
import EntityRow from "../components/EntityRow.jsx";
import { balanceStyle, dateRu, eur, genderLabel } from "../utils/money.js";

export default function OrdersList() {
  const [refs, setRefs] = useState(null);
  const [data, setData] = useState({ items: [], total: 0 });
  const [filters, setFilters] = useState({ season_id: "", brand_id: "", gender: "" });
  const [showFilters, setShowFilters] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      setData(await fetchBrandOrders({ ...filters, limit: 100 }));
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
      .then(setRefs)
      .catch((e) => setErr(e.message));
  }, []);

  return (
    <div>
      <p className="sub" style={{ margin: "0 0 1rem" }}>
        {data.total ? `${data.total} записей` : " "}
      </p>

      <button
        type="button"
        className="secondary filter-toggle"
        onClick={() => setShowFilters((v) => !v)}
      >
        {showFilters ? "Скрыть фильтры" : "Фильтры"}
      </button>

      <div className={`filters${showFilters ? "" : " collapsed"}`}>
        <label>
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
        <label>
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
        <label>
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

      {err ? <p className="error">{err}</p> : null}

      {loading ? (
        <p className="loading">Загрузка…</p>
      ) : !data.items.length ? (
        <p className="empty">Заказов нет</p>
      ) : (
        <div className="entity-list">
          {data.items.map((row) => (
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
