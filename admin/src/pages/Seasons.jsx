import { useCallback, useEffect, useState } from "react";
import { createSeason, deleteSeason, fetchSeasons, updateSeason } from "../api.js";

const EMPTY = { name: "", code: "", sort_order: 0 };

const VISIBILITY = [
  { key: "previous", label: "Предыдущий", title: "Предыдущий сезон в списках work" },
  { key: "current", label: "Текущий", title: "Текущий сезон: списки work и дашборд" },
  { key: "next", label: "Следующий", title: "Следующий сезон: списки work и дашборд" },
];

export default function Seasons() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(EMPTY);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editingId, setEditingId] = useState("");
  const [edit, setEdit] = useState(EMPTY);

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

  function setEditField(field, value) {
    setEdit((prev) => ({ ...prev, [field]: value }));
  }

  function startEdit(row) {
    setEditingId(row.id);
    setEdit({
      name: row.name,
      code: row.code,
      sort_order: row.sort_order ?? 0,
    });
  }

  function cancelEdit() {
    setEditingId("");
    setEdit(EMPTY);
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

  async function onSaveEdit() {
    if (!editingId) return;
    const name = edit.name.trim();
    const code = edit.code.trim();
    if (!name || !code) {
      setErr("Название и код обязательны");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await updateSeason(editingId, {
        name,
        code,
        sort_order: Number(edit.sort_order) || 0,
      });
      cancelEdit();
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

  async function onSetVisibility(row, slot) {
    setErr("");
    setBusy(true);
    try {
      await updateSeason(row.id, {
        visibility: row.visibility === slot ? null : slot,
      });
      await reload();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function onSetOrderPlan(row) {
    if (row.is_order_plan) return;
    setErr("");
    try {
      await updateSeason(row.id, { is_order_plan: true });
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
      if (editingId === row.id) cancelEdit();
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
        Код нужен для коротких подписей, например <code>ВЛ2027</code>.
        Отметьте три видимых сезона: предыдущий, текущий и следующий. Каждая роль
        только у одного сезона — новая галочка снимает её с другого. В work эти три
        кода фильтруют заказы, оплаты и поставки. Дашборд показывает текущий и
        следующий. Колонка «План» — один сезон раздела «Для заказа».
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
                {VISIBILITY.map((slot) => (
                  <th key={slot.key}>{slot.label}</th>
                ))}
                <th>План</th>
                <th>Название</th>
                <th>Код</th>
                <th>Порядок</th>
                <th>Статус</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {items.map((row) => {
                const isEditing = editingId === row.id;
                return (
                  <tr key={row.id}>
                    {VISIBILITY.map((slot) => (
                      <td key={slot.key}>
                        <label
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            cursor: "pointer",
                          }}
                          title={slot.title}
                        >
                          <input
                            type="checkbox"
                            checked={row.visibility === slot.key}
                            onChange={() => onSetVisibility(row, slot.key)}
                            disabled={busy}
                          />
                        </label>
                      </td>
                    ))}
                    <td>
                      <label
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "0.35rem",
                          cursor: "pointer",
                          whiteSpace: "nowrap",
                        }}
                        title="Сезон раздела «Для заказа» и планов категорий"
                      >
                        <input
                          type="radio"
                          name="order-plan-season"
                          checked={Boolean(row.is_order_plan)}
                          onChange={() => onSetOrderPlan(row)}
                          disabled={busy}
                        />
                        {row.is_order_plan ? "Да" : ""}
                      </label>
                    </td>
                    <td>
                      {isEditing ? (
                        <input
                          value={edit.name}
                          onChange={(e) => setEditField("name", e.target.value)}
                          maxLength={120}
                          autoFocus
                        />
                      ) : (
                        row.name
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <input
                          value={edit.code}
                          onChange={(e) => setEditField("code", e.target.value)}
                          maxLength={32}
                        />
                      ) : (
                        <code>{row.code}</code>
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <input
                          type="number"
                          value={edit.sort_order}
                          onChange={(e) => setEditField("sort_order", e.target.value)}
                          style={{ width: 80 }}
                        />
                      ) : (
                        row.sort_order
                      )}
                    </td>
                    <td>{row.is_active ? "Активен" : "Архив"}</td>
                    <td>
                      <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                        {isEditing ? (
                          <>
                            <button type="button" onClick={onSaveEdit} disabled={busy}>
                              Сохранить
                            </button>
                            <button type="button" className="secondary" onClick={cancelEdit}>
                              Отмена
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => startEdit(row)}
                            >
                              Изменить
                            </button>
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => onToggle(row)}
                            >
                              {row.is_active ? "В архив" : "Вернуть"}
                            </button>
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => onDelete(row)}
                            >
                              Удалить
                            </button>
                          </>
                        )}
                      </div>
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
