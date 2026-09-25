import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchPublicCertificate } from "../api.js";
import CertificateCard from "./CertificateCard.jsx";
import "./certificate.styles.css";

export default function CertificatePage() {
  const { id, code } = useParams();
  const ref = id || code;
  const backPath = id ? `/certificates/${encodeURIComponent(id)}` : `/c/${encodeURIComponent(code || "")}`;
  const [certificate, setCertificate] = useState(null);
  const [stage, setStage] = useState("loading");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchPublicCertificate(ref)
      .then((data) => {
        if (cancelled) return;
        setCertificate(data);
        setTimeout(() => setStage("shown"), 700);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ref]);

  let statusHint = "Статус: ";
  if (certificate?.status === "ACTIVE") statusHint = "*Статус: Действует";
  if (certificate?.status === "USED") statusHint = "*Статус: Использован";
  if (certificate?.status === "EXPIRED") statusHint = "*Статус: Истёк";
  if (certificate?.status === "CANCELLED") statusHint = "*Статус: Отменён";

  return (
    <div className="certificate-page">
      <div className="certificate-wrapper">
        <div className="certificate-scene">
          <img src="/images/envelope-back.png" alt="" className="envelope-back" />
          <div className={certificate ? "certificate-card-wrapper show" : "certificate-card-wrapper"}>
            {certificate ? <CertificateCard certificate={certificate} /> : null}
          </div>
          <img src="/images/envelope-front.png" alt="" className="envelope-front" />
        </div>
        <div className="certificate-footer">
          {!certificate && !failed ? <div className="certificate-loading">Подождите, загружаем сертификат…</div> : null}
          {failed ? <div className="certificate-loading">Сертификат не найден</div> : null}
          {stage === "shown" ? <div className="certificate-status-hint">{statusHint}</div> : null}
          <Link to={`/rules?from=${encodeURIComponent(backPath)}`} className="certificate-rules-link">
            Правила использования сертификата
          </Link>
          <a href="https://antrasha.ru" target="_blank" rel="noopener noreferrer" className="certificate-site-link">
            <img src="/favicon.svg" alt="ANTRASHA" className="certificate-site-icon" />
          </a>
        </div>
      </div>
    </div>
  );
}
