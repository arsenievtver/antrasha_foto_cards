import { useEffect, useState } from "react";
import { createTag, deleteTag, fetchTags, updateTag } from "../api.js";

export default function Tags() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("style");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState("");
  const [editingName, setEditingName] = useState("");

  async function reload() {
    const data = await fetchTags();
    setItems(data.items || []);
  }

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        await reload();
      } catch (e) {
        if (!c) setErr(e.message);
      } finally {
        if (!c) setLoading(false);
      }
    })();
    return () => {
      c = true;
    };
  }, []);

  async function onCreate(e) {
    e.preventDefault();
    setErr("");
    try {
      await createTag(name.trim(), type.trim());
      setName("");
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onDelete(id) {
    if (!confirm("Удалить тег? Связи с фото тоже пропадут.")) return;
    setErr("");
    try {
      await deleteTag(id);
      if (editingId === id) {
        setEditingId("");
        setEditingName("");
      }
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onSaveEdit() {
    if (!editingId) return;
    const nextName = editingName.trim();
    if (!nextName) {
      setErr("Название тега не может быть пустым");
      return;
    }
    setErr("");
    try {
      await updateTag(editingId, nextName);
      setEditingId("");
      setEditingName("");
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  if (loading) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Теги</h2>
      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 style={{ marginTop: 0 }}>Новый тег</h3>
        <form className="form-stack" onSubmit={onCreate} style={{ maxWidth: 420 }}>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Название</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div style={{ flex: 1 }}>
              <label>Тип (категория)</label>
              <input value={type} onChange={(e) => setType(e.target.value)} required />
            </div>
          </div>
          {err && <p className="error">{err}</p>}
          <button type="submit">Добавить</button>
        </form>
      </div>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Тип</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id}>
                <td>
                  {editingId === t.id ? (
                    <input
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      maxLength={100}
                      autoFocus
                    />
                  ) : (
                    t.name
                  )}
                </td>
                <td>{t.type}</td>
                <td>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {editingId === t.id ? (
                      <>
                        <button type="button" onClick={onSaveEdit}>
                          Сохранить
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => {
                            setEditingId("");
                            setEditingName("");
                          }}
                        >
                          Отмена
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => {
                          setEditingId(t.id);
                          setEditingName(t.name);
                        }}
                      >
                        Переименовать
                      </button>
                    )}
                    <button type="button" className="danger" onClick={() => onDelete(t.id)}>
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
