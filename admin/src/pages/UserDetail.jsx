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

function TastePreviewSection({ title, preview }) {
  if (!preview) {
    return (
      <div style={{ marginBottom: "1rem" }}>
        <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>{title}</h4>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>Нет данных.</p>
      </div>
    );
  }

  const ready = preview.taste_vector_ready;
  const photos = preview.nearest_photos || [];

  return (
    <div style={{ marginBottom: "1.25rem" }}>
      <h4 style={{ margin: "0 0 0.5rem", fontSize: "0.95rem" }}>{title}</h4>
      {!ready ? (
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>
          Профиль для этой коллекции ещё не собран — нужны лайки/дизлайки по фото с embedding.
        </p>
      ) : photos.length === 0 ? (
        <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.9rem" }}>
          Вектор есть (обновлений: {preview.taste_swipe_updates ?? 0}), но в каталоге нет фото для
          сравнения.
        </p>
      ) : (
        <>
          <p style={{ margin: "0 0 0.5rem", fontSize: "0.85rem", color: "var(--muted)" }}>
            Обновлений по этой коллекции: <strong>{preview.taste_swipe_updates ?? 0}</strong>
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
              gap: "0.75rem",
            }}
          >
            {photos.map((p) => (
              <figure key={p.photo_id} style={{ margin: 0 }}>
                <a href={p.url} target="_blank" rel="noreferrer">
                  <img
                    src={p.url}
                    alt=""
                    style={{
                      width: "100%",
                      aspectRatio: "3/4",
                      objectFit: "cover",
                      borderRadius: 8,
                      border: "1px solid var(--border)",
                    }}
                  />
                </a>
                <figcaption style={{ fontSize: "0.78rem", color: "var(--muted)", marginTop: 4 }}>
                  cosine {(Number(p.cosine) * 100).toFixed(0)}%
                  {p.brand ? ` · ${p.brand}` : ""}
                </figcaption>
              </figure>
            ))}
          </div>
        </>
      )}
    </div>
  );
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
  const previews = data.taste_previews || [];
  const malePreview = previews.find((p) => p.collection_gender === "male");
  const femalePreview = previews.find((p) => p.collection_gender === "female");

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
            <tr>
              <th>Push о новинках</th>
              <td>
                {data.push_subscribed
                  ? `Подписан${
                      data.push_gender_scope
                        ? ` (${data.push_gender_scope === "male" ? "муж." : data.push_gender_scope === "female" ? "жен." : "оба"})`
                        : ""
                    }`
                  : "Не подписан"}
              </td>
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

      <h3 style={{ marginTop: "1.25rem" }}>Вектор вкуса (превью)</h3>
      <p style={{ color: "var(--muted)", fontSize: "0.9rem", marginTop: 0 }}>
        До 4 образов из соответствующей коллекции с наибольшим cosine к профилю (k-NN по
        embedding). Male и female — отдельные профили, если в настройках ленты включён раздельный
        вкус.
      </p>
      <div className="card" style={{ marginBottom: "1.25rem" }}>
        <TastePreviewSection title="Ближайшие female" preview={femalePreview} />
        <TastePreviewSection title="Ближайшие male" preview={malePreview} />
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
                  <td>{w.tag_type}</td>
                  <td>{w.weight.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <h3 style={{ marginTop: "1.25rem" }}>Пары тегов</h3>
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
              {pairWeights.map((w) => (
                <tr key={`${w.tag_a_id}-${w.tag_b_id}`}>
                  <td>{w.tag_a_name}</td>
                  <td>{w.tag_b_name}</td>
                  <td>{w.weight.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
