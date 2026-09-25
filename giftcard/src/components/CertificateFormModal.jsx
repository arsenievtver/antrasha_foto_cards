import { useState } from "react";
import { createCertificate } from "../api.js";
import Switch from "./Switch.jsx";

function digitsPhone(raw) {
  let value = String(raw || "").replace(/\D/g, "");
  if (!value.startsWith("7")) value = `7${value}`;
  return value.slice(0, 11);
}

export default function CertificateFormModal({ employeeDefault, onClose, onCreated }) {
  const [form, setForm] = useState({
    name: "",
    last_name: "",
    phone: "7",
    giver_name: "",
    giver_phone: "",
    nominal: "",
    description: "",
    employee: employeeDefault || "",
    indefinite: true,
    period: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function setField(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await createCertificate({
        nominal: Number(form.nominal) || 0,
        description: form.description,
        employee: form.employee,
        check_amount: 0,
        status: "ACTIVE",
        indefinite: form.indefinite,
        period: form.indefinite ? null : Number(form.period) || 0,
        name: form.name || null,
        last_name: form.last_name || null,
        phone: form.phone,
        giver_name: form.giver_name.trim() || null,
        giver_phone: form.giver_phone.trim() ? digitsPhone(form.giver_phone) : null,
        created_at: new Date().toISOString().slice(0, 10),
      });
      onCreated();
    } catch (err) {
      setError(err.message || "Не удалось создать сертификат");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal-sheet" onMouseDown={(event) => event.stopPropagation()}>
        <h2>Создать сертификат</h2>
        <form className="form-stack" onSubmit={onSubmit}>
          <label>
            Имя владельца
            <input value={form.name} onChange={(event) => setField("name", event.target.value)} />
          </label>
          <label>
            Фамилия владельца
            <input value={form.last_name} onChange={(event) => setField("last_name", event.target.value)} />
          </label>
          <label>
            Телефон владельца
            <input
              value={form.phone}
              required
              onChange={(event) => setField("phone", digitsPhone(event.target.value))}
            />
          </label>
          <label>
            Даритель
            <input
              value={form.giver_name}
              placeholder="ФИО, как в сообщении"
              onChange={(event) => setField("giver_name", event.target.value)}
            />
          </label>
          <label>
            Телефон дарителя
            <input
              value={form.giver_phone}
              placeholder="Куда продублировать сообщение"
              onChange={(event) => setField("giver_phone", event.target.value.replace(/\D/g, "").slice(0, 11))}
            />
          </label>
          <label>
            Сумма
            <input
              type="number"
              min="0"
              required
              value={form.nominal}
              onChange={(event) => setField("nominal", event.target.value)}
            />
          </label>
          <label>
            Описание
            <input value={form.description} onChange={(event) => setField("description", event.target.value)} />
          </label>
          <label>
            Сотрудник
            <input value={form.employee} onChange={(event) => setField("employee", event.target.value)} />
          </label>
          <Switch
            label="Бессрочный"
            checked={form.indefinite}
            onChange={(value) => setField("indefinite", value)}
          />
          <label>
            Период (дней)
            <input
              type="number"
              min="1"
              disabled={form.indefinite}
              value={form.period}
              onChange={(event) => setField("period", event.target.value)}
            />
          </label>
          {error ? <p className="error">{error}</p> : null}
          <div className="modal-actions">
            <button type="button" className="secondary" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" disabled={loading}>
              {loading ? "Создание…" : "Создать"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
