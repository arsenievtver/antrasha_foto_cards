import { useEffect, useState } from "react";
import {
  createTag,
  createTagGroup,
  deleteTag,
  deleteTagGroup,
  fetchTagGroups,
  fetchTags,
  updateTag,
  updateTagGroup,
} from "../api.js";

export default function Tags() {
  const [groups, setGroups] = useState([]);
  const [items, setItems] = useState([]);
  const [name, setName] = useState("");
  const [groupId, setGroupId] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState("");
  const [editingName, setEditingName] = useState("");
  const [editingGroupId, setEditingGroupId] = useState("");
  const [editingGroupTitle, setEditingGroupTitle] = useState("");
  const [newGroupSlug, setNewGroupSlug] = useState("");
  const [newGroupTitle, setNewGroupTitle] = useState("");

  async function reload() {
    const [gr, tags] = await Promise.all([fetchTagGroups(), fetchTags()]);
    setGroups(gr.items || []);
    setItems(tags.items || []);
    if (!groupId && gr.items?.length) setGroupId(gr.items[0].id);
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
    if (!groupId) {
      setErr("Выберите группу (категорию)");
      return;
    }
    setErr("");
    try {
      await createTag(name.trim(), { groupId });
      setName("");
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onCreateGroup(e) {
    e.preventDefault();
    const slug = newGroupSlug.trim();
    const title = newGroupTitle.trim();
    if (!slug || !title) return;
    setErr("");
    try {
      const created = await createTagGroup({ slug, title });
      setNewGroupSlug("");
      setNewGroupTitle("");
      setGroupId(created.id);
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

  async function onDeleteGroup(id, title) {
    if (
      !confirm(
        `Удалить группу «${title}» и все её теги? Разметка на фото потеряет эти теги.`,
      )
    ) {
      return;
    }
    setErr("");
    try {
      await deleteTagGroup(id);
      if (groupId === id) setGroupId("");
      if (editingGroupId === id) {
        setEditingGroupId("");
        setEditingGroupTitle("");
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

  async function onSaveGroupTitle() {
    if (!editingGroupId) return;
    const title = editingGroupTitle.trim();
    if (!title) {
      setErr("Название группы не может быть пустым");
      return;
    }
    setErr("");
    try {
      await updateTagGroup(editingGroupId, { title });
      setEditingGroupId("");
      setEditingGroupTitle("");
      await reload();
    } catch (e) {
      setErr(e.message);
    }
  }

  if (loading) return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Теги</h2>
      {err ? <p className="error">{err}</p> : null}
      <p className="muted" style={{ marginTop: "-0.25rem", maxWidth: 640 }}>
        Группа (категория) хранится в базе — её название видно в разметке и на странице «Фото».
        Slug группы не меняйте без необходимости (на него завязаны старые записи type).
      </p>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 style={{ marginTop: 0 }}>Новая группа (категория)</h3>
        <form className="form-stack" onSubmit={onCreateGroup} style={{ maxWidth: 520 }}>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Slug (латиница, например color)</label>
              <input
                value={newGroupSlug}
                onChange={(e) => setNewGroupSlug(e.target.value)}
                required
                pattern="[a-z0-9_]+"
                title="латиница, цифры, подчёркивание"
              />
            </div>
            <div style={{ flex: 1 }}>
              <label>Название в интерфейсе</label>
              <input
                value={newGroupTitle}
                onChange={(e) => setNewGroupTitle(e.target.value)}
                required
                placeholder="Цвет"
              />
            </div>
          </div>
          <button type="submit" className="secondary">
            Создать группу
          </button>
        </form>
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 style={{ marginTop: 0 }}>Группы</h3>
        {groups.length === 0 ? (
          <p className="muted">Нет групп — создайте первую выше.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Название</th>
                <th>Slug</th>
                <th>Лимит тегов</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {groups.map((g) => (
                <tr key={g.id}>
                  <td>
                    {editingGroupId === g.id ? (
                      <input
                        value={editingGroupTitle}
                        onChange={(e) => setEditingGroupTitle(e.target.value)}
                        maxLength={200}
                        autoFocus
                      />
                    ) : (
                      g.title
                    )}
                  </td>
                  <td className="muted">{g.slug}</td>
                  <td className="muted">до {g.max_tags}</td>
                  <td>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      {editingGroupId === g.id ? (
                        <>
                          <button type="button" onClick={onSaveGroupTitle}>
                            Сохранить
                          </button>
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => {
                              setEditingGroupId("");
                              setEditingGroupTitle("");
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
                            setEditingGroupId(g.id);
                            setEditingGroupTitle(g.title);
                          }}
                        >
                          Переименовать
                        </button>
                      )}
                      <button
                        type="button"
                        className="danger"
                        onClick={() => onDeleteGroup(g.id, g.title)}
                      >
                        Удалить группу
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card" style={{ marginBottom: "1rem" }}>
        <h3 style={{ marginTop: 0 }}>Новый тег</h3>
        <form className="form-stack" onSubmit={onCreate} style={{ maxWidth: 420 }}>
          <div className="flex-gap">
            <div style={{ flex: 1 }}>
              <label>Название тега</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div style={{ flex: 1 }}>
              <label>Группа (категория)</label>
              <select value={groupId} onChange={(e) => setGroupId(e.target.value)} required>
                <option value="">— выберите —</option>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.title}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <button type="submit" disabled={!groups.length}>
            Добавить тег
          </button>
        </form>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Название</th>
              <th>Группа</th>
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
                <td>{t.group_title || t.group_slug || t.type}</td>
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
