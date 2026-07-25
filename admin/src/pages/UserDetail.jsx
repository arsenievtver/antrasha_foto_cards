import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchUserDetail } from "../api.js";

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

export default function UserDetail() {
  const { userId } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let c = false;
    (async () => {
      setLoading(true);
      setErr("");
      try {
        const d = await fetchUserDetail(userId);
        if (!c) setData(d);
      } catch (e) {
        if (!c) setErr(e.message);
      } finally {
        if (!c) setLoading(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [userId]);

  if (loading) {
    return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;
  }
  if (err) return <p className="error">{err}</p>;
  if (!data?.user) return <p className="error">Нет данных</p>;

  const u = data.user;
  const weights = data.tag_weights || [];
  const pairWeights = data.tag_pair_weights || [];

  return (
    <div>
      <p style={{ marginTop: 0 }}>
        <Link to="/users">← К списку</Link>
      </p>
      <h2 style={{ marginTop: "0.5rem" }}>
        {u.display_name?.trim() || u.phone}
      </h2>
      <div className="card" style={{ marginBottom: "1rem" }}>
        <table className="detail-meta">
          <tbody>
            <tr>
              <th>Телефон</th>
              <td>{u.phone}</td>
            </tr>
            <tr>
              <th>Имя</th>
              <td>{u.display_name?.trim() || "—"}</td>
            </tr>
            <tr>
              <th>Роль</th>
              <td>{u.role === "worker" ? "Сотрудник" : "Клиент"}</td>
            </tr>
            <tr>
              <th>Создан</th>
              <td>{fmtDate(u.created_at)}</td>
            </tr>
            <tr>
              <th>Последний вход</th>
              <td>{fmtDate(u.last_login_at)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 style={{ marginTop: "1.25rem" }}>Статистика свайпов</h3>
      <div className="stats-grid" style={{ marginBottom: "1.25rem" }}>
        <div className="stat">
          <div className="v">{data.interactions_total}</div>
          <div className="k">Всего взаимодействий</div>
        </div>
        <div className="stat">
          <div className="v">{data.likes}</div>
          <div className="k">Лайков</div>
        </div>
        <div className="stat">
          <div className="v">{data.dislikes}</div>
          <div className="k">Дизлайков</div>
        </div>
        <div className="stat">
          <div className="v">
            {data.avg_view_time_ms != null
              ? Math.round(data.avg_view_time_ms)
              : "—"}
          </div>
          <div className="k">Среднее время просмотра (мс)</div>
        </div>
        <div className="stat">
          <div className="v">{data.interactions_male}</div>
          <div className="k">Свайпов (male)</div>
        </div>
        <div className="stat">
          <div className="v">{data.interactions_female}</div>
          <div className="k">Свайпов (female)</div>
        </div>
        <div className="stat">
          <div className="v">{data.likes_male}</div>
          <div className="k">Лайков (male)</div>
        </div>
        <div className="stat">
          <div className="v">{data.likes_female}</div>
          <div className="k">Лайков (female)</div>
        </div>
      </div>

      <h3>Веса тегов (профиль)</h3>
      <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginTop: 0 }}>
        Накопленные веса после лайков/дизлайков по каталогу тегов.
      </p>
      <div className="card">
        {weights.length === 0 ? (
          <p style={{ margin: 0, color: "var(--muted)" }}>Пока нет данных.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Тег</th>
                <th>Тип</th>
                <th>Вес</th>
              </tr>
            </thead>
            <tbody>
              {weights.map((w) => (
                <tr key={w.tag_id}>
                  <td>{w.tag_name}</td>
                  <td style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                    {w.tag_type}
                  </td>
                  <td>{Number(w.weight).toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <h3 style={{ marginTop: "1.5rem" }}>Парные веса (кросс-групповые)</h3>
      <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginTop: 0 }}>
        Сочетания вроде «тип изделия + принт» — сильнее влияют на ранжирование ленты.
      </p>
      <div className="card">
        {pairWeights.length === 0 ? (
          <p style={{ margin: 0, color: "var(--muted)" }}>Пока нет данных.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Тег A</th>
                <th>Тег B</th>
                <th>Вес</th>
              </tr>
            </thead>
            <tbody>
              {pairWeights.map((p) => (
                <tr key={`${p.tag_a_id}-${p.tag_b_id}`}>
                  <td>{p.tag_a_name}</td>
                  <td>{p.tag_b_name}</td>
                  <td>{Number(p.weight).toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
