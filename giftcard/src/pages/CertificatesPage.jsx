import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getDisplayName, listCertificates } from "../api.js";
import CertificateFormModal from "../components/CertificateFormModal.jsx";
import ChargeModal from "../components/ChargeModal.jsx";
import TelegramModal from "../components/TelegramModal.jsx";

function formatDateRu(value) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function expirationText(cert) {
  if (cert.indefinite) return "бессрочно";
  if (!cert.created_at || !cert.period) return "—";
  const date = new Date(cert.created_at);
  date.setDate(date.getDate() + cert.period);
  return `до ${formatDateRu(date)}`;
}

export default function CertificatesPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [onlyActive, setOnlyActive] = useState(true);
  const [creating, setCreating] = useState(false);
  const [chargeCert, setChargeCert] = useState(null);
  const [telegramCert, setTelegramCert] = useState(null);

  async function reload() {
    setLoading(true);
    setError("");
    try {
      setRows(await listCertificates());
    } catch (err) {
      setError(err.message || "Не удалось загрузить сертификаты");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return rows.filter((cert) => {
      if (onlyActive && cert.status !== "ACTIVE") return false;
      if (!needle) return true;
      return [cert.code, cert.phone, cert.name, cert.last_name, cert.employee, cert.description]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle));
    });
  }, [rows, query, onlyActive]);

  return (
    <>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Поиск по коду, телефону, имени"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <label className="check-inline">
          <input
            type="checkbox"
            checked={onlyActive}
            onChange={(event) => setOnlyActive(event.target.checked)}
          />
          Только действующие
        </label>
        <button type="button" onClick={() => setCreating(true)}>
          Создать сертификат
        </button>
      </div>

      {loading ? <p className="empty">Загрузка…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {!loading && !error ? (
        <div className="table-wrap">
          <table className="certs">
            <thead>
              <tr>
                <th>Код</th>
                <th>Номинал</th>
                <th>Остаток</th>
                <th>Описание</th>
                <th>Телефон</th>
                <th>Сотрудник</th>
                <th>Выдан</th>
                <th>Срок</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={10}>Нет сертификатов</td>
                </tr>
              ) : (
                visible.map((cert) => (
                  <tr key={cert.id}>
                    <td>
                      <Link to={`/certificates/${cert.id}`} target="_blank" rel="noreferrer">
                        {cert.code}
                      </Link>
                    </td>
                    <td>{cert.nominal}</td>
                    <td>{cert.amount}</td>
                    <td>{cert.description || "—"}</td>
                    <td>{cert.phone}</td>
                    <td>{cert.employee || "—"}</td>
                    <td>{formatDateRu(cert.created_at)}</td>
                    <td>{expirationText(cert)}</td>
                    <td className={`status-${cert.status}`}>{cert.status}</td>
                    <td>
                      <button type="button" className="secondary icon-btn" onClick={() => setTelegramCert(cert)}>
                        Telegram
                      </button>{" "}
                      <button
                        type="button"
                        className="icon-btn"
                        disabled={cert.status !== "ACTIVE"}
                        onClick={() => setChargeCert(cert)}
                      >
                        Списать
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {creating ? (
        <CertificateFormModal
          employeeDefault={getDisplayName()}
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            reload();
          }}
        />
      ) : null}
      {chargeCert ? (
        <ChargeModal
          certificate={chargeCert}
          onClose={() => setChargeCert(null)}
          onDone={() => {
            setChargeCert(null);
            reload();
          }}
        />
      ) : null}
      {telegramCert ? (
        <TelegramModal certificate={telegramCert} onClose={() => setTelegramCert(null)} />
      ) : null}
    </>
  );
}
