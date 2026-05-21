import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStats } from "../api.js";

function fmt(n) {
  return Number(n ?? 0).toLocaleString("ru-RU");
}

function pct(n) {
  return `${Number(n ?? 0).toFixed(1)}%`;
}

function VisitBar({ value, max }) {
  const w = max > 0 ? Math.max(4, Math.round((100 * value) / max)) : 0;
  return (
    <div className="dash-bar" title={`${fmt(value)} заходов`}>
      <div className="dash-bar__fill" style={{ width: `${w}%` }} />
      <span className="dash-bar__n">{fmt(value)}</span>
    </div>
  );
}

function TrafficSplit({ attributed, organic, total }) {
  const aPct = total > 0 ? (100 * attributed) / total : 0;
  const oPct = total > 0 ? 100 - aPct : 0;
  return (
    <div className="dash-traffic-split">
      <div className="dash-traffic-split__track">
        <div
          className="dash-traffic-split__attr"
          style={{ width: `${aPct}%` }}
          title={`По ссылкам: ${fmt(attributed)}`}
        />
        <div
          className="dash-traffic-split__org"
          style={{ width: `${oPct}%` }}
          title={`Без ref: ${fmt(organic)}`}
        />
      </div>
      <div className="dash-traffic-split__legend">
        <span>
          <i className="dash-dot dash-dot--attr" /> По ссылкам — {fmt(attributed)} ({pct(aPct)})
        </span>
        <span>
          <i className="dash-dot dash-dot--org" /> Без ссылки — {fmt(organic)} ({pct(oPct)})
        </span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [s, setS] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchStats();
        if (!cancelled) setS(data);
      } catch (e) {
        if (!cancelled) setErr(e.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const campaigns = s?.campaign_visits ?? [];
  const maxVisits = useMemo(
    () => Math.max(1, ...campaigns.map((c) => c.visits)),
    [campaigns],
  );

  const attributed = s?.sessions_with_campaign ?? 0;
  const organic = s?.sessions_organic ?? 0;
  const sessionsTotal = s?.sessions_total ?? 0;

  const totals = useMemo(() => {
    if (!campaigns.length) return null;
    return campaigns.reduce(
      (acc, c) => ({
        visits: acc.visits + c.visits,
        visits_7d: acc.visits_7d + c.visits_7d,
        visits_30d: acc.visits_30d + c.visits_30d,
        interactions: acc.interactions + c.interactions,
        likes: acc.likes + c.likes,
        registrations: acc.registrations + c.registrations,
      }),
      {
        visits: 0,
        visits_7d: 0,
        visits_30d: 0,
        interactions: 0,
        likes: 0,
        registrations: 0,
      },
    );
  }, [campaigns]);

  if (err) return <p className="error">{err}</p>;
  if (!s) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  const appCells = [
    ["Пользователи", s.users],
    ["Фото активных", s.active_photos],
    ["Муж / жен", `${s.photos_male} / ${s.photos_female}`],
    ["Теги", s.tags],
    ["Свайпов всего", s.interactions],
  ];

  const trafficCells = [
    ["Сессии всего", sessionsTotal],
    ["По рекламным ссылкам", attributed],
    ["Без ссылки (органика)", organic],
    ["Кампаний", campaigns.length],
  ];

  return (
    <div className="dashboard">
      <h2 style={{ marginTop: 0 }}>Дашборд</h2>

      <section className="dash-section">
        <h3 className="dash-section__title">Приложение</h3>
        <div className="stats-grid">
          {appCells.map(([k, v]) => (
            <div key={k} className="stat">
              <div className="v">{v}</div>
              <div className="k">{k}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="dash-section">
        <h3 className="dash-section__title">Трафик</h3>
        <div className="stats-grid stats-grid--traffic">
          {trafficCells.map(([k, v]) => (
            <div key={k} className="stat">
              <div className="v">{typeof v === "number" ? fmt(v) : v}</div>
              <div className="k">{k}</div>
            </div>
          ))}
        </div>
        <div className="card dash-traffic-card">
          <div className="dash-traffic-card__label">Распределение заходов</div>
          <TrafficSplit
            attributed={attributed}
            organic={organic}
            total={sessionsTotal}
          />
        </div>
      </section>

      <section className="dash-section">
        <div className="dash-section__head">
          <h3 className="dash-section__title">Рекламные ссылки</h3>
          <Link to="/campaigns">Управление ссылками →</Link>
        </div>

        {!campaigns.length ? (
          <div className="card">
            <p style={{ color: "var(--muted)", margin: 0 }}>
              Кампаний пока нет.{" "}
              <Link to="/campaigns">Создайте первую ссылку</Link>, чтобы видеть
              статистику по каждой.
            </p>
          </div>
        ) : (
          <div className="card dash-campaigns-card">
            <div className="table-wrap">
              <table className="dash-campaigns-table">
                <thead>
                  <tr>
                    <th>Кампания</th>
                    <th>ref</th>
                    <th>Заходы</th>
                    <th>7 дн</th>
                    <th>30 дн</th>
                    <th>Вовлечённость</th>
                    <th>Свайпы</th>
                    <th>♥ / ✕</th>
                    <th>Регистрации</th>
                    <th>Доля</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((row) => (
                    <tr
                      key={row.campaign_id}
                      className={row.is_active ? "" : "dash-row--inactive"}
                    >
                      <td>
                        <div className="dash-campaign-name">{row.name}</div>
                        <div className="dash-campaign-meta">
                          <code>{row.path}</code>
                          {!row.is_active ? (
                            <span className="dash-badge">выкл</span>
                          ) : null}
                        </div>
                        <a
                          href={row.tracking_url}
                          target="_blank"
                          rel="noreferrer"
                          className="dash-campaign-link"
                        >
                          открыть ссылку
                        </a>
                      </td>
                      <td>
                        <code>{row.slug}</code>
                      </td>
                      <td className="dash-cell-bar">
                        <VisitBar value={row.visits} max={maxVisits} />
                      </td>
                      <td>{fmt(row.visits_7d)}</td>
                      <td>{fmt(row.visits_30d)}</td>
                      <td>
                        <span className="dash-metric-main">
                          {fmt(row.engaged_sessions)}
                        </span>
                        <span className="dash-metric-sub">
                          {pct(row.engagement_rate)}
                        </span>
                      </td>
                      <td>{fmt(row.interactions)}</td>
                      <td>
                        <span className="dash-like">{fmt(row.likes)}</span>
                        {" / "}
                        <span className="dash-dislike">{fmt(row.dislikes)}</span>
                      </td>
                      <td>{fmt(row.registrations)}</td>
                      <td>{pct(row.visit_share)}</td>
                    </tr>
                  ))}
                </tbody>
                {totals ? (
                  <tfoot>
                    <tr className="dash-tfoot">
                      <td colSpan={2}>
                        <strong>Итого по кампаниям</strong>
                      </td>
                      <td>{fmt(totals.visits)}</td>
                      <td>{fmt(totals.visits_7d)}</td>
                      <td>{fmt(totals.visits_30d)}</td>
                      <td>—</td>
                      <td>{fmt(totals.interactions)}</td>
                      <td>{fmt(totals.likes)}</td>
                      <td>{fmt(totals.registrations)}</td>
                      <td>100%</td>
                    </tr>
                  </tfoot>
                ) : null}
              </table>
            </div>
            <p className="dash-table-note">
              Заход — новая сессия с <code>?ref=</code>. Вовлечённость — сессии хотя бы с
              одним свайпом. Регистрации — пользователи, зарегистрировавшиеся после перехода
              по этой ссылке (с момента обновления).
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
