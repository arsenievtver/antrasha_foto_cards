import { useCallback, useEffect, useState } from "react";
import {
  createRankingEvalBenchmark,
  embedRankingEvalBenchmark,
  fetchRankingEvalBenchmark,
  fetchRankingEvalBenchmarks,
  fetchRankingEvalSubmission,
  fetchRankingEvalSubmissions,
  getRole,
  patchRankingEvalBenchmark,
  uploadRankingEvalPhotos,
  deleteRankingEvalPhoto,
} from "../api.js";

function fmtTau(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v).toFixed(2);
}

export default function RankingEvalAdmin() {
  const [tab, setTab] = useState("benchmarks");
  const [list, setList] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [submissions, setSubmissions] = useState([]);
  const [submissionDetail, setSubmissionDetail] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [newName, setNewName] = useState("");
  const [newGender, setNewGender] = useState("female");

  const loadList = useCallback(async () => {
    setErr("");
    const rows = await fetchRankingEvalBenchmarks();
    setList(rows || []);
  }, []);

  const loadDetail = useCallback(async (id) => {
    if (!id) return;
    setErr("");
    const d = await fetchRankingEvalBenchmark(id);
    setDetail(d);
  }, []);

  const loadSubmissions = useCallback(async () => {
    setErr("");
    const rows = await fetchRankingEvalSubmissions(selectedId || undefined);
    setSubmissions(rows || []);
  }, [selectedId]);

  useEffect(() => {
    loadList().catch((e) => setErr(e.message));
  }, [loadList]);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId).catch((e) => setErr(e.message));
    else setDetail(null);
  }, [selectedId, loadDetail]);

  useEffect(() => {
    if (tab === "results") loadSubmissions().catch((e) => setErr(e.message));
  }, [tab, loadSubmissions]);

  async function onCreate(e) {
    e.preventDefault();
    if (getRole() !== "superuser" || busy) return;
    setBusy(true);
    setErr("");
    try {
      const d = await createRankingEvalBenchmark({
        name: newName.trim() || "Набор",
        gender: newGender,
      });
      setNewName("");
      await loadList();
      setSelectedId(d.id);
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function onUpload(e) {
    const files = e.target.files;
    if (!files?.length || !selectedId || getRole() !== "superuser") return;
    setBusy(true);
    setErr("");
    try {
      const d = await uploadRankingEvalPhotos(selectedId, files);
      setDetail(d);
      await loadList();
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  async function onEmbedLoop() {
    if (!selectedId || busy) return;
    setBusy(true);
    setErr("");
    try {
      for (;;) {
        const batch = await embedRankingEvalBenchmark(selectedId, 4);
        await loadDetail(selectedId);
        await loadList();
        if (!batch.processed) break;
      }
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive() {
    if (!detail || getRole() !== "superuser" || busy) return;
    setBusy(true);
    setErr("");
    try {
      const d = await patchRankingEvalBenchmark(detail.id, {
        is_active: !detail.is_active,
      });
      setDetail(d);
      await loadList();
    } catch (ex) {
      setErr(ex.message || String(ex));
    } finally {
      setBusy(false);
    }
  }

  async function openSubmission(id) {
    setErr("");
    try {
      const d = await fetchRankingEvalSubmission(id);
      setSubmissionDetail(d);
    } catch (ex) {
      setErr(ex.message || String(ex));
    }
  }

  const byPhoto = submissionDetail
    ? Object.fromEntries((submissionDetail.photos || []).map((p) => [p.photo_id, p]))
    : {};

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Оценка ранжирования</h2>
      <p style={{ color: "var(--muted)", fontSize: "0.92rem" }}>
        Эталонные наборы (до 10 фото), векторизация, сравнение с порядком участников.
      </p>
      {err ? <p className="error">{err}</p> : null}

      <div className="toolbar" style={{ marginBottom: "1rem" }}>
        <button type="button" className={tab === "benchmarks" ? "" : "secondary"} onClick={() => setTab("benchmarks")}>
          Наборы
        </button>
        <button type="button" className={tab === "results" ? "" : "secondary"} onClick={() => setTab("results")}>
          Результаты
        </button>
      </div>

      {tab === "benchmarks" ? (
        <div style={{ display: "grid", gridTemplateColumns: "minmax(200px, 280px) 1fr", gap: "1rem" }}>
          <div className="card">
            <h3 style={{ marginTop: 0 }}>Наборы</h3>
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {list.map((b) => (
                <li key={b.id} style={{ marginBottom: 6 }}>
                  <button
                    type="button"
                    className={selectedId === b.id ? "" : "secondary"}
                    style={{ width: "100%", textAlign: "left" }}
                    onClick={() => setSelectedId(b.id)}
                  >
                    {b.name} ({b.gender}) {b.is_active ? "· активен" : ""}
                    <br />
                    <small>
                      {b.embedded_count}/{b.photo_count} embed
                    </small>
                  </button>
                </li>
              ))}
            </ul>
            {getRole() === "superuser" ? (
              <form onSubmit={onCreate} style={{ marginTop: "1rem" }}>
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="Название"
                  maxLength={120}
                />
                <select value={newGender} onChange={(e) => setNewGender(e.target.value)} style={{ marginTop: 6 }}>
                  <option value="female">female</option>
                  <option value="male">male</option>
                </select>
                <button type="submit" disabled={busy} style={{ marginTop: 8 }}>
                  Создать
                </button>
              </form>
            ) : null}
          </div>

          <div className="card">
            {!detail ? (
              <p style={{ color: "var(--muted)" }}>Выберите или создайте набор.</p>
            ) : (
              <>
                <h3 style={{ marginTop: 0 }}>{detail.name}</h3>
                <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>
                  {detail.gender} · {detail.embedded_count}/{detail.photo_count} с embedding
                </p>
                {getRole() === "superuser" ? (
                  <div className="toolbar" style={{ flexWrap: "wrap", marginBottom: "0.75rem" }}>
                    <label className="secondary" style={{ cursor: "pointer" }}>
                      Загрузить фото
                      <input type="file" accept="image/*" multiple hidden onChange={onUpload} disabled={busy} />
                    </label>
                    <button type="button" disabled={busy} onClick={onEmbedLoop}>
                      Векторизовать
                    </button>
                    <button type="button" disabled={busy} onClick={toggleActive}>
                      {detail.is_active ? "Снять активность" : "Сделать активным"}
                    </button>
                  </div>
                ) : null}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))",
                    gap: "0.5rem",
                  }}
                >
                  {(detail.photos || []).map((p) => (
                    <figure key={p.photo_id} style={{ margin: 0 }}>
                      <img
                        src={p.url}
                        alt=""
                        style={{ width: "100%", aspectRatio: "3/4", objectFit: "cover", borderRadius: 6 }}
                      />
                      <figcaption style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                        {p.has_embedding ? "✓ embed" : "⏳"}
                        {getRole() === "superuser" ? (
                          <button
                            type="button"
                            className="secondary"
                            style={{ marginLeft: 4, padding: "0 4px" }}
                            onClick={() =>
                              deleteRankingEvalPhoto(detail.id, p.photo_id)
                                .then(() => loadDetail(detail.id))
                                .then(() => loadList())
                                .catch((e) => setErr(e.message))
                            }
                          >
                            ×
                          </button>
                        ) : null}
                      </figcaption>
                    </figure>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>Дата</th>
                <th>Участник</th>
                <th>Набор</th>
                <th>τ</th>
                <th>ρ</th>
                <th>top-3</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => (
                <tr key={s.id}>
                  <td>{new Date(s.created_at).toLocaleString("ru-RU")}</td>
                  <td>{s.user_label}</td>
                  <td>
                    {s.benchmark_name} ({s.gender})
                  </td>
                  <td>{fmtTau(s.kendall_tau)}</td>
                  <td>{fmtTau(s.spearman_rho)}</td>
                  <td>{s.top3_overlap ?? "—"}</td>
                  <td>
                    <button type="button" className="secondary" onClick={() => openSubmission(s.id)}>
                      Сравнить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {submissionDetail ? (
            <div style={{ marginTop: "1.25rem" }}>
              <h3>Сравнение: {submissionDetail.user_label}</h3>
              <p style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
                τ={fmtTau(submissionDetail.kendall_tau)} · ρ={fmtTau(submissionDetail.spearman_rho)} · top3=
                {submissionDetail.top3_overlap ?? "—"}
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                <div>
                  <strong>Человек</strong>
                  <ol>
                    {submissionDetail.human_order.map((pid) => (
                      <li key={`h-${pid}`}>
                        {byPhoto[pid] ? (
                          <img src={byPhoto[pid].url} alt="" style={{ width: 56, verticalAlign: "middle" }} />
                        ) : (
                          pid
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
                <div>
                  <strong>Модель</strong>
                  <ol>
                    {submissionDetail.model_order.map((pid) => (
                      <li key={`m-${pid}`}>
                        {byPhoto[pid] ? (
                          <img src={byPhoto[pid].url} alt="" style={{ width: 56, verticalAlign: "middle" }} />
                        ) : (
                          pid
                        )}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>
              <button type="button" className="secondary" onClick={() => setSubmissionDetail(null)}>
                Закрыть
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
