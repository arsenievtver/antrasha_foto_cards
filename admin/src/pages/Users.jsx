import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createUser, deleteUser, fetchUsers, updateUser } from "../api.js";
import {
	digitsOnly,
	formatPhoneMask,
	formatPinMask,
	formatPinMaskUpTo12,
	normalizePhoneRu,
	pinDigits,
	pinDigitsUpTo12,
} from "../utils/masks.js";

function phoneToMasked(phone) {
	if (!phone) return "";
	return formatPhoneMask(digitsOnly(phone));
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return iso;
  }
}

export default function Users() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 30;
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const [createOpen, setCreateOpen] = useState(false);
  const [createPhone, setCreatePhone] = useState("");
  const [createPin, setCreatePin] = useState("");
  const [createRole, setCreateRole] = useState("user");

  const [editUser, setEditUser] = useState(null);
  const [editPhone, setEditPhone] = useState("");
  const [editPin, setEditPin] = useState("");
  const [editRole, setEditRole] = useState("user");
  const [saving, setSaving] = useState(false);

  async function load() {
    setErr("");
    const data = await fetchUsers({ skip, limit });
    setItems(data.items || []);
    setTotal(data.total ?? 0);
  }

  useEffect(() => {
    let c = false;
    (async () => {
      setLoading(true);
      try {
        await load();
      } catch (e) {
        if (!c) setErr(e.message);
      } finally {
        if (!c) setLoading(false);
      }
    })();
    return () => {
      c = true;
    };
  }, [skip]);

  function openEdit(u) {
    setEditUser(u);
    setEditPhone(phoneToMasked(u.phone));
    setEditPin("");
    setEditRole(u.role);
    setErr("");
  }

  async function submitCreate(e) {
    e.preventDefault();
    setSaving(true);
    setErr("");
    try {
      const norm = normalizePhoneRu(createPhone);
      if (!norm) {
        setErr("Укажите корректный номер телефона");
        setSaving(false);
        return;
      }
      const p =
        createRole === "worker"
          ? pinDigits(createPin)
          : pinDigitsUpTo12(createPin);
      if (createRole === "worker" && p.length !== 6) {
        setErr("Для сотрудника PIN — ровно 6 цифр (•••-•••)");
        setSaving(false);
        return;
      }
      if (createRole === "user" && (p.length < 4 || p.length > 12)) {
        setErr("PIN пользователя: от 4 до 12 цифр");
        setSaving(false);
        return;
      }
      await createUser({
        phone: norm,
        pin: p,
        role: createRole,
      });
      setCreateOpen(false);
      setCreatePhone("");
      setCreatePin("");
      setCreateRole("user");
      await load();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setSaving(false);
    }
  }

  async function submitEdit(e) {
    e.preventDefault();
    if (!editUser) return;
    setSaving(true);
    setErr("");
    try {
      const norm = normalizePhoneRu(editPhone);
      if (!norm) {
        setErr("Укажите корректный номер телефона");
        setSaving(false);
        return;
      }
      const body = {
        phone: norm,
        role: editRole,
      };
      const newPin =
        editRole === "worker"
          ? pinDigits(editPin)
          : pinDigitsUpTo12(editPin);
      const promoting =
        editRole === "worker" && editUser.role !== "worker";
      if (promoting && newPin.length !== 6) {
        setErr("При назначении роли «Сотрудник» укажите новый PIN (6 цифр).");
        setSaving(false);
        return;
      }
      if (newPin.length > 0) {
        if (editRole === "worker" && newPin.length !== 6) {
          setErr("PIN сотрудника — ровно 6 цифр (•••-•••)");
          setSaving(false);
          return;
        }
        if (
          editRole === "user" &&
          (newPin.length < 4 || newPin.length > 12)
        ) {
          setErr("PIN пользователя: от 4 до 12 цифр");
          setSaving(false);
          return;
        }
        body.pin = newPin;
      }
      await updateUser(editUser.id, body);
      setEditUser(null);
      await load();
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setSaving(false);
    }
  }

  async function onDelete(u) {
    if (
      !confirm(
        `Удалить пользователя ${u.phone}? Связанные данные (лайки, веса тегов) будут удалены.`,
      )
    ) {
      return;
    }
    setErr("");
    try {
      await deleteUser(u.id);
      await load();
    } catch (ex) {
      setErr(ex.message);
    }
  }

  if (loading && items.length === 0) {
    return <p style={{ color: "var(--muted)" }}>Загрузка…</p>;
  }

  const canMore = skip + items.length < total;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Пользователи и сотрудники</h2>
      <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
        Сотрудник (worker) входит в админку по телефону и 6-значному PIN. Обычный пользователь — по телефону и PIN (4–12 цифр) в приложении.
      </p>
      <div className="flex-gap" style={{ marginBottom: "1rem" }}>
        <button type="button" onClick={() => setCreateOpen(true)}>
          Добавить пользователя
        </button>
      </div>
      {err && <p className="error">{err}</p>}
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Имя</th>
              <th>Телефон</th>
              <th>Роль</th>
              <th>Последний вход</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link to={`/users/${u.id}`} className="table-link">
                    {u.display_name?.trim() || "—"}
                  </Link>
                </td>
                <td>{u.phone}</td>
                <td>{u.role === "worker" ? "Сотрудник" : "Пользователь"}</td>
                <td style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                  {fmtDate(u.last_login_at)}
                </td>
                <td>
                  <div className="flex-gap">
                    <button type="button" className="secondary" onClick={() => openEdit(u)}>
                      Изменить
                    </button>
                    <button type="button" className="danger" onClick={() => onDelete(u)}>
                      Удалить
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex-gap" style={{ marginTop: "1rem" }}>
        <button
          type="button"
          className="secondary"
          disabled={skip === 0}
          onClick={() => setSkip((s) => Math.max(0, s - limit))}
        >
          Назад
        </button>
        <button
          type="button"
          className="secondary"
          disabled={!canMore}
          onClick={() => setSkip((s) => s + limit)}
        >
          Дальше
        </button>
      </div>

      {createOpen && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => !saving && setCreateOpen(false)}
        >
          <div className="modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>Новый пользователь</h3>
            <form className="form-stack" onSubmit={submitCreate}>
              <div>
                <label>Телефон</label>
                <input
                  inputMode="tel"
                  placeholder="+7 (999) 123-45-67"
                  value={createPhone}
                  onChange={(e) =>
                    setCreatePhone(formatPhoneMask(e.target.value))
                  }
                  required
                  autoComplete="tel"
                />
              </div>
              <div>
                <label>PIN</label>
                <input
                  inputMode="numeric"
                  placeholder={
                    createRole === "worker" ? "•••-•••" : "•••-••• или длиннее"
                  }
                  value={createPin}
                  onChange={(e) =>
                    setCreatePin(
                      createRole === "worker"
                        ? formatPinMask(e.target.value)
                        : formatPinMaskUpTo12(e.target.value),
                    )
                  }
                  required
                  autoComplete="new-password"
                />
                <small style={{ color: "var(--muted)" }}>
                  Сотрудник: 6 цифр (•••-•••). Пользователь: 4–12 цифр.
                </small>
              </div>
              <div>
                <label>Роль</label>
                <select
                  value={createRole}
                  onChange={(e) => {
                    const r = e.target.value;
                    setCreateRole(r);
                    setCreatePin((prev) =>
                      r === "worker"
                        ? formatPinMask(prev)
                        : formatPinMaskUpTo12(prev),
                    );
                  }}
                >
                  <option value="user">Пользователь</option>
                  <option value="worker">Сотрудник</option>
                </select>
              </div>
              <div className="flex-gap">
                <button type="submit" disabled={saving}>
                  {saving ? "Сохранение…" : "Создать"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={saving}
                  onClick={() => setCreateOpen(false)}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {editUser && (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => !saving && setEditUser(null)}
        >
          <div className="modal" role="dialog" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ marginTop: 0 }}>Изменить: {editUser.phone}</h3>
            <form className="form-stack" onSubmit={submitEdit}>
              <div>
                <label>Телефон</label>
                <input
                  inputMode="tel"
                  placeholder="+7 (999) 123-45-67"
                  value={editPhone}
                  onChange={(e) =>
                    setEditPhone(formatPhoneMask(e.target.value))
                  }
                  required
                  autoComplete="tel"
                />
              </div>
              <div>
                <label>Новый PIN (необязательно)</label>
                <input
                  inputMode="numeric"
                  value={editPin}
                  onChange={(e) =>
                    setEditPin(
                      editRole === "worker"
                        ? formatPinMask(e.target.value)
                        : formatPinMaskUpTo12(e.target.value),
                    )
                  }
                  placeholder="оставьте пустым, если не меняете"
                  autoComplete="new-password"
                />
                <small style={{ color: "var(--muted)" }}>
                  При переводе в «Сотрудник» укажите новый PIN из 6 цифр.
                </small>
              </div>
              <div>
                <label>Роль</label>
                <select
                  value={editRole}
                  onChange={(e) => {
                    const r = e.target.value;
                    setEditRole(r);
                    setEditPin((prev) =>
                      r === "worker"
                        ? formatPinMask(prev)
                        : formatPinMaskUpTo12(prev),
                    );
                  }}
                >
                  <option value="user">Пользователь</option>
                  <option value="worker">Сотрудник</option>
                </select>
              </div>
              <div className="flex-gap">
                <button type="submit" disabled={saving}>
                  {saving ? "Сохранение…" : "Сохранить"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={saving}
                  onClick={() => setEditUser(null)}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
