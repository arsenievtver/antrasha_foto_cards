import { useEffect, useState } from "react";
import { createTag, deleteTag, fetchTags } from "../api.js";

export default function Tags() {
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("style");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

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
                <td>{t.name}</td>
                <td>{t.type}</td>
                <td>
                  <button type="button" className="danger" onClick={() => onDelete(t.id)}>
                    Удалить
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
