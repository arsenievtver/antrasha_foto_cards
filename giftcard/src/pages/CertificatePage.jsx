import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchPublicCertificate } from "../api.js";
import CertificateCard from "./CertificateCard.jsx";
import "./certificate.styles.css";

export default function CertificatePage() {
  const { id } = useParams();
  const [certificate, setCertificate] = useState(null);
  const [stage, setStage] = useState("loading");
  const [offsetY, setOffsetY] = useState(30);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchPublicCertificate(id)
      .then((data) => {
        if (cancelled) return;
        setCertificate(data);
        setTimeout(() => {
          setOffsetY(0);
          setStage("shown");
        }, 50);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

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
          <div
            className={certificate ? "certificate-card-wrapper show" : "certificate-card-wrapper"}
            style={{
              transform: `translateX(-50%) translateY(${offsetY}px)`,
              transition: "transform 0.6s cubic-bezier(0.22, 1, 0.36, 1)",
            }}
          >
            {certificate ? <CertificateCard certificate={certificate} /> : null}
          </div>
          <img src="/images/envelope-front.png" alt="" className="envelope-front" />
        </div>
        <div className="certificate-footer">
          {!certificate && !failed ? <div className="certificate-loading">Подождите, загружаем сертификат…</div> : null}
          {failed ? <div className="certificate-loading">Сертификат не найден</div> : null}
          {stage === "shown" ? <div className="certificate-status-hint">{statusHint}</div> : null}
          <a
            href="https://antrasha.ru/giftcards"
            target="_blank"
            rel="noopener noreferrer"
            className="certificate-rules-link"
          >
            Правила использования сертификата
          </a>
          <a href="https://t.me/AntrashaBot" target="_blank" rel="noopener noreferrer" className="certificate-telegram-link">
            <img src="/telegram.svg" alt="Telegram" className="telegram-icon" />
          </a>
        </div>
      </div>
    </div>
  );
}
