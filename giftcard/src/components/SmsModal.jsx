import { useEffect, useState } from "react";
import { previewShareSms, sendShareSms } from "../api.js";

const ROLE_LABEL = {
  owner: "Владельцу",
  giver: "Дарителю",
};

export default function SmsModal({ certificate, onClose }) {
  const [messages, setMessages] = useState(null);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    previewShareSms(certificate.id)
      .then((data) => {
        if (!cancelled) setMessages(data.messages || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Не удалось подготовить SMS");
      });
    return () => {
      cancelled = true;
    };
  }, [certificate.id]);

  async function onSend() {
    setError("");
    setLoading(true);
    try {
      const data = await sendShareSms(certificate.id);
      setResult(data.messages || []);
    } catch (err) {
      setError(err.message || "Не удалось отправить");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal-sheet" onMouseDown={(event) => event.stopPropagation()}>
        <h2>СМС · {certificate.code}</h2>
        {result ? (
          <>
            {result.map((item) => (
              <p key={`${item.role}-${item.phone}`}>
                {ROLE_LABEL[item.role] || item.role} {item.phone}: {item.sent ? "отправлено" : item.error || "не отправлено"}
              </p>
            ))}
            <div className="modal-actions">
              <button type="button" onClick={onClose}>
                Закрыть
              </button>
            </div>
          </>
        ) : (
          <>
            {!messages && !error ? <p>Готовим тексты…</p> : null}
            {messages?.map((item) => (
              <p key={`${item.role}-${item.phone}`}>
                <strong>
                  {ROLE_LABEL[item.role] || item.role} {item.phone}
                </strong>
                <br />
                {item.text}
              </p>
            ))}
            {error ? <p className="error">{error}</p> : null}
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={onClose}>
                Отмена
              </button>
              <button type="button" disabled={loading || !messages?.length} onClick={onSend}>
                {loading ? "Отправка…" : "Отправить"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
