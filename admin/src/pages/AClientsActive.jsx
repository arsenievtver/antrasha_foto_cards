import { useEffect, useMemo, useState } from "react";
import { fetchActiveAClients } from "../api.js";

function rub(value) {
  if (value === null || value === undefined || value === "") return "—";
  return `${Math.round(Number(value)).toLocaleString("ru-RU")} ₽`;
}

function pct(value) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toLocaleString("ru-RU")}%`;
}

function num(value, digits) {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return digits === undefined ? n.toLocaleString("ru-RU") : n.toLocaleString("ru-RU", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function csvCell(value) {
  const text = value === null || value === undefined ? "" : String(value);
  return /[;"\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function listText(value) {
  return Array.isArray(value) ? value.join(", ") : value || "";
}

function sumOf(rows, key) {
  return rows.reduce((acc, row) => acc + (Number(row[key]) || 0), 0);
}

function avgOf(rows, key) {
  const values = rows.map((row) => row[key]).filter((value) => value !== null && value !== undefined && value !== "");
  if (!values.length) return null;
  return values.reduce((acc, value) => acc + Number(value), 0) / values.length;
}

function trendOf(cur, prev) {
  if (!prev) return null;
  return Math.round(((cur || 0) / prev - 1) * 1000) / 10;
}

function cellValue(row, key) {
  if (key === "brands" || key === "categories") return listText(row[key]);
  return row[key];
}

function compareRows(a, b, key, dir) {
  const av = cellValue(a, key);
  const bv = cellValue(b, key);
  const aEmpty = av === null || av === undefined || av === "";
  const bEmpty = bv === null || bv === undefined || bv === "";
  if (aEmpty && bEmpty) return 0;
  if (aEmpty) return 1;
  if (bEmpty) return -1;
  const cmp =
    typeof av === "number" && typeof bv === "number"
      ? av - bv
      : String(av).localeCompare(String(bv), "ru", { numeric: true });
  return dir === "asc" ? cmp : -cmp;
}

function tally(rows, pick) {
  const acc = new Map();
  for (const row of rows) {
    for (const value of pick(row)) {
      const text = String(value || "").trim();
      if (!text) continue;
      acc.set(text, (acc.get(text) || 0) + 1);
    }
  }
  return [...acc.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "ru")).slice(0, 8);
}

const LEFT_COLUMNS = [
  { key: "name", label: "Клиент" },
  { key: "where", label: "Куда ушёл" },
  { key: "rev_cur12", label: "Последние 12 мес", money: true },
  { key: "rev_prev12", label: "Прошлые 12 мес", money: true },
];

const COLUMNS = [
  { key: "name", label: "Клиент" },
  { key: "cohort", label: "К прошлой неделе" },
  { key: "status", label: "Статус" },
  { key: "rev_prev12", label: "Прошлые 12 мес", money: true },
  { key: "rev_cur12", label: "Последние 12 мес", money: true },
  { key: "trend_pct", label: "Динамика", percent: true },
  { key: "pace", label: "Темп" },
  { key: "week_pct", label: "К срезу", percent: true },
  { key: "avg_check", label: "Средний чек", money: true },
  { key: "median_gap", label: "Интервал, дн" },
  { key: "visits", label: "Визиты" },
  { key: "days_since", label: "Дней с визита" },
  { key: "sizes", label: "Размеры" },
  { key: "brands", label: "Марки" },
  { key: "categories", label: "Предпочтения" },
];

function downloadActive(rows, week) {
  const head = [
    "Клиент",
    "Телефон",
    "К прошлой неделе",
    "Статус",
    "Выручка прошлые 12 мес",
    "Выручка последние 12 мес",
    "Динамика %",
    "Темп",
    "К прошлому срезу %",
    "Средний чек",
    "Интервал, дн",
    "Визиты",
    "Дней с визита",
    "Размеры",
    "Марки",
    "Предпочтения",
  ];
  const body = rows.map((row) => [
    row.name,
    row.phone,
    row.cohort || "",
    row.status,
    row.rev_prev12,
    row.rev_cur12,
    row.trend_pct,
    row.pace,
    row.week_pct,
    row.avg_check,
    row.median_gap,
    row.visits,
    row.days_since,
    row.sizes,
    listText(row.brands),
    listText(row.categories),
  ]);
  const text = `\uFEFF${[head, ...body].map((line) => line.map(csvCell).join(";")).join("\n")}`;
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `a-clients-active-${week || new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function paceColor(pace) {
  if (pace === "растёт") return "var(--ok, #1b7f3a)";
  if (pace === "падает") return "var(--danger, #b42318)";
  return "inherit";
}

export default function AClientsActive() {
  const [board, setBoard] = useState(null);
  const [err, setErr] = useState("");
  const [q, setQ] = useState("");
  const [slice, setSlice] = useState("all");
  const [sort, setSort] = useState({ key: "rev_cur12", dir: "desc" });

  useEffect(() => {
    let cancelled = false;
    fetchActiveAClients()
      .then((row) => {
        if (!cancelled) setBoard(row);
      })
      .catch((e) => {
        if (!cancelled) setErr(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const hasPrevious = Boolean(board?.summary?.has_previous);
  const items = board?.items || [];
  const left = board?.left || [];

  const searched = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return items;
    return items.filter(
      (row) => row.name?.toLowerCase().includes(needle) || String(row.phone || "").includes(needle),
    );
  }, [items, q]);

  const searchedLeft = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return left;
    return left.filter(
      (row) => row.name?.toLowerCase().includes(needle) || String(row.phone || "").includes(needle),
    );
  }, [left, q]);

  const slices = useMemo(() => {
    const base = [
      { id: "all", label: "Всего", rows: searched },
      { id: "growing", label: "Растут", rows: searched.filter((row) => row.pace === "растёт") },
      { id: "falling", label: "Падают", rows: searched.filter((row) => row.pace === "падает") },
      { id: "flat", label: "Ровно", rows: searched.filter((row) => row.pace === "ровно") },
    ];
    if (!hasPrevious) return base;
    return [
      base[0],
      { id: "new", label: "Новые", rows: searched.filter((row) => row.cohort === "новый") },
      { id: "stayed", label: "Были", rows: searched.filter((row) => row.cohort === "был") },
      ...base.slice(1),
      { id: "left", label: "Выбыли", rows: searchedLeft },
    ];
  }, [searched, searchedLeft, hasPrevious]);

  const visible = slices.find((item) => item.id === slice)?.rows || searched;
  const showingLeft = slice === "left";
  const columns = showingLeft ? LEFT_COLUMNS : COLUMNS;
  const sortKey = columns.some((col) => col.key === sort.key) ? sort.key : "rev_cur12";

  const sorted = useMemo(
    () => [...visible].sort((a, b) => compareRows(a, b, sortKey, sort.dir)),
    [visible, sortKey, sort.dir],
  );

  const sizes = tally(showingLeft ? [] : sorted, (row) => String(row.sizes || "").split(";"));
  const brands = tally(showingLeft ? [] : sorted, (row) => row.brands || []);
  const categories = tally(showingLeft ? [] : sorted, (row) => row.categories || []);

  function onSort(key) {
    setSort((prev) => (prev.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" }));
  }

  if (err) return <p className="error">{err}</p>;
  if (!board) return <p style={{ color: "var(--muted)" }}>Загружаем срез…</p>;
  if (!board.ready) {
    return (
      <p style={{ color: "var(--muted)", maxWidth: 720 }}>
        Среза ещё нет. Он запишется в понедельник, когда неделя запросит МойСклад. Прошлые недели хранили только
        список на контроле, поэтому действующих за них восстановить нельзя.
      </p>
    );
  }

  const prev = sumOf(showingLeft ? sorted : sorted, "rev_prev12");
  const cur = sumOf(sorted, "rev_cur12");

  return (
    <>
      <p style={{ color: "var(--muted)", marginTop: 0, maxWidth: 760 }}>
        Категория А, которая держит ритм: не в списке на контроле. Срез от {board.week_start}
        {board.prev_week_start ? `, сравнение с ${board.prev_week_start}` : ""}. Динамика — последние 12 месяцев к
        предыдущим 12. «К срезу» — как изменилась эта выручка с прошлого понедельника. Полоса ±5% считается ровной.
      </p>
      {!hasPrevious ? (
        <p style={{ color: "var(--muted)" }}>
          Это первый срез. Новых, оставшихся и выбывших можно будет увидеть со следующей недели.
        </p>
      ) : null}

      <div className="flex-gap" style={{ flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Имя или телефон" style={{ minWidth: 180 }} />
        <button type="button" className="secondary" disabled={!sorted.length || showingLeft} onClick={() => downloadActive(sorted, board.week_start)}>
          Скачать CSV
        </button>
      </div>

      <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
        <table>
          <thead>
            <tr>
              <th>Срез</th>
              <th>Клиентов</th>
              <th>Прошлые 12 мес</th>
              <th>Последние 12 мес</th>
              <th>Динамика</th>
              <th>Средний чек</th>
              <th>Интервал, дн</th>
            </tr>
          </thead>
          <tbody>
            {slices.map((item) => {
              const itemPrev = sumOf(item.rows, "rev_prev12");
              const itemCur = sumOf(item.rows, "rev_cur12");
              const active = item.id === slice;
              return (
                <tr
                  key={item.id}
                  onClick={() => setSlice(active && item.id !== "all" ? "all" : item.id)}
                  style={{ cursor: "pointer", background: active ? "var(--row-active, rgba(0,0,0,0.04))" : undefined }}
                >
                  <td>{item.label}</td>
                  <td>{item.rows.length}</td>
                  <td>{rub(itemPrev)}</td>
                  <td>{rub(itemCur)}</td>
                  <td>{pct(trendOf(itemCur, itemPrev))}</td>
                  <td>{item.id === "left" ? "—" : rub(avgOf(item.rows, "avg_check"))}</td>
                  <td>{item.id === "left" ? "—" : num(avgOf(item.rows, "median_gap"), 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p style={{ color: "var(--muted)", marginBottom: 0 }}>
          В выборке {sorted.length}: последние 12 мес {rub(cur)}, прошлые {rub(prev)}, динамика {pct(trendOf(cur, prev))}.
        </p>
      </div>

      {showingLeft ? null : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1rem", marginBottom: "1rem" }}>
          <Preference title="Размеры" rows={sizes} />
          <Preference title="Предпочтения" rows={categories} />
          <Preference title="Марки" rows={brands} />
        </div>
      )}

      <div style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} onClick={() => onSort(col.key)} style={{ cursor: "pointer", whiteSpace: "nowrap" }}>
                  {col.label}
                  {sortKey === col.key ? (sort.dir === "asc" ? " ↑" : " ↓") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.id}>
                {columns.map((col) => (
                  <td key={col.key} style={{ color: col.key === "pace" ? paceColor(row.pace) : undefined, whiteSpace: col.money || col.percent ? "nowrap" : undefined }}>
                    {col.key === "name" ? (
                      <>
                        {row.name}
                        <div style={{ color: "var(--muted)", fontSize: "0.85rem" }}>{row.phone}</div>
                      </>
                    ) : col.money ? (
                      rub(row[col.key])
                    ) : col.percent ? (
                      pct(row[col.key])
                    ) : col.key === "cohort" ? (
                      row.cohort || "—"
                    ) : col.key === "brands" || col.key === "categories" ? (
                      listText(row[col.key]) || "—"
                    ) : (
                      row[col.key] ?? "—"
                    )}
                  </td>
                ))}
              </tr>
            ))}
            {!sorted.length ? (
              <tr>
                <td colSpan={columns.length}>{showingLeft ? "Никто не выбыл." : "В этом срезе никого нет."}</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Preference({ title, rows }) {
  return (
    <div>
      <h3 style={{ margin: "0 0 0.35rem" }}>{title}</h3>
      {rows.length ? (
        <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
          {rows.map(([name, count]) => (
            <li key={name}>
              {name} <span style={{ color: "var(--muted)" }}>{count}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p style={{ color: "var(--muted)", margin: 0 }}>—</p>
      )}
    </div>
  );
}
