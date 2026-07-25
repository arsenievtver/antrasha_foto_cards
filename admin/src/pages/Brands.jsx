import { useCallback, useEffect, useState } from "react";
import {
  createBrand,
  fetchBrandProcurementStats,
  fetchBrandStats,
  fetchBrands,
  fetchSeasons,
} from "../api.js";
import { balanceStyle, dateRu, eur, genderLabel, kg } from "../utils/money.js";

function BrandDetail({ brandId, onClose }) {
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    setStats(null);
    setErr("");
    fetchBrandProcurementStats(brandId)
      .then(setStats)
      .catch((e) => setErr(e.message));
  }, [brandId]);

  if (err) return <p className="error">{err}</p>;
  if (!stats) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  return (
    <div className="card" style={{ marginBottom: "1.5rem" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "1rem",
        }}
      >
        <h3 style={{ margin: 0 }}>{stats.brand_name}</h3>
        <button type="button" className="secondary" onClick={onClose}>
          Закрыть
        </button>
      </div>

      <div className="stats-grid" style={{ marginTop: "1rem" }}>
        <div className="stat">
          <div className="v">{eur(stats.orders_eur)}</div>
          <div className="k">Заказано ({stats.orders_count} шт. заказов)</div>
        </div>
        <div className="stat">
          <div className="v">{eur(stats.paid_eur)}</div>
          <div className="k">Оплачено всего</div>
        </div>
        <div className="stat">
          <div className="v">{eur(stats.prepaid_eur)}</div>
          <div className="k">Из них предоплата</div>
        </div>
        <div className="stat">
          <div className="v">{eur(stats.shipped_eur)}</div>
          <div className="k">Поставлено ({kg(stats.shipped_weight_kg)})</div>
        </div>
        <div className="stat">
          <div className="v" style={balanceStyle(stats.balance_to_pay_eur)}>
            {eur(stats.balance_to_pay_eur)}
          </div>
          <div className="k">Остаток к оплате</div>
        </div>
        <div className="stat">
          <div className="v" style={balanceStyle(stats.balance_to_ship_eur)}>
            {eur(stats.balance_to_ship_eur)}
          </div>
          <div className="k">Остаток к поставке</div>
        </div>
        <div className="stat">
          <div className="v" style={balanceStyle(stats.prepayment_due_eur)}>
            {eur(stats.prepayment_due_eur)}
          </div>
          <div className="k">
            Предоплата не закрыта
            {stats.nearest_prepayment_due_on
              ? ` · срок ${dateRu(stats.nearest_prepayment_due_on)}`
              : ""}
          </div>
        </div>
      </div>

      <h4 style={{ marginBottom: "0.5rem" }}>По сезонам</h4>
      {!stats.by_season.length ? (
        <p style={{ color: "var(--muted)" }}>Данных нет.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Сезон</th>
              <th>Заказов</th>
              <th>Заказано</th>
              <th>Оплачено</th>
              <th>Поставлено</th>
              <th>К оплате</th>
              <th>К поставке</th>
            </tr>
          </thead>
          <tbody>
            {stats.by_season.map((s) => (
              <tr key={s.season_id}>
                <td>{s.season_name}</td>
                <td>{s.orders_count}</td>
                <td>{eur(s.orders_eur)}</td>
                <td>{eur(s.paid_eur)}</td>
                <td>{eur(s.shipped_eur)}</td>
                <td style={balanceStyle(s.balance_to_pay_eur)}>{eur(s.balance_to_pay_eur)}</td>
                <td style={balanceStyle(s.balance_to_ship_eur)}>
                  {eur(s.balance_to_ship_eur)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h4 style={{ marginBottom: "0.5rem" }}>По категориям</h4>
      {!stats.by_category.length ? (
        <p style={{ color: "var(--muted)" }}>Разбивка по категориям не заполнена.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Категория</th>
              <th>Пол</th>
              <th>Заказано</th>
            </tr>
          </thead>
          <tbody>
            {stats.by_category.map((c) => (
              <tr key={c.category_id}>
                <td>{c.category_name}</td>
                <td>{genderLabel(c.category_gender)}</td>
                <td>{eur(c.amount_eur)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function Brands() {
  const [brands, setBrands] = useState([]);
  const [statsByBrand, setStatsByBrand] = useState({});
  const [seasons, setSeasons] = useState([]);
  const [seasonId, setSeasonId] = useState("");
  const [selected, setSelected] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const [brandsRes, statsRes] = await Promise.all([
        fetchBrands(),
        fetchBrandStats(seasonId ? { season_id: seasonId } : undefined),
      ]);
      setBrands(brandsRes.items || []);
      const map = {};
      for (const s of statsRes.items || []) map[s.brand_id] = s;
      setStatsByBrand(map);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [seasonId]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    fetchSeasons()
      .then((res) => setSeasons(res.items || []))
      .catch((e) => setErr(e.message));
  }, []);

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await createBrand(name.trim());
      setName("");
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Бренды</h2>
      <p style={{ color: "var(--muted)", maxWidth: 760 }}>
        Сводка по закупкам: сколько заказано, оплачено и поставлено. Откройте бренд,
        чтобы увидеть разбивку по сезонам и категориям.
      </p>

      {err ? <p className="error">{err}</p> : null}

      {selected ? (
        <BrandDetail brandId={selected} onClose={() => setSelected("")} />
      ) : null}

      <div className="card" style={{ maxWidth: 460, marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новый бренд</h3>
        <form className="form-stack" onSubmit={onCreate}>
          <label>
            Название
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Название бренда"
              required
            />
          </label>
          <button type="submit" disabled={busy || !name.trim()}>
            {busy ? "Создание…" : "Добавить бренд"}
          </button>
        </form>
      </div>

      <div className="card">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-end",
            gap: "1rem",
            flexWrap: "wrap",
          }}
        >
          <h3 style={{ margin: 0 }}>Сводка ({brands.length})</h3>
          <label style={{ minWidth: 220 }}>
            Сезон
            <select value={seasonId} onChange={(e) => setSeasonId(e.target.value)}>
              <option value="">Все сезоны</option>
              {seasons.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !brands.length ? (
          <p style={{ color: "var(--muted)" }}>Брендов нет.</p>
        ) : (
          <table style={{ marginTop: "0.75rem" }}>
            <thead>
              <tr>
                <th>Бренд</th>
                <th>Заказов</th>
                <th>Заказано</th>
                <th>Оплачено</th>
                <th>Поставлено</th>
                <th>К оплате</th>
                <th>К поставке</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {brands.map((b) => {
                const s = statsByBrand[b.id];
                return (
                  <tr key={b.id}>
                    <td>{b.name}</td>
                    <td>{s?.orders_count ?? 0}</td>
                    <td>{eur(s?.orders_eur)}</td>
                    <td>{eur(s?.paid_eur)}</td>
                    <td>{eur(s?.shipped_eur)}</td>
                    <td style={balanceStyle(s?.balance_to_pay_eur)}>
                      {eur(s?.balance_to_pay_eur)}
                    </td>
                    <td style={balanceStyle(s?.balance_to_ship_eur)}>
                      {eur(s?.balance_to_ship_eur)}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => setSelected(b.id)}
                      >
                        Статистика
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
