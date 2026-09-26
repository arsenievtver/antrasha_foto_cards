import { useState } from "react";
import { createCertificate } from "../api.js";
import { normalizePhoneRu } from "../utils/masks.js";
import PhoneField from "./PhoneField.jsx";
import Switch from "./Switch.jsx";

function phoneForApi(masked) {
  const normalized = normalizePhoneRu(masked);
  return normalized ? normalized.slice(1) : "";
}

export default function CertificateFormModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: "",
    last_name: "",
    phone: "",
    giver_name: "",
    giver_phone: "",
    nominal: "",
    description: "",
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
      const phone = phoneForApi(form.phone);
      if (!phone) {
        setError("Укажите корректный телефон владельца");
        return;
      }
      const giverPhoneRaw = form.giver_phone.trim();
      const giverPhone = giverPhoneRaw ? phoneForApi(giverPhoneRaw) : "";
      if (giverPhoneRaw && !giverPhone) {
        setError("Укажите корректный телефон дарителя");
        return;
      }
      await createCertificate({
        nominal: Number(form.nominal) || 0,
        description: form.description,
        employee: "",
        check_amount: 0,
        status: "ACTIVE",
        indefinite: form.indefinite,
        period: form.indefinite ? null : Number(form.period) || 0,
        name: form.name || null,
        last_name: form.last_name || null,
        phone,
        giver_name: form.giver_name.trim() || null,
        giver_phone: giverPhone || null,
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
          <PhoneField
            label="Телефон владельца"
            value={form.phone}
            onChange={(value) => setField("phone", value)}
            required
          />
          <label>
            Даритель — ФИО, как в сообщении
            <input
              value={form.giver_name}
              onChange={(event) => setField("giver_name", event.target.value)}
            />
          </label>
          <PhoneField
            label="Телефон дарителя — куда продублировать сообщение"
            value={form.giver_phone}
            onChange={(value) => setField("giver_phone", value)}
          />
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
