export default function CertificateCard({ certificate }) {
  const { amount, phone, code, status, indefinite, created_at: createdAt, period } = certificate;
  const statusIcon = status === "ACTIVE" ? "" : "❌";

  let validUntil = "бессрочно";
  if (!indefinite && createdAt && period) {
    const date = new Date(createdAt);
    date.setDate(date.getDate() + period);
    const dd = String(date.getDate()).padStart(2, "0");
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const yy = String(date.getFullYear()).slice(-2);
    validUntil = `${dd}.${mm}.${yy}`;
  }

  return (
    <div className="certificate-card">
      <h2>Сертификат {code}</h2>
      <p className="certificate-amount">
        На сумму <strong>{amount}</strong> ₽
      </p>
      <p>Владелец: {phone}</p>
      <p>Действителен до: {validUntil}</p>
      <div className="certificate-status-icon">{statusIcon}</div>
    </div>
  );
}
