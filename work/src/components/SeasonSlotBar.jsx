import { useEffect, useState } from "react";
import { fetchProcurementRefs, fetchSeasonDashboard } from "../api.js";
import { eur, num } from "../utils/money.js";

const STORAGE_KEY = "antrasha_work_season_slot";

export const SEASON_SLOTS = [
  { key: "previous", label: "Предыдущий" },
  { key: "current", label: "Текущий" },
  { key: "next", label: "Следующий" },
];

function compactEur(value) {
  const n = num(value);
  if (Math.abs(n) >= 1000) {
    return `${(n / 1000).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}k €`;
  }
  return eur(n);
}

export function pickDefaultSeasonId(seasons) {
  const visible = (seasons || []).filter((s) =>
    SEASON_SLOTS.some((slot) => slot.key === s.visibility),
  );
  let saved = "";
  try {
    saved = sessionStorage.getItem(STORAGE_KEY) || "";
  } catch {
    saved = "";
  }
  if (saved && visible.some((s) => s.id === saved)) return saved;
  const bySlot = Object.fromEntries(visible.map((s) => [s.visibility, s]));
  return bySlot.current?.id || bySlot.next?.id || bySlot.previous?.id || "";
}

export function rememberSeasonId(id) {
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* приватный режим */
  }
}

export function useVisibleSeasons() {
  const [seasons, setSeasons] = useState([]);
  const [seasonId, setSeasonIdState] = useState("");
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    let active = true;
    fetchProcurementRefs()
      .then((refs) => {
        if (!active) return;
        const list = refs.seasons || [];
        setSeasons(list);
        setSeasonIdState(pickDefaultSeasonId(list));
      })
      .catch((e) => {
        if (active) setErr(e.message);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, []);

  function setSeasonId(id) {
    setSeasonIdState(id);
    rememberSeasonId(id);
  }

  return { seasons, seasonId, setSeasonId, ready, err };
}

export default function SeasonSlotBar({ seasons, seasonId, onChange, ready = true }) {
  const [totals, setTotals] = useState(null);
  const [sumsErr, setSumsErr] = useState("");

  const bySlot = Object.fromEntries(
    (seasons || [])
      .filter((s) => SEASON_SLOTS.some((slot) => slot.key === s.visibility))
      .map((s) => [s.visibility, s]),
  );
  const hasAny = SEASON_SLOTS.some((slot) => bySlot[slot.key]);

  useEffect(() => {
    if (!seasonId) {
      setTotals(null);
      setSumsErr("");
      return undefined;
    }
    let active = true;
    setTotals(null);
    setSumsErr("");
    fetchSeasonDashboard(seasonId)
      .then((res) => {
        if (!active) return;
        setTotals(res.items?.[0]?.totals || null);
      })
      .catch((e) => {
        if (!active) return;
        setTotals(null);
        setSumsErr(e.message);
      });
    return () => {
      active = false;
    };
  }, [seasonId]);

  if (!ready) return null;

  if (!hasAny) {
    return (
      <p className="field-hint" style={{ marginTop: 0 }}>
        Отметьте предыдущий, текущий и следующий сезоны в админке.
      </p>
    );
  }

  return (
    <div className="season-bar">
      <div className="season-slots" role="tablist" aria-label="Сезон">
        {SEASON_SLOTS.map((slot) => {
          const season = bySlot[slot.key];
          if (!season) return <div key={slot.key} />;
          const active = season.id === seasonId;
          return (
            <button
              key={slot.key}
              type="button"
              role="tab"
              aria-selected={active}
              className={`season-slots__btn${active ? " is-active" : ""}`}
              title={season.name}
              onClick={() => onChange(season.id)}
            >
              <span className="season-slots__code">{season.code}</span>
              <span className="season-slots__role">{slot.label}</span>
            </button>
          );
        })}
      </div>

      {totals ? (
        <>
          <div className="season-sums">
            <div className="season-sums__cell">
              <div className="season-sums__label">Заказ</div>
              <div className="season-sums__value">{compactEur(totals.orders_eur)}</div>
            </div>
            <div className="season-sums__cell">
              <div className="season-sums__label">Оплата</div>
              <div className="season-sums__value">{compactEur(totals.paid_eur)}</div>
            </div>
            <div className="season-sums__cell">
              <div className="season-sums__label">Поставки</div>
              <div className="season-sums__value">{compactEur(totals.shipped_eur)}</div>
            </div>
          </div>
          <p className="season-sums__hint">
            к оплате {compactEur(totals.balance_to_pay_eur)} · к поставке{" "}
            {compactEur(totals.balance_to_ship_eur)}
          </p>
        </>
      ) : sumsErr ? (
        <p className="field-hint">Сводка сезона недоступна</p>
      ) : null}
    </div>
  );
}
