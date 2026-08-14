import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPrepaymentOverview } from "../api.js";
import { dateRu, eur, genderLabel, num } from "../utils/money.js";

const STATUS_META = {
  overdue: { label: "Просрочено", tone: "danger" },
  due_soon: { label: "Скоро", tone: "warn" },
  open: { label: "Открыто", tone: "muted" },
  paid: { label: "Оплачено", tone: "ok" },
};

function pct(part, total) {
  if (!total) return 0;
  return Math.min(100, Math.round((part / total) * 1000) / 10);
}

function formatCompactEur(value) {
  const n = num(value);
  if (Math.abs(n) >= 1000) {
    return `${(n / 1000).toLocaleString("ru-RU", {
      maximumFractionDigits: 1,
    })}k €`;
  }
  return eur(n);
}

function dueLabel(item) {
  if (!item.due_on) return "Без срока";
  const days = item.days_until_due;
  if (days == null) return dateRu(item.due_on);
  if (days < 0) {
    const n = Math.abs(days);
    return `−${n} дн · ${dateRu(item.due_on)}`;
  }
  if (days === 0) return `Сегодня · ${dateRu(item.due_on)}`;
  if (days === 1) return `Завтра · ${dateRu(item.due_on)}`;
  return `через ${days} дн · ${dateRu(item.due_on)}`;
}

function ProgressBar({ paid, planned, tone }) {
  const fill = pct(num(paid), num(planned));
  return (
    <div className="pp-progress" aria-hidden>
      <div
        className={`pp-progress__fill pp-progress__fill--${tone || "accent"}`}
        style={{ width: `${Math.max(fill, fill > 0 ? 3 : 0)}%` }}
      />
    </div>
  );
}

function KpiStrip({ totals }) {
  const planned = num(totals.planned_eur);
  const paid = num(totals.paid_eur);
  const outstanding = num(totals.outstanding_eur);
  const paidPct = pct(paid, planned);

  return (
    <div className="pp-kpi">
      <div className="pp-kpi__cell">
        <div className="pp-kpi__label">Начислено</div>
        <div className="pp-kpi__value">{formatCompactEur(planned)}</div>
      </div>
      <div className="pp-kpi__cell">
        <div className="pp-kpi__label">Оплачено</div>
        <div className="pp-kpi__value pp-kpi__value--ok">{formatCompactEur(paid)}</div>
      </div>
      <div className="pp-kpi__cell">
        <div className="pp-kpi__label">Остаток</div>
        <div
          className={`pp-kpi__value ${outstanding > 0 ? "pp-kpi__value--warn" : "pp-kpi__value--ok"}`}
        >
          {formatCompactEur(outstanding)}
        </div>
      </div>
      <div className="pp-kpi__bar-wrap">
        <div className="pp-kpi__bar-meta">
          <span>Оплачено {paidPct}%</span>
          <span>
            {totals.paid_count}/{totals.orders_count} закрыто
          </span>
        </div>
        <ProgressBar paid={paid} planned={planned} tone="ok" />
      </div>
    </div>
  );
}

function AlertBanner({ totals, dueSoonDays }) {
  const overdue = num(totals.overdue_count);
  const soon = num(totals.due_soon_count);
  if (!overdue && !soon) {
    if (!totals.orders_count) return null;
    return (
      <div className="pp-alert pp-alert--ok">
        <span className="pp-alert__title">Всё под контролем</span>
        <span className="pp-alert__meta">Нет просрочек и срочных предоплат</span>
      </div>
    );
  }

  return (
    <div className={`pp-alert ${overdue ? "pp-alert--danger" : "pp-alert--warn"}`}>
      <div className="pp-alert__row">
        {overdue > 0 ? (
          <div className="pp-alert__chip">
            <span className="pp-alert__chip-label">Просрочено</span>
            <span className="pp-alert__chip-value">
              {overdue} · {eur(totals.overdue_eur)}
            </span>
          </div>
        ) : null}
        {soon > 0 ? (
          <div className="pp-alert__chip">
            <span className="pp-alert__chip-label">≤ {dueSoonDays} дн</span>
            <span className="pp-alert__chip-value">
              {soon} · {eur(totals.due_soon_eur)}
            </span>
          </div>
        ) : null}
      </div>
      <p className="pp-alert__hint">
        {overdue > 0
          ? "Сначала закройте просроченные предоплаты — они сверху в каждом сезоне."
          : "Ближайшие сроки — оплатите вовремя, чтобы не уйти в просрочку."}
      </p>
    </div>
  );
}

function StatusFilter({ value, onChange, totals }) {
  const options = [
    { key: "all", label: "Все", count: totals.orders_count },
    { key: "overdue", label: "Просрочка", count: totals.overdue_count },
    { key: "due_soon", label: "Скоро", count: totals.due_soon_count },
    { key: "open", label: "Открыто", count: totals.open_count },
    { key: "paid", label: "Оплачено", count: totals.paid_count },
  ];

  return (
    <div className="pp-filters" role="tablist" aria-label="Фильтр статуса">
      {options.map((opt) => (
        <button
          key={opt.key}
          type="button"
          role="tab"
          aria-selected={value === opt.key}
          className={`pp-filters__btn${value === opt.key ? " is-active" : ""}`}
          onClick={() => onChange(opt.key)}
        >
          {opt.label}
          <span className="pp-filters__count">{opt.count}</span>
        </button>
      ))}
    </div>
  );
}

function PrepaymentRow({ item }) {
  const meta = STATUS_META[item.status] || STATUS_META.open;
  const planned = num(item.prepayment_amount_eur);
  const paid = num(item.prepaid_eur);
  const outstanding = num(item.outstanding_eur);
  const fillTone =
    item.status === "overdue"
      ? "danger"
      : item.status === "due_soon"
        ? "warn"
        : item.status === "paid"
          ? "ok"
          : "accent";

  return (
    <Link to={`/orders/${item.order_id}`} className={`pp-row pp-row--${meta.tone}`}>
      <div className="pp-row__top">
        <div className="pp-row__brand">{item.brand_name}</div>
        <span className={`pp-badge pp-badge--${meta.tone}`}>{meta.label}</span>
      </div>
      <div className="pp-row__due">{dueLabel(item)}</div>
      <ProgressBar paid={paid} planned={planned} tone={fillTone} />
      <div className="pp-row__foot">
        <span className="pp-row__money">
          {eur(paid)}
          <span className="pp-row__sep">/</span>
          {eur(planned)}
        </span>
        {outstanding > 0 ? (
          <span className={`pp-row__left pp-row__left--${meta.tone}`}>
            ещё {eur(outstanding)}
          </span>
        ) : (
          <span className="pp-row__left pp-row__left--ok">закрыто</span>
        )}
      </div>
      {item.gender ? (
        <div className="pp-row__meta">{genderLabel(item.gender)}</div>
      ) : null}
    </Link>
  );
}

function SeasonBlock({ season, filter }) {
  const items = useMemo(() => {
    const list = season.items || [];
    if (filter === "all") return list;
    return list.filter((it) => it.status === filter);
  }, [season.items, filter]);

  const hasAny = (season.items || []).length > 0;
  if (filter !== "all" && hasAny && !items.length) return null;

  return (
    <section className="pp-season">
      <header className="pp-season__head">
        <div>
          <div className="pp-season__name">{season.season_name}</div>
          <div className="pp-season__code">{season.season_code}</div>
        </div>
        {(season.totals.overdue_count > 0 || season.totals.due_soon_count > 0) && (
          <div className="pp-season__flags">
            {season.totals.overdue_count > 0 ? (
              <span className="pp-badge pp-badge--danger">
                {season.totals.overdue_count} проср.
              </span>
            ) : null}
            {season.totals.due_soon_count > 0 ? (
              <span className="pp-badge pp-badge--warn">
                {season.totals.due_soon_count} скоро
              </span>
            ) : null}
          </div>
        )}
      </header>

      {!hasAny ? (
        <div className="dash-card">
          <p className="empty" style={{ margin: 0, padding: "0.35rem 0" }}>
            В сезоне нет заказов с предоплатой
          </p>
        </div>
      ) : (
        <>
          <div className="dash-card">
            <KpiStrip totals={season.totals} />
          </div>
          <div className="pp-list">
            {items.map((item) => (
              <PrepaymentRow key={item.order_id} item={item} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export default function Prepayments() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchPrepaymentOverview()
      .then((res) => {
        if (!active) return;
        setData(res);
        const t = res?.totals;
        if (num(t?.overdue_count) > 0) setFilter("overdue");
        else if (num(t?.due_soon_count) > 0) setFilter("due_soon");
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
  if (!data?.items?.length) return <p className="empty">Нет сезонов на дашборде</p>;

  const totals = data.totals;

  return (
    <div className="pp">
      <AlertBanner totals={totals} dueSoonDays={data.due_soon_days} />

      <div className="dash-card">
        <h3 className="dash-card__title">Итого по сезонам PWA</h3>
        <KpiStrip totals={totals} />
      </div>

      <StatusFilter value={filter} onChange={setFilter} totals={totals} />

      {data.items.map((season) => (
        <SeasonBlock key={season.season_id} season={season} filter={filter} />
      ))}

      {filter !== "all" &&
      !(data.items || []).some((s) =>
        (s.items || []).some((it) => it.status === filter),
      ) ? (
        <p className="empty">Нет предоплат в выбранном статусе</p>
      ) : null}

      <p className="field-hint pp-footnote">
        На {dateRu(data.as_of)} · «Скоро» — срок в ближайшие {data.due_soon_days} дн.
      </p>
    </div>
  );
}
