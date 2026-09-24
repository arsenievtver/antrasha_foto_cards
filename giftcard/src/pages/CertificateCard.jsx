export default function CertificateCard({ certificate }) {
  const { amount, phone, code, status, indefinite, created_at: createdAt, period } = certificate;
  const statusIcon = status === "ACTIVE" ? "" : "❌";

  let validUntil = "бессрочно";
  if (!indefinite && createdAt && period) {
    const date = new Date(createdAt);
    date.setDate(date.getDate() + period);
    validUntil = date.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  }

  return (
    <div className="certificate-card">
      <h2>Сертификат {code}</h2>
      <p style={{ fontSize: "16px", margin: "8px 0" }}>
        На сумму <strong>{amount}</strong> ₽
      </p>
      <p>Владелец: {phone}</p>
      <p>Действителен до: {validUntil}</p>
      <div className="certificate-status-icon">{statusIcon}</div>
    </div>
  );
}
