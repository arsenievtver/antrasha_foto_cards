import { useEffect, useState } from "react";
import { fetchStats } from "../api.js";

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

  if (err) return <p className="error">{err}</p>;
  if (!s) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  const cells = [
    ["Пользователи", s.users],
    ["Сотрудники (worker)", s.workers],
    ["Фото", s.photos],
    ["Активных фото", s.active_photos],
    ["Муж / Жен", `${s.photos_male} / ${s.photos_female}`],
    ["Теги", s.tags],
    ["Взаимодействия", s.interactions],
    ["Сессии (всего)", s.sessions_total ?? 0],
    ["Заходы по ссылкам", s.sessions_with_campaign ?? 0],
  ];

  const campaignVisits = s.campaign_visits ?? [];

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Статистика</h2>
      <div className="stats-grid">
        {cells.map(([k, v]) => (
          <div key={k} className="stat">
            <div className="v">{v}</div>
            <div className="k">{k}</div>
          </div>
        ))}
      </div>

      {campaignVisits.length > 0 ? (
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h3 style={{ marginTop: 0 }}>Заходы по рекламным ссылкам</h3>
          <table>
            <thead>
              <tr>
                <th>Кампания</th>
                <th>ref</th>
                <th>Заходы</th>
              </tr>
            </thead>
            <tbody>
              {campaignVisits.map((row) => (
                <tr key={row.campaign_id}>
                  <td>{row.name}</td>
                  <td>
                    <code>{row.slug}</code>
                  </td>
                  <td>{row.visits}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
