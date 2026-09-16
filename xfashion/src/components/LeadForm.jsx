import { useState } from "react";
import { submitLead } from "../api.js";
import { formatPhoneMask, normalizePhoneRu } from "../utils/masks.js";
import { getStoredRef } from "../utils/ref.js";

const CHANNELS = [
  { id: "telegram", label: "Telegram" },
  { id: "vk", label: "VK" },
  { id: "phone", label: "Звонок" },
  { id: "email", label: "Email" },
  { id: "max", label: "MAX" },
];

export default function LeadForm({ id = "xf-lead" }) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [channel, setChannel] = useState("telegram");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [done, setDone] = useState(false);

  async function onSubmit(e) {
    e.preventDefault();
    setErr("");
    const norm = normalizePhoneRu(phone);
    if (!norm) {
      setErr("Укажите корректный номер телефона");
      return;
    }
    setBusy(true);
    try {
      await submitLead({
        phone: norm,
        name: name.trim() || null,
        contact_channel: CHANNELS.find((c) => c.id === channel)?.label || channel,
        message: message.trim() || null,
        ref: getStoredRef() || null,
      });
      setDone(true);
    } catch (ex) {
      setErr(ex.message || "Ошибка отправки");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="xf-lead xf-lead--done" id={id}>
        <h2>Заявка отправлена</h2>
        <p>Мы свяжемся с вами выбранным способом в ближайшее время.</p>
      </div>
    );
  }

  return (
    <form className="xf-lead" id={id} onSubmit={onSubmit}>
      <h2>Запросить презентацию</h2>
      <p className="xf-lead__hint">Как с вами связаться?</p>
      <div className="xf-channels" role="group" aria-label="Способ связи">
        {CHANNELS.map((c) => (
          <label key={c.id} className="xf-channel">
            <input
              type="radio"
              name="channel"
              value={c.id}
              checked={channel === c.id}
              onChange={() => setChannel(c.id)}
            />
            {c.label}
          </label>
        ))}
      </div>
      <label>
        Имя
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Необязательно" />
      </label>
      <label>
        Телефон
        <input
          value={phone}
          onChange={(e) => setPhone(formatPhoneMask(e.target.value))}
          placeholder="+7 (___) ___-__-__"
          required
          inputMode="tel"
          autoComplete="tel"
        />
      </label>
      <label>
        Комментарий
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          rows={3}
          placeholder="Магазин, город, маркетплейсы…"
        />
      </label>
      {err ? <p className="xf-error">{err}</p> : null}
      <button type="submit" className="xf-btn" disabled={busy}>
        {busy ? "Отправка…" : "Отправить запрос"}
      </button>
      <p className="xf-consent">
        Отправляя данные, вы соглашаетесь с{" "}
        <a href="https://antrasha.ru/privacy" target="_blank" rel="noopener noreferrer">
          политикой конфиденциальности
        </a>
        .
      </p>
    </form>
  );
}
