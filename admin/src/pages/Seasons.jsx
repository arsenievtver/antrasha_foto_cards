import { useCallback, useEffect, useState } from "react";
import { createSeason, deleteSeason, fetchSeasons, updateSeason } from "../api.js";

const EMPTY = { name: "", code: "", sort_order: 0 };

export default function Seasons() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const res = await fetchSeasons();
      setItems(res.items || []);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onCreate(e) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await createSeason({
        name: form.name.trim(),
        code: form.code.trim(),
        sort_order: Number(form.sort_order) || 0,
      });
      setForm(EMPTY);
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onToggle(row) {
    setErr("");
    try {
      await updateSeason(row.id, { is_active: !row.is_active });
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onDelete(row) {
    if (!window.confirm(`Удалить сезон «${row.name}»?`)) return;
    setErr("");
    try {
      await deleteSeason(row.id);
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Сезоны</h2>
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Сезон закупки — ярлык, к которому привязываются заказы, оплаты и поставки.
        Код нужен для коротких подписей в отчётах, например <code>ВЛ2027</code>.
      </p>

      {err ? <p className="error">{err}</p> : null}

      <div className="card" style={{ maxWidth: 560, marginBottom: "1.5rem" }}>
        <h3 style={{ marginTop: 0 }}>Новый сезон</h3>
        <form className="form-stack" onSubmit={onCreate}>
          <label>
            Название
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              placeholder="Весна-Лето 2027"
              required
            />
          </label>
          <label>
            Код
            <input
              value={form.code}
              onChange={(e) => set("code", e.target.value)}
              placeholder="ВЛ2027"
              required
            />
          </label>
          <label>
            Порядок сортировки
            <input
              type="number"
              value={form.sort_order}
              onChange={(e) => set("sort_order", e.target.value)}
            />
            <span className="field-hint">
              Чем больше число, тем выше сезон в списках и выпадающих полях.
            </span>
          </label>
          <button type="submit" disabled={busy || !form.name.trim() || !form.code.trim()}>
            {busy ? "Создание…" : "Создать сезон"}
          </button>
        </form>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Список</h3>
        {loading ? (
          <p style={{ color: "var(--muted)" }}>Загрузка…</p>
        ) : !items.length ? (
          <p style={{ color: "var(--muted)" }}>Пока нет сезонов.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Код</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id}>
                  <td>{row.name}</td>
                  <td>
                    <code>{row.code}</code>
                  </td>
                  <td>{row.is_active ? "Активен" : "Архив"}</td>
                  <td>
                    <button type="button" className="secondary" onClick={() => onToggle(row)}>
                      {row.is_active ? "В архив" : "Вернуть"}
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      style={{ marginLeft: "0.4rem" }}
                      onClick={() => onDelete(row)}
                    >
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
