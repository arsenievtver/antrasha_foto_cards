import { useEffect, useMemo, useState } from "react";
import { fetchOrderGuidance } from "../api.js";
import { dateRu, eur } from "../utils/money.js";

export default function OrderGuidance() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(true);
  const [filters, setFilters] = useState({ gender: "", key: "" });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr("");
    fetchOrderGuidance()
      .then((payload) => {
        if (!cancelled) setData(payload);
      })
      .catch((e) => {
        if (!cancelled) setErr(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const categoryOptions = useMemo(() => {
    const list = data?.categories || [];
    if (!filters.gender) return list;
    return list.filter((c) => c.gender === filters.gender);
  }, [data, filters.gender]);

  const items = useMemo(() => {
    const list = data?.categories || [];
    return list.filter((c) => {
      if (filters.gender && c.gender !== filters.gender) return false;
      if (filters.key && c.key !== filters.key) return false;
      return true;
    });
  }, [data, filters]);

  const period = data?.meta?.sales_period;
  const periodLabel = period
    ? `${dateRu(period.from)} – ${dateRu(period.to)}`
    : null;

  return (
    <div>
      <p className="sub" style={{ margin: "0 0 1rem" }}>
        {data?.meta?.as_of ? `Остатки на ${data.meta.as_of}` : " "}
        {periodLabel ? ` · ВЛ2025+ВЛ2026 с ${periodLabel}` : ""}
        {" · только весна-лето"}
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
          Пол
          <select
            value={filters.gender}
            onChange={(e) => {
              const gender = e.target.value;
              setFilters((p) => {
                const next = { ...p, gender };
                if (p.key) {
                  const ok = (data?.categories || []).some(
                    (c) => c.key === p.key && (!gender || c.gender === gender),
                  );
                  if (!ok) next.key = "";
                }
                return next;
              });
            }}
          >
            <option value="">Все</option>
            <option value="men">Мужской</option>
            <option value="women">Женский</option>
            <option value="unisex">Универсальный</option>
          </select>
        </label>
        <label>
          Категория
          <select
            value={filters.key}
            onChange={(e) => setFilters((p) => ({ ...p, key: e.target.value }))}
          >
            <option value="">Все</option>
            {categoryOptions.map((c) => (
              <option key={c.key} value={c.key}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {err ? <p className="error">{err}</p> : null}

      {loading ? (
        <p className="loading">Загрузка…</p>
      ) : !items.length ? (
        <p className="empty">Нет категорий</p>
      ) : (
        <div className="guidance-list">
          {items.map((cat) => (
            <GuidanceCard key={cat.key} cat={cat} />
          ))}
        </div>
      )}
    </div>
  );
}

function GuidanceCard({ cat }) {
  const st = cat.stock_totals || {};
  const chart = cat.size_sales_chart || {};
  const labels = chart.labels || [];
  const values = chart.sellQuantity || [];
  const rows = cat.size_summary_rows || [];
  const reinforce = new Set(cat.reinforce_sizes || []);
  const weaken = new Set(cat.weaken_sizes || []);

  return (
    <article className="guidance-card">
      <header className="guidance-card__head">
        <h2 className="guidance-card__title">{cat.name}</h2>
        <span className="guidance-card__amount">{eur(cat.order_amount_eur)}</span>
      </header>

      <p className="guidance-card__stock">
        {st.total != null
          ? `Остатки: ${st.total} шт (${st.fresh_vl26 ?? 0};${st.old ?? 0}) ${st.fresh_vl26 ?? 0}-ВЛ2026; ${st.old ?? 0}-старые`
          : "Остатки: —"}
      </p>

      {cat.reinforce_sizes?.length ? (
        <p className="guidance-card__hint guidance-card__hint--up">
          Усилить: {cat.reinforce_sizes.join(", ")}
        </p>
      ) : null}
      {cat.weaken_sizes?.length ? (
        <p className="guidance-card__hint guidance-card__hint--down">
          Ослабить: {cat.weaken_sizes.join(", ")}
        </p>
      ) : (
        <p className="guidance-card__hint">Ослабить: нет явных</p>
      )}

      {cat.comment ? <p className="guidance-card__comment">{cat.comment}</p> : null}

      {rows.length ? (
        <table className="guidance-table">
          <thead>
            <tr>
              <th>Размер</th>
              <th>Поступило</th>
              <th>Продано</th>
              <th>Остатки</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.size}>
                <td>{row.size}</td>
                <td>{row.received_total}</td>
                <td>{row.sold_total}</td>
                <td>{row.stock_total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="guidance-card__nochart">Нет данных по размерам</p>
      )}

      {labels.length ? (
        <SizeSalesChart
          labels={labels}
          values={values}
          reinforce={reinforce}
          weaken={weaken}
        />
      ) : null}
    </article>
  );
}

function SizeSalesChart({ labels, values, reinforce, weaken }) {
  const max = Math.max(1, ...values.map((v) => Number(v) || 0));

  return (
    <div className="size-chart" aria-label="Продажи по размерам">
      <p className="size-chart__caption">Продано ВЛ2025+ВЛ2026 (шт)</p>
      <div className="size-chart__bars">
        {labels.map((label, i) => {
          const qty = Number(values[i]) || 0;
          const h = Math.round((qty / max) * 100);
          let tone = "";
          if (reinforce.has(label)) tone = " size-chart__col--up";
          else if (weaken.has(label)) tone = " size-chart__col--down";
          return (
            <div key={`${label}-${i}`} className={`size-chart__col${tone}`}>
              <span className="size-chart__qty">{qty || ""}</span>
              <div className="size-chart__bar-wrap">
                <div className="size-chart__bar" style={{ height: `${h}%` }} />
              </div>
              <span className="size-chart__label">{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
