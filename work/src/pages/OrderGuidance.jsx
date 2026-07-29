import { useEffect, useMemo, useState } from "react";
import { fetchOrderGuidance } from "../api.js";
import { dateRu, genderLabel } from "../utils/money.js";

export default function OrderGuidance() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(true);
  const [filters, setFilters] = useState({ gender: "", q: "" });

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

  const items = useMemo(() => {
    const list = data?.categories || [];
    const q = filters.q.trim().toLowerCase();
    return list.filter((c) => {
      if (filters.gender && c.gender !== filters.gender) return false;
      if (q && !(c.name || "").toLowerCase().includes(q)) return false;
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
        {periodLabel ? ` · продажи ${periodLabel}` : ""}
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
            onChange={(e) => setFilters((p) => ({ ...p, gender: e.target.value }))}
          >
            <option value="">Все</option>
            <option value="men">Мужской</option>
            <option value="women">Женский</option>
            <option value="unisex">Универсальный</option>
          </select>
        </label>
        <label>
          Категория
          <input
            type="search"
            placeholder="Поиск…"
            value={filters.q}
            onChange={(e) => setFilters((p) => ({ ...p, q: e.target.value }))}
          />
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
  const reinforce = new Set(cat.reinforce_sizes || []);
  const weaken = new Set(cat.weaken_sizes || []);

  return (
    <article className="guidance-card">
      <header className="guidance-card__head">
        <h2 className="guidance-card__title">{cat.name}</h2>
        <span className="guidance-card__gender">{genderLabel(cat.gender)}</span>
      </header>

      <p className="guidance-card__stock">
        Остатки: {st.total ?? "—"} шт
        {st.fresh_vl26 != null || st.old != null
          ? ` · ВЛ2026 ${st.fresh_vl26 ?? 0} / старые ${st.old ?? 0}`
          : ""}
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

      {labels.length ? (
        <SizeSalesChart
          labels={labels}
          values={values}
          reinforce={reinforce}
          weaken={weaken}
        />
      ) : (
        <p className="guidance-card__nochart">Нет продаж за период</p>
      )}
    </article>
  );
}

function SizeSalesChart({ labels, values, reinforce, weaken }) {
  const max = Math.max(1, ...values.map((v) => Number(v) || 0));

  return (
    <div className="size-chart" aria-label="Продажи по размерам">
      <p className="size-chart__caption">Продажи по размерам (шт)</p>
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
