import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getDisplayName, listCertificates } from "../api.js";
import CertificateFormModal from "../components/CertificateFormModal.jsx";
import Switch from "../components/Switch.jsx";
import ChargeModal from "../components/ChargeModal.jsx";
import SmsModal from "../components/SmsModal.jsx";

function formatShortDate(value) {
  if (!value) return "—";
  const [year, month, day] = String(value).slice(0, 10).split("-");
  if (!year || !month || !day) return "—";
  return `${day}.${month}.${year.slice(-2)}`;
}

function expirationText(cert) {
  if (cert.indefinite) return "бессрочно";
  if (!cert.created_at || !cert.period) return "—";
  const [year, month, day] = String(cert.created_at).slice(0, 10).split("-").map(Number);
  const date = new Date(year, month - 1, day);
  date.setDate(date.getDate() + cert.period);
  const dd = String(date.getDate()).padStart(2, "0");
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const yy = String(date.getFullYear()).slice(-2);
  return `до ${dd}.${mm}.${yy}`;
}

function formatMoney(value) {
  if (value === null || value === undefined || value === "") return "—";
  return Number(value).toLocaleString("ru-RU");
}

export default function CertificatesPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [onlyActive, setOnlyActive] = useState(true);
  const [creating, setCreating] = useState(false);
  const [chargeCert, setChargeCert] = useState(null);
  const [smsCert, setSmsCert] = useState(null);

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
      return [cert.code, cert.phone, cert.name, cert.last_name, cert.giver_name, cert.giver_phone, cert.employee, cert.description]
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
        <Switch
          label="Только действующие"
          checked={onlyActive}
          onChange={setOnlyActive}
        />
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
                <th>Сумма</th>
                <th>Описание</th>
                <th>Телефон</th>
                <th>Даритель</th>
                <th>Сотрудник</th>
                <th>Даты</th>
                <th>Статус</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={9}>Нет сертификатов</td>
                </tr>
              ) : (
                visible.map((cert) => (
                  <tr key={cert.id}>
                    <td className="nowrap">
                      <Link to={`/c/${cert.public_slug}`} target="_blank" rel="noreferrer">
                        {cert.code}
                      </Link>
                    </td>
                    <td className="cell-stack">
                      <span>{formatMoney(cert.nominal)} ₽</span>
                      <span className="cell-sub">остаток {formatMoney(cert.amount)} ₽</span>
                    </td>
                    <td className="cell-desc">{cert.description || "—"}</td>
                    <td className="nowrap">{cert.phone}</td>
                    <td className="cell-stack">
                      {cert.giver_name || cert.giver_phone ? (
                        <>
                          <span>{cert.giver_name || "—"}</span>
                          {cert.giver_phone ? <span className="cell-sub">{cert.giver_phone}</span> : null}
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="nowrap">{cert.employee || "—"}</td>
                    <td className="cell-stack">
                      <span>{formatShortDate(cert.created_at)}</span>
                      <span className="cell-sub">{expirationText(cert)}</span>
                    </td>
                    <td className={`nowrap status-${cert.status}`}>{cert.status}</td>
                    <td>
                      <div className="row-actions">
                        <button type="button" className="secondary icon-btn" onClick={() => setSmsCert(cert)}>
                          СМС
                        </button>
                        <button
                          type="button"
                          className="icon-btn"
                          disabled={cert.status !== "ACTIVE"}
                          onClick={() => setChargeCert(cert)}
                        >
                          Списать
                        </button>
                      </div>
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
      {smsCert ? <SmsModal certificate={smsCert} onClose={() => setSmsCert(null)} /> : null}
    </>
  );
}
