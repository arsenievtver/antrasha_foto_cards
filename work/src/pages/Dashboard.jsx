import { useEffect, useMemo, useState } from "react";
import { fetchSeasonDashboard } from "../api.js";
import { eur, num } from "../utils/money.js";

const PIE_COLORS = [
  "#c4a574",
  "#7dbe9a",
  "#6b9bd1",
  "#e07a9a",
  "#e8a87c",
  "#9b8ec4",
  "#5bbdbd",
  "#d4a5a5",
];

function genderAmount(byGender, key) {
  const row = (byGender || []).find((g) => g.gender === key);
  return num(row?.orders_eur);
}

function pct(part, total) {
  if (!total) return 0;
  return Math.round((part / total) * 1000) / 10;
}

function formatCompactEur(value) {
  const n = num(value);
  if (n >= 1000) {
    return `${(n / 1000).toLocaleString("ru-RU", {
      maximumFractionDigits: 1,
    })}k €`;
  }
  return eur(n);
}

/** SVG donut: items[{ label, amount, color }] */
function DonutChart({ items, emptyLabel }) {
  const total = items.reduce((acc, it) => acc + it.amount, 0);
  if (!total) {
    return (
      <div className="dash-donut dash-donut--empty">
        <span>{emptyLabel}</span>
      </div>
    );
  }

  const size = 160;
  const stroke = 28;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <svg
      className="dash-donut"
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      aria-hidden
    >
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke="var(--surface-2)"
        strokeWidth={stroke}
      />
      {items.map((it) => {
        const len = (it.amount / total) * c;
        const el = (
          <circle
            key={it.key}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={it.color}
            strokeWidth={stroke}
            strokeDasharray={`${len} ${c - len}`}
            strokeDashoffset={-offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        );
        offset += len;
        return el;
      })}
    </svg>
  );
}

function TotalsBarChart({ totals }) {
  const series = [
    { key: "orders", label: "Заказ", value: num(totals.orders_eur), color: "var(--accent)" },
    { key: "paid", label: "Оплата", value: num(totals.paid_eur), color: "var(--ok)" },
    { key: "shipped", label: "Поставки", value: num(totals.shipped_eur), color: "var(--warn)" },
  ];
  const max = Math.max(...series.map((s) => s.value), 1);

  return (
    <div className="dash-bars">
      {series.map((s) => (
        <div key={s.key} className="dash-bars__col">
          <div className="dash-bars__value">{formatCompactEur(s.value)}</div>
          <div className="dash-bars__track">
            <div
              className="dash-bars__fill"
              style={{
                height: `${Math.max(4, (s.value / max) * 100)}%`,
                background: s.color,
              }}
            />
          </div>
          <div className="dash-bars__label">{s.label}</div>
        </div>
      ))}
    </div>
  );
}

function GenderProgress({ byGender }) {
  const men = genderAmount(byGender, "men");
  const women = genderAmount(byGender, "women");
  const mixed = genderAmount(byGender, "mixed");
  const unknown = genderAmount(byGender, "unknown");
  const other = mixed + unknown;
  const total = men + women + other;

  if (!total) {
    return <p className="empty" style={{ padding: "0.5rem 0" }}>Нет заказов в сезоне</p>;
  }

  const menPct = pct(men, total);
  const womenPct = pct(women, total);
  const otherPct = pct(other, total);

  return (
    <div className="dash-gender">
      <div className="dash-gender__sums">
        <span className="dash-gender__sum dash-gender__sum--men">
          Муж {eur(men)}
        </span>
        <span className="dash-gender__sum dash-gender__sum--women">
          Жен {eur(women)}
        </span>
        {other > 0 ? (
          <span className="dash-gender__sum dash-gender__sum--other">
            Прочее {eur(other)}
          </span>
        ) : null}
      </div>
      <div className="dash-gender__bar" role="img" aria-label="Распределение заказа по полу">
        {men > 0 ? (
          <div
            className="dash-gender__seg dash-gender__seg--men"
            style={{ width: `${(men / total) * 100}%` }}
          />
        ) : null}
        {women > 0 ? (
          <div
            className="dash-gender__seg dash-gender__seg--women"
            style={{ width: `${(women / total) * 100}%` }}
          />
        ) : null}
        {other > 0 ? (
          <div
            className="dash-gender__seg dash-gender__seg--other"
            style={{ width: `${(other / total) * 100}%` }}
          />
        ) : null}
      </div>
      <div className="dash-gender__pcts">
        <span className="dash-gender__pct dash-gender__pct--men">{menPct}%</span>
        <span className="dash-gender__pct dash-gender__pct--women">{womenPct}%</span>
        {other > 0 ? (
          <span className="dash-gender__pct dash-gender__pct--other">{otherPct}%</span>
        ) : null}
      </div>
    </div>
  );
}

function PieBlock({ title, items, emptyLabel }) {
  const chartItems = useMemo(
    () =>
      (items || []).map((it, i) => ({
        key: it.key,
        label: it.label,
        amount: num(it.amount),
        color: PIE_COLORS[i % PIE_COLORS.length],
      })),
    [items],
  );
  const total = chartItems.reduce((a, x) => a + x.amount, 0);

  return (
    <div className="dash-card">
      <h3 className="dash-card__title">{title}</h3>
      <div className="dash-pie">
        <DonutChart items={chartItems} emptyLabel={emptyLabel} />
        {!chartItems.length ? (
          <p className="empty" style={{ margin: 0 }}>
            {emptyLabel}
          </p>
        ) : (
          <ul className="dash-legend">
            {chartItems.map((it) => (
              <li key={it.key}>
                <span className="dash-legend__swatch" style={{ background: it.color }} />
                <span className="dash-legend__name">{it.label}</span>
                <span className="dash-legend__meta">
                  {eur(it.amount)} · {pct(it.amount, total)}%
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function BrandPieBlock({ items }) {
  const mapped = useMemo(
    () =>
      (items || []).map((it) => ({
        key: it.brand_id,
        label: it.brand_name,
        amount: it.amount_eur,
      })),
    [items],
  );
  return <PieBlock title="Бренды" items={mapped} emptyLabel="Нет заказов" />;
}

function CategoryPieBlock({ title, items }) {
  const withAmount = useMemo(
    () => (items || []).filter((it) => num(it.amount_eur) > 0),
    [items],
  );
  const mapped = useMemo(
    () =>
      withAmount.map((it) => ({
        key: it.category_id,
        label: it.category_name,
        amount: it.amount_eur,
      })),
    [withAmount],
  );
  const showPlan = (items || []).some((it) => it.plan_eur != null);

  return (
    <>
      <PieBlock title={title} items={mapped} emptyLabel="Категории не заданы" />
      {showPlan ? <CategoryPlanList items={items} /> : null}
    </>
  );
}

function formatSignedEur(value) {
  const n = num(value);
  const abs = eur(Math.abs(n));
  if (n > 0) return `+${abs}`;
  if (n < 0) return `−${abs}`;
  return abs;
}

function CategoryPlanList({ items }) {
  const rows = useMemo(
    () =>
      (items || []).filter((it) => it.plan_eur != null),
    [items],
  );
  if (!rows.length) return null;

  return (
    <div className="dash-card dash-plan">
      <h3 className="dash-card__title">План · факт</h3>
      <div className="dash-plan__table-wrap">
        <table className="dash-plan__table">
          <thead>
            <tr>
              <th>Категория</th>
              <th>План</th>
              <th>Факт</th>
              <th>Разница</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const delta = num(row.delta_eur);
              const tone =
                delta > 0 ? "dash-plan__delta--over" : delta < 0 ? "dash-plan__delta--under" : "";
              return (
                <tr key={row.category_id}>
                  <td>{row.category_name}</td>
                  <td>{eur(row.plan_eur)}</td>
                  <td>{eur(row.amount_eur)}</td>
                  <td className={tone}>{formatSignedEur(delta)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="field-hint" style={{ marginBottom: 0 }}>
        Разница = факт − план: «−» недобор, «+» перезаказ
      </p>
    </div>
  );
}

function SeasonSection({ data }) {
  return (
    <section className="dash-season-block">
      <div className="dash-season">
        <div className="dash-season__name">{data.season_name}</div>
        <div className="dash-season__code">{data.season_code}</div>
      </div>

      <div className="dash-card">
        <h3 className="dash-card__title">Заказ · Оплата · Поставки</h3>
        <TotalsBarChart totals={data.totals} />
        <p className="field-hint" style={{ marginBottom: 0 }}>
          Заказов: {data.totals.orders_count} · к оплате {eur(data.totals.balance_to_pay_eur)} · к
          поставке {eur(data.totals.balance_to_ship_eur)}
        </p>
      </div>

      <div className="dash-card">
        <h3 className="dash-card__title">Заказ: муж / жен</h3>
        <GenderProgress byGender={data.by_gender} />
      </div>

      <BrandPieBlock items={data.by_brand} />

      <CategoryPieBlock title="Категории · муж" items={data.by_category_men} />
      <CategoryPieBlock title="Категории · жен" items={data.by_category_women} />
    </section>
  );
}

export default function Dashboard() {
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchSeasonDashboard()
      .then((res) => {
        if (active) setItems(res.items || []);
      })
      .catch((e) => {
        if (active) setErr(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) return <p className="loading">Загрузка…</p>;
  if (err) return <p className="error">{err}</p>;
  if (!items.length) return <p className="empty">Нет сезонов на дашборде</p>;

  return (
    <div className="dash">
      {items.map((data) => (
        <SeasonSection key={data.season_id} data={data} />
      ))}
    </div>
  );
}
