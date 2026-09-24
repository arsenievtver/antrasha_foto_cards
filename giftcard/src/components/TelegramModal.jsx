import { useState } from "react";
import { sendTelegram } from "../api.js";

export default function TelegramModal({ certificate, onClose }) {
  const [chatId, setChatId] = useState("");
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await sendTelegram(certificate.id, chatId);
      setDone(true);
    } catch (err) {
      setError(err.message || "Не удалось отправить");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal-sheet" onMouseDown={(event) => event.stopPropagation()}>
        <h2>Telegram · {certificate.code}</h2>
        {done ? (
          <>
            <p>Сообщение отправлено.</p>
            <div className="modal-actions">
              <button type="button" onClick={onClose}>
                Закрыть
              </button>
            </div>
          </>
        ) : (
          <form className="form-stack" onSubmit={onSubmit}>
            <label>
              Telegram ID
              <input
                inputMode="numeric"
                required
                value={chatId}
                onChange={(event) => setChatId(event.target.value.replace(/\D/g, ""))}
              />
            </label>
            {error ? <p className="error">{error}</p> : null}
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={onClose}>
                Отмена
              </button>
              <button type="submit" disabled={loading}>
                {loading ? "Отправка…" : "Отправить"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
