import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  addAClientCaretaker,
  dismissAClientCaretaker,
  fetchAClient,
  fetchAClients,
  fetchStaffFeedbackStats,
  syncAClients,
} from "../api.js";
import AClientsActive from "./AClientsActive.jsx";

const STATUSES = ["просрочил визит", "покупает меньше", "ушёл (>12 мес)"];

function rub(value) {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value).toLocaleString("ru-RU")} ₽`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch {
    return String(iso).slice(0, 10);
  }
}

function fmtWhen(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return String(iso);
  }
}

function delta(from, to) {
  if (from == null || to == null) return null;
  return to - from;
}

function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return /[;"\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function staffNames(row) {
  return (row.caretakers || []).map((person) => person.author_label).filter(Boolean);
}

function sumOf(rows, key) {
  return rows.reduce((acc, row) => acc + (Number(row[key]) || 0), 0);
}

function downloadClients(rows) {
  const head = [
    "Клиент",
    "Телефон",
    "Статус",
    "На контроле",
    "Недель в списке",
    "Последняя покупка",
    "Дней назад",
    "Обычный интервал, дн",
    "Выручка прошлые 12 мес",
    "Выручка последние 12 мес",
    "Покупок за 24 мес",
    "Бренды",
    "Категории",
    "Размеры",
    "Средняя скидка %",
    "Доля уценки %",
    "Сотрудники",
    "Комментариев",
    "Последний комментарий",
    "Автор комментария",
    "Подборка",
  ];
  const body = rows.map((row) => [
    row.name,
    row.phone,
    row.status,
    row.active ? "да" : "снят",
    row.weeks_on_list,
    row.last_visit,
    row.days_since,
    row.median_gap,
    row.rev_prev12,
    row.rev_cur12,
    row.visits,
    (row.brands || []).join(", "),
    (row.categories || []).join(", "),
    row.sizes,
    row.avg_discount_pct,
    row.markdown_share_pct,
    staffNames(row).join(", "),
    row.comment_count,
    row.last_comment_text,
    row.last_comment_author,
    (row.picks || []).map((pick) => `${pick.name} — ${pick.price} ₽${pick.old ? " (старый)" : ""}`).join(" | "),
  ]);
  const text = `\uFEFF${[head, ...body].map((line) => line.map(csvCell).join(";")).join("\n")}`;
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `a-clients-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const SLICES = [
  { id: "all", label: "Всего" },
  { id: "with", label: "С сотрудником" },
  { id: "without", label: "Без сотрудника" },
  { id: "comment", label: "С комментарием" },
  { id: "no-comment", label: "Без комментария" },
  ...STATUSES.map((name) => ({ id: `status:${name}`, label: name })),
];

function inSlice(row, slice) {
  if (slice === "with") return staffNames(row).length > 0;
  if (slice === "without") return staffNames(row).length === 0;
  if (slice === "comment") return row.comment_count > 0;
  if (slice === "no-comment") return !row.comment_count;
  if (slice.startsWith("status:")) return row.status === slice.slice(7);
  return true;
}

export default function AClients() {
  const [q, setQ] = useState("");
  const [caretaker, setCaretaker] = useState("");
  const [slice, setSlice] = useState("all");
  const [showLeft, setShowLeft] = useState(false);
  const [items, setItems] = useState([]);
  const [staff, setStaff] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [err, setErr] = useState("");
  const [note, setNote] = useState("");
  const [tab, setTab] = useState("watch");

  const load = useCallback(async () => {
    setLoading(true);
    setErr("");
    try {
      const [list, stats] = await Promise.all([
        fetchAClients({ active: showLeft ? "" : true }),
        fetchStaffFeedbackStats({}),
      ]);
      setItems(list.items || []);
      setStaff(stats.items || []);
      setSelectedId((prev) => (prev && (list.items || []).some((row) => row.id === prev) ? prev : ""));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, [showLeft]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    fetchAClient(selectedId)
      .then((row) => {
        if (!cancelled) setDetail(row);
      })
      .catch((e) => {
        if (!cancelled) setErr(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const caretakerOptions = useMemo(() => {
    const names = new Map();
    for (const person of staff) {
      if (person.author_user_id) names.set(person.author_user_id, person.author_label);
    }
    for (const row of items) {
      for (const person of row.caretakers || []) {
        names.set(person.author_user_id || person.author_label, person.author_label);
      }
    }
    return [...names.entries()].map(([id, label]) => ({ id, label }));
  }, [staff, items]);

  const searched = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return items.filter((row) => {
      if (needle && !row.name.toLowerCase().includes(needle) && !(row.phone || "").includes(needle)) return false;
      if (caretaker) {
        const keys = (row.caretakers || []).flatMap((person) =>
          [person.author_user_id, person.author_label].filter(Boolean),
        );
        if (!keys.includes(caretaker)) return false;
      }
      return true;
    });
  }, [items, q, caretaker]);

  const visible = useMemo(
    () => searched.filter((row) => inSlice(row, slice)),
    [searched, slice],
  );

  const summaryRows = useMemo(
    () =>
      SLICES.map((item) => {
        const rows = searched.filter((row) => inSlice(row, item.id));
        return {
          ...item,
          count: rows.length,
          prev: sumOf(rows, "rev_prev12"),
          cur: sumOf(rows, "rev_cur12"),
        };
      }),
    [searched],
  );

  async function onSync() {
    setSyncing(true);
    setErr("");
    setNote("");
    try {
      const stats = await syncAClients();
      setNote(
        `Недель: ${stats.reports}. На контроле: ${stats.active}. Комментарии привязаны: ${stats.linked_messages}, склеены: ${stats.merged_messages}.`,
      );
      await load();
      if (selectedId) setDetail(await fetchAClient(selectedId));
    } catch (e) {
      setErr(e.message);
    } finally {
      setSyncing(false);
    }
  }

  async function reloadDetail() {
    if (!selectedId) return;
    const row = await fetchAClient(selectedId);
    setDetail(row);
    await load();
  }

  async function onAddCaretaker(authorUserId) {
    const person = staff.find((row) => row.author_user_id === authorUserId);
    if (!person || !detail) return;
    setErr("");
    try {
      await addAClientCaretaker(detail.id, {
        author_user_id: person.author_user_id,
        author_label: person.author_label,
      });
      await reloadDetail();
    } catch (e) {
      setErr(e.message);
    }
  }

  async function onDismiss(caretakerId) {
    if (!detail) return;
    setErr("");
    try {
      await dismissAClientCaretaker(detail.id, caretakerId);
      await reloadDetail();
    } catch (e) {
      setErr(e.message);
    }
  }

  const progress = detail?.progress;

  return (
    <section>
      <h2 style={{ marginTop: 0, marginBottom: "0.35rem" }}>Клиенты А</h2>
      <div className="flex-gap" style={{ gap: "0.4rem", marginBottom: "0.75rem" }}>
        <button type="button" className={tab === "watch" ? "" : "secondary"} onClick={() => setTab("watch")}>
          На контроле
        </button>
        <button type="button" className={tab === "active" ? "" : "secondary"} onClick={() => setTab("active")}>
          Действующие
        </button>
      </div>
      {tab === "active" ? (
        <AClientsActive />
      ) : (
        <>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "0.85rem", maxWidth: 760 }}>
        Кто из категории А сейчас на контроле, кто из продавцов с ним на связи и что написано в{" "}
        <Link to="/staff-feedback">«Спросе»</Link>. Список берётся из <Link to="/weekly-insight">недель</Link>.
        У одного клиента может быть несколько сотрудников — по тому, кто сам о нём написал.
      </p>

      <div className="flex-gap" style={{ flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Имя или телефон"
          style={{ minWidth: 180 }}
        />
        <select value={caretaker} onChange={(e) => setCaretaker(e.target.value)}>
          <option value="">Все сотрудники</option>
          {caretakerOptions.map((person) => (
            <option key={person.id} value={person.id}>
              {person.label}
            </option>
          ))}
        </select>
        <label>
          <input type="checkbox" checked={showLeft} onChange={(e) => setShowLeft(e.target.checked)} /> снятые с контроля
        </label>
        <button type="button" className="secondary" disabled={!visible.length} onClick={() => downloadClients(visible)}>
          Скачать CSV
        </button>
        <button type="button" onClick={onSync} disabled={syncing}>
          {syncing ? "Собираем…" : "Обновить из недель"}
        </button>
      </div>
      {note ? <p style={{ color: "var(--muted)" }}>{note}</p> : null}
      {err ? <p className="error">{err}</p> : null}

      {items.length ? (
        <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
          <h3 style={{ marginBottom: "0.4rem" }}>Сводка</h3>
          <table>
            <thead>
              <tr>
                <th>Срез</th>
                <th>Клиентов</th>
                <th>Прошлые 12 мес</th>
                <th>Последние 12 мес</th>
              </tr>
            </thead>
            <tbody>
              {summaryRows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => setSlice((prev) => (prev === row.id ? "all" : row.id))}
                  style={{
                    cursor: "pointer",
                    background: slice === row.id ? "var(--row-active, rgba(0,0,0,0.06))" : undefined,
                  }}
                >
                  <td>{row.label}</td>
                  <td>{row.count}</td>
                  <td>{rub(row.prev)}</td>
                  <td>{rub(row.cur)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ color: "var(--muted)", marginTop: 0 }}>
            В выборке {visible.length}
            {visible.length !== searched.length ? ` из ${searched.length}` : ""}: последние 12 мес{" "}
            {rub(sumOf(visible, "rev_cur12"))}, прошлые {rub(sumOf(visible, "rev_prev12"))}.
          </p>
        </div>
      ) : null}

      {!visible.length ? (
        <p style={{ color: "var(--muted)" }}>
          {loading
            ? "Загрузка…"
            : items.length
              ? "По этому фильтру никого нет."
              : "Список ещё не собран. Нажмите «Обновить из недель»: возьмём клиентов из готовых отчётов и разберём комментарии."}
        </p>
      ) : (
        <>
        <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Клиент</th>
                  <th>Статус</th>
                  <th>12 мес</th>
                  <th>Сотрудники</th>
                  <th>Комментарий</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => (
                  <tr
                    key={row.id}
                    onClick={() => setSelectedId(row.id)}
                    style={{ cursor: "pointer", background: row.id === selectedId ? "var(--row-active, rgba(0,0,0,0.04))" : undefined }}
                  >
                    <td>
                      <div>{row.name}</div>
                      <div style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                        {row.phone || "—"}
                        {row.active ? "" : " · снят"}
                        {row.weeks_on_list ? ` · ${row.weeks_on_list} нед.` : ""}
                      </div>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {row.status || "—"}
                      <div style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                        {row.days_since != null ? `${row.days_since} дн` : ""}
                      </div>
                    </td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      {rub(row.rev_cur12)}
                      <div style={{ color: "var(--muted)", fontSize: "0.85rem" }}>было {rub(row.rev_prev12)}</div>
                    </td>
                    <td>{staffNames(row).join(", ") || "—"}</td>
                    <td>
                      {row.last_comment_text ? (
                        <>
                          <div style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
                            {row.last_comment_author} · {fmtDate(row.last_comment_at)}
                          </div>
                          {row.last_comment_text}
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
        </div>

        {selectedId ? (
          <div className="modal-backdrop" role="presentation" onClick={() => setSelectedId("")}>
            <div className="modal" role="dialog" onClick={(e) => e.stopPropagation()}>
          {detail && detail.id === selectedId ? (
            <>
              <h3 style={{ marginTop: 0 }}>{detail.name}</h3>
              <p style={{ marginTop: 0 }}>
                {detail.phone || "телефона нет"}
                {" · "}
                {detail.active ? detail.status : "снят с контроля"}
                {detail.days_since != null ? ` · ${detail.days_since} дн без визита` : ""}
              </p>
              <p>
                Прошлые 12 мес {rub(detail.rev_prev12)}, последние {rub(detail.rev_cur12)}. Визитов {detail.visits ?? "—"}.
              </p>
              {progress ? (
                <p>
                  В списке {progress.weeks_on_list}{" "}
                  {progress.weeks_on_list === 1 ? "неделя" : "нед."}
                  {progress.first_week ? ` с ${progress.first_week}` : ""}.
                  {progress.on_list_now
                    ? " Сейчас на контроле."
                    : " В последней неделе его уже нет — вышел из контроля."}
                  {delta(progress.rev_cur12_first, progress.rev_cur12_last) != null && progress.weeks_on_list > 1
                    ? ` Выручка 12 мес с первой недели списка: ${rub(progress.rev_cur12_first)} → ${rub(progress.rev_cur12_last)}.`
                    : ""}
                </p>
              ) : null}

              <h4>Сотрудники</h4>
              {(detail.caretakers || []).length ? (
                <ul style={{ paddingLeft: "1.1rem" }}>
                  {(detail.caretakers || []).map((person) => (
                    <li key={person.id}>
                      {person.author_label}
                      <span style={{ color: "var(--muted)" }}>
                        {" "}
                        · {person.source === "manual" ? "вручную" : "из комментария"}
                      </span>{" "}
                      <button type="button" className="secondary" onClick={() => onDismiss(person.id)}>
                        снять
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p style={{ color: "var(--muted)" }}>Пока никто не написал и вручную не назначен.</p>
              )}
              <label>
                Добавить{" "}
                <select
                  value=""
                  onChange={(e) => {
                    if (e.target.value) onAddCaretaker(e.target.value);
                  }}
                >
                  <option value="">сотрудника…</option>
                  {staff
                    .filter((person) => person.author_user_id)
                    .map((person) => (
                      <option key={person.author_user_id} value={person.author_user_id}>
                        {person.author_label}
                      </option>
                    ))}
                </select>
              </label>

              <h4>По неделям</h4>
              {(detail.weeks || []).length ? (
                <table>
                  <thead>
                    <tr>
                      <th>Неделя</th>
                      <th>Статус</th>
                      <th>Дней</th>
                      <th>12 мес</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.weeks.map((week) => (
                      <tr key={week.week_start}>
                        <td>{week.week_start}</td>
                        <td>{week.status}</td>
                        <td>{week.days_since}</td>
                        <td>{rub(week.rev_cur12)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p style={{ color: "var(--muted)" }}>Недель пока нет.</p>
              )}

              <h4>Комментарии</h4>
              {(detail.comments || []).length ? (
                detail.comments.map((group) => (
                  <article key={group.thread_id || group.parts[0].id} style={{ marginBottom: "0.8rem" }}>
                    <div style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
                      {group.author_label} · {fmtWhen(group.created_at)}
                      {group.parts.length > 1 ? " · одна мысль из нескольких сообщений" : ""}
                    </div>
                    <div style={{ whiteSpace: "pre-wrap" }}>
                      {group.parts.map((part) => part.text).join("\n\n")}
                    </div>
                  </article>
                ))
              ) : (
                <p style={{ color: "var(--muted)" }}>Комментариев нет.</p>
              )}

              {detail.sizes ? (
                <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>Размеры: {detail.sizes}</p>
              ) : null}
              {(detail.brands || []).length ? (
                <p style={{ color: "var(--muted)", fontSize: "0.9rem" }}>Бренды: {detail.brands.join(", ")}</p>
              ) : null}
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Загрузка…</p>
          )}
              <button type="button" className="secondary" onClick={() => setSelectedId("")} style={{ marginTop: "0.75rem" }}>
                Закрыть
              </button>
            </div>
          </div>
        ) : null}
        </>
      )}
        </>
      )}
    </section>
  );
}
