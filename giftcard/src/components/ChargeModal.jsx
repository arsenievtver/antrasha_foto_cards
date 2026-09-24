import { useState } from "react";
import { chargeCertificate, sendConfirmCode } from "../api.js";

export default function ChargeModal({ certificate, onClose, onDone }) {
  const [sum, setSum] = useState(String(certificate.amount));
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState("");
  const [step, setStep] = useState("idle");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function sendSms() {
    setError("");
    const amount = Number(sum);
    if (!amount || amount <= 0 || amount > certificate.amount) {
      setError(`Введите сумму от 1 до ${certificate.amount}`);
      return;
    }
    setLoading(true);
    try {
      const data = await sendConfirmCode(certificate.id, amount);
      setDevCode(data.dev_confirm_code || "");
      setStep("sent");
    } catch (err) {
      setError(err.message || "Не удалось отправить SMS");
    } finally {
      setLoading(false);
    }
  }

  async function confirm() {
    if (!code.trim()) return;
    setLoading(true);
    setError("");
    try {
      await chargeCertificate(certificate.id, code.trim());
      setStep("done");
    } catch (err) {
      setError(err.message || "Неверный код");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div className="modal-sheet" onMouseDown={(event) => event.stopPropagation()}>
        <h2>Списать {certificate.code}</h2>
        {step === "done" ? (
          <>
            <p>Списание проведено.</p>
            <div className="modal-actions">
              <button type="button" onClick={onDone}>
                Закрыть
              </button>
            </div>
          </>
        ) : (
          <div className="form-stack">
            <label>
              Сумма списания
              <input
                type="number"
                min="1"
                max={certificate.amount}
                value={sum}
                disabled={step !== "idle"}
                onChange={(event) => setSum(event.target.value)}
              />
              <span className="field-hint">Максимум: {certificate.amount}</span>
            </label>
            {step === "sent" ? (
              <label>
                Код из SMS
                <input value={code} onChange={(event) => setCode(event.target.value)} inputMode="numeric" />
                {devCode ? <span className="field-hint">Локально SMS не уходит. Код: {devCode}</span> : null}
              </label>
            ) : null}
            {error ? <p className="error">{error}</p> : null}
            <div className="modal-actions">
              <button type="button" className="secondary" onClick={onClose}>
                Отмена
              </button>
              {step === "idle" ? (
                <button type="button" disabled={loading} onClick={sendSms}>
                  {loading ? "Отправка…" : "Отправить SMS"}
                </button>
              ) : (
                <button type="button" disabled={loading} onClick={confirm}>
                  {loading ? "Проверка…" : "Списать"}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
