import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ADMIN_PERMISSIONS,
  DEFAULT_WORKER_PERMISSIONS,
  createUser,
  deleteUser,
  fetchUsers,
  updateUser,
} from "../api.js";
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

function togglePerm(list, key) {
  const set = new Set(list || []);
  if (set.has(key)) set.delete(key);
  else set.add(key);
  const next = ADMIN_PERMISSIONS.map((p) => p.key).filter((k) => set.has(k));
  return next.length ? next : [...DEFAULT_WORKER_PERMISSIONS];
}

export default function Users() {
  const [tab, setTab] = useState("clients"); // clients | workers
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const limit = 30;
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);

  const [createOpen, setCreateOpen] = useState(false);
  const [createPhone, setCreatePhone] = useState("");
  const [createPin, setCreatePin] = useState("");
  const [createPerms, setCreatePerms] = useState([...DEFAULT_WORKER_PERMISSIONS]);

  const [editUser, setEditUser] = useState(null);
  const [editPhone, setEditPhone] = useState("");
  const [editPin, setEditPin] = useState("");
  const [saving, setSaving] = useState(false);
  const [permBusyId, setPermBusyId] = useState(null);

  const roleFilter = tab === "workers" ? "worker" : "user";

  async function load() {
    setErr("");
    const data = await fetchUsers({ skip, limit, role: roleFilter });
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
  }, [skip, tab]);

  function switchTab(next) {
    if (next === tab) return;
    setTab(next);
    setSkip(0);
    setErr("");
  }

  function openEdit(u) {
    setEditUser(u);
    setEditPhone(phoneToMasked(u.phone));
    setEditPin("");
    setErr("");
  }

  function openCreate() {
    setCreatePhone("");
    setCreatePin("");
    setCreatePerms([...DEFAULT_WORKER_PERMISSIONS]);
    setCreateOpen(true);
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
      const isWorker = tab === "workers";
      const p = isWorker ? pinDigits(createPin) : pinDigitsUpTo12(createPin);
      if (isWorker && p.length !== 6) {
        setErr("Для сотрудника PIN — ровно 6 цифр (•••-•••)");
        setSaving(false);
        return;
      }
      if (!isWorker && (p.length < 4 || p.length > 12)) {
        setErr("PIN клиента: от 4 до 12 цифр");
        setSaving(false);
        return;
      }
      await createUser({
        phone: norm,
        pin: p,
        role: isWorker ? "worker" : "user",
        admin_permissions: isWorker ? createPerms : undefined,
      });
      setCreateOpen(false);
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
      const body = { phone: norm };
      const isWorker = editUser.role === "worker";
      const newPin = isWorker ? pinDigits(editPin) : pinDigitsUpTo12(editPin);
      if (newPin.length > 0) {
        if (isWorker && newPin.length !== 6) {
          setErr("PIN сотрудника — ровно 6 цифр (•••-•••)");
          setSaving(false);
          return;
        }
        if (!isWorker && (newPin.length < 4 || newPin.length > 12)) {
          setErr("PIN клиента: от 4 до 12 цифр");
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

  async function onTogglePerm(u, key) {
    const next = togglePerm(u.admin_permissions, key);
    setPermBusyId(u.id);
    setErr("");
    try {
      const updated = await updateUser(u.id, { admin_permissions: next });
      setItems((prev) =>
        prev.map((row) => (row.id === u.id ? { ...row, ...updated } : row)),
      );
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setPermBusyId(null);
    }
  }

  async function onDelete(u) {
    const label = u.role === "worker" ? "сотрудника" : "клиента";
    if (
      !confirm(
        `Удалить ${label} ${u.phone}? Связанные данные (лайки, веса тегов) будут удалены.`,
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
  const isWorkers = tab === "workers";

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Клиенты и сотрудники</h2>
      <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
        Клиенты — приложение (телефон + PIN 4–12 цифр). Сотрудники — админка (PIN 6 цифр) с
        правами по разделам.
      </p>

      <div className="tabs" style={{ maxWidth: 420, marginBottom: "1rem" }}>
        <button
          type="button"
          className={!isWorkers ? "active" : ""}
          onClick={() => switchTab("clients")}
        >
          Клиенты
        </button>
        <button
          type="button"
          className={isWorkers ? "active" : ""}
          onClick={() => switchTab("workers")}
        >
          Сотрудники
        </button>
      </div>

      <div className="flex-gap" style={{ marginBottom: "1rem" }}>
        <button type="button" onClick={openCreate}>
          {isWorkers ? "Добавить сотрудника" : "Добавить клиента"}
        </button>
      </div>
      {err && <p className="error">{err}</p>}

      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>Имя</th>
              <th>Телефон</th>
              {isWorkers &&
                ADMIN_PERMISSIONS.map((p) => (
                  <th key={p.key} style={{ textAlign: "center", fontSize: "0.75rem" }}>
                    {p.label}
                  </th>
                ))}
              <th>Последний вход</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={isWorkers ? 3 + ADMIN_PERMISSIONS.length : 4} className="muted">
                  Пока пусто
                </td>
              </tr>
            )}
            {items.map((u) => (
              <tr key={u.id}>
                <td>
                  {u.role === "user" ? (
                    <Link to={`/users/${u.id}`} className="table-link">
                      {u.display_name?.trim() || "—"}
                    </Link>
                  ) : (
                    u.display_name?.trim() || "—"
                  )}
                </td>
                <td>{u.phone}</td>
                {isWorkers &&
                  ADMIN_PERMISSIONS.map((p) => {
                    const checked = (u.admin_permissions || []).includes(p.key);
                    const busy = permBusyId === u.id;
                    return (
                      <td key={p.key} style={{ textAlign: "center" }}>
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={busy}
                          title={p.label}
                          aria-label={`${p.label}: ${u.phone}`}
                          onChange={() => onTogglePerm(u, p.key)}
                        />
                      </td>
                    );
                  })}
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
        <span className="muted" style={{ alignSelf: "center" }}>
          {total ? `${skip + 1}–${skip + items.length} из ${total}` : "0"}
        </span>
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
            <h3 style={{ marginTop: 0 }}>
              {isWorkers ? "Новый сотрудник" : "Новый клиент"}
            </h3>
            <form className="form-stack" onSubmit={submitCreate}>
              <div>
                <label>Телефон</label>
                <input
                  inputMode="tel"
                  placeholder="+7 (999) 123-45-67"
                  value={createPhone}
                  onChange={(e) => setCreatePhone(formatPhoneMask(e.target.value))}
                  required
                  autoComplete="tel"
                />
              </div>
              <div>
                <label>PIN</label>
                <input
                  inputMode="numeric"
                  placeholder={isWorkers ? "•••-•••" : "•••-••• или длиннее"}
                  value={createPin}
                  onChange={(e) =>
                    setCreatePin(
                      isWorkers
                        ? formatPinMask(e.target.value)
                        : formatPinMaskUpTo12(e.target.value),
                    )
                  }
                  required
                  autoComplete="new-password"
                />
                <small style={{ color: "var(--muted)" }}>
                  {isWorkers
                    ? "Сотрудник: ровно 6 цифр (•••-•••)."
                    : "Клиент: от 4 до 12 цифр."}
                </small>
              </div>
              {isWorkers && (
                <div>
                  <label>Доступ к разделам</label>
                  <div className="perm-checks">
                    {ADMIN_PERMISSIONS.map((p) => (
                      <label key={p.key} className="perm-check">
                        <input
                          type="checkbox"
                          checked={createPerms.includes(p.key)}
                          onChange={() => setCreatePerms((prev) => togglePerm(prev, p.key))}
                        />
                        {p.label}
                      </label>
                    ))}
                  </div>
                </div>
              )}
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
                  onChange={(e) => setEditPhone(formatPhoneMask(e.target.value))}
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
                      editUser.role === "worker"
                        ? formatPinMask(e.target.value)
                        : formatPinMaskUpTo12(e.target.value),
                    )
                  }
                  placeholder="оставьте пустым, если не меняете"
                  autoComplete="new-password"
                />
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
