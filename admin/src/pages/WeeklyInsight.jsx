import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchWeeklyReport, fetchWeeklyReports, runWeeklyReport } from "../api.js";

const POLL_MS = 10000;
const STATUS = { running: "формируется", done: "готов", error: "ошибка" };
const TRIGGER = { schedule: "по расписанию", manual: "вручную" };

const rub = (v) => (v === null || v === undefined ? "—" : `${Math.round(v).toLocaleString("ru-RU")} ₽`);
const mln = (v) => (v === null || v === undefined ? "—" : `${(v / 1e6).toFixed(2)} млн`);
const pct = (v) => (v === null || v === undefined ? "—" : `${v}%`);
const num = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString("ru-RU"));

function fmtDateTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("ru-RU");
  } catch {
    return String(iso);
  }
}

function change(cur, prev) {
  if (!prev || cur === null || cur === undefined) return "—";
  const v = Math.round((cur / prev - 1) * 100);
  return `${v > 0 ? "+" : ""}${v}%`;
}

function csvCell(v) {
  const s = v === null || v === undefined ? "" : String(v);
  return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function downloadWatchlist(report) {
  const head = [
    "Клиент", "Телефон", "Статус", "Последняя покупка", "Дней назад", "Обычный интервал, дн",
    "Выручка прошлые 12 мес", "Выручка последние 12 мес", "Покупок за 24 мес", "Бренды", "Категории",
    "Размеры", "Средняя скидка %", "Доля уценки %", "Подборка",
  ];
  const rows = (report.watchlist || []).map((w) => [
    w.name, w.phone, w.status, w.last, w.days_since, w.median_gap, w.rev_prev12, w.rev_cur12, w.visits,
    (w.brands || []).join(", "), (w.categories || []).join(", "), w.sizes, w.avg_discount_pct, w.markdown_share_pct,
    (w.picks || []).map((p) => `${p.name} — ${p.price} ₽${p.old ? " (старый)" : ""}`).join(" | "),
  ]);
  const text = "\uFEFF" + [head, ...rows].map((r) => r.map(csvCell).join(";")).join("\n");
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `clients-watchlist-${report.week_start}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function Table({ head, rows }) {
  return (
    <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
      <table>
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td key={j}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WeekSection({ week }) {
  const metrics = [
    ["Выручка", "revenue", rub],
    ["Чеков", "checks", num],
    ["Штук", "units", num],
    ["Средний чек", "avg_check", rub],
    ["Средняя скидка", "avg_discount_pct", pct],
    ["Штук с уценкой >20%", "markdown_units_pct", pct],
  ];
  const ret = week.returned_from_prev_watchlist || {};
  return (
    <>
      <h3>
        За неделю {week.period.from} — {week.period.to}
      </h3>
      <Table
        head={["", "Неделя", "Прошлая неделя", "Год назад", "К году"]}
        rows={metrics.map(([label, key, f]) => [
          label,
          f(week.sales[key]),
          f(week.prev_week[key]),
          f(week.same_week_last_year[key]),
          key === "revenue" || key === "checks" ? change(week.sales[key], week.same_week_last_year[key]) : "",
        ])}
      />
      <p>
        Покупателей с картой: {week.buyers_named}, из них новых {week.buyers_new}, клиентов A {week.buyers_a}.
        {ret.watchlist_size
          ? ` Из прошлого списка на контроле вернулись ${ret.clients} из ${ret.watchlist_size} на ${rub(ret.revenue)}.`
          : ""}{" "}
        Приход: {num(week.arrivals.units)} шт, {week.arrivals.models} моделей на {rub(week.arrivals.cost)}.
      </p>
      <div className="flex-gap" style={{ flexWrap: "wrap", gap: "1.5rem", alignItems: "flex-start" }}>
        <Table head={["Категория", "Выручка", "Доля"]} rows={week.top_categories.map((r) => [r.key, rub(r.revenue), pct(r.share_pct)])} />
        <Table head={["Бренд", "Выручка", "Доля"]} rows={week.top_brands.map((r) => [r.key, rub(r.revenue), pct(r.share_pct)])} />
      </div>
    </>
  );
}

function DynamicsSection({ dynamics }) {
  const max = Math.max(1, ...dynamics.map((d) => Math.max(d.revenue || 0, d.revenue_last_year || 0)));
  return (
    <>
      <h3>Динамика, 13 недель</h3>
      <Table
        head={["Неделя с", "Выручка", "", "Год назад", "Чеков", "Скидка", "Уценка", "Приход (себест.)"]}
        rows={dynamics.map((d) => [
          d.week_start,
          rub(d.revenue),
          <div key="bar" style={{ width: 160 }}>
            <div style={{ height: 8, width: `${((d.revenue || 0) / max) * 100}%`, background: "var(--accent, #4a7)" }} />
            <div style={{ height: 4, marginTop: 2, width: `${((d.revenue_last_year || 0) / max) * 100}%`, background: "var(--muted, #999)" }} />
          </div>,
          rub(d.revenue_last_year),
          num(d.checks),
          pct(d.avg_discount_pct),
          pct(d.markdown_units_pct),
          rub(d.arrivals_cost),
        ])}
      />
    </>
  );
}

function OverallSection({ overall, clients }) {
  const hist = overall.stock_cost_history || {};
  return (
    <>
      <h3>
        В общем: 12 мес ({overall.period_cur.from} — {overall.period_cur.to})
      </h3>
      <Table
        head={["", "Последние 12 мес", "Прошлые 12 мес", "Изменение"]}
        rows={[
          ["Выручка по чекам", mln(overall.sales_cur.revenue), mln(overall.sales_prev.revenue), change(overall.sales_cur.revenue, overall.sales_prev.revenue)],
          ["Выручка все каналы (отчёт прибыльности)", mln(overall.revenue_all_channels_cur), mln(overall.revenue_all_channels_prev), change(overall.revenue_all_channels_cur, overall.revenue_all_channels_prev)],
          ["Себестоимость продаж", mln(overall.cogs_cur), mln(overall.cogs_prev), change(overall.cogs_cur, overall.cogs_prev)],
          ["Закуплено (по себестоимости)", mln(overall.bought_cost_cur), mln(overall.bought_cost_prev), change(overall.bought_cost_cur, overall.bought_cost_prev)],
          ["Чеков", num(overall.sales_cur.checks), num(overall.sales_prev.checks), change(overall.sales_cur.checks, overall.sales_prev.checks)],
          ["Средняя скидка", pct(overall.sales_cur.avg_discount_pct), pct(overall.sales_prev.avg_discount_pct), ""],
          ["Штук с уценкой", pct(overall.sales_cur.markdown_units_pct), pct(overall.sales_prev.markdown_units_pct), ""],
        ]}
      />
      <p>
        Склад сейчас {mln(overall.stock_cost_now)} по себестоимости
        {Object.entries(hist).map(([d, v]) => `, на ${d} — ${mln(v)}`).join("")}. Запас — {overall.months_of_stock ?? "—"} мес
        продаж. Валовая маржа {pct(overall.gross_margin_pct)}.
      </p>
      <Table
        head={["Возраст вещи при продаже", "Выручка", "Доля", "Скидка", "Уценка"]}
        rows={Object.entries(overall.sales_by_age_at_sale || {}).map(([k, v]) => [k, mln(v.revenue), pct(v.revenue_share_pct), pct(v.avg_discount_pct), pct(v.markdown_units_pct)])}
      />
      <h3>Клиенты</h3>
      <Table
        head={["Сегмент", "Клиентов", "Прошлые 12 мес", "Последние 12 мес", "Изменение"]}
        rows={Object.entries(clients.segments).map(([s, v]) => [s, v.clients, mln(v.rev_prev12), mln(v.rev_cur12), change(v.rev_cur12, v.rev_prev12)])}
      />
      <Table
        head={["Клиенты A", "Клиентов", "Прошлые 12 мес", "Последние 12 мес"]}
        rows={Object.entries(clients.a_status).map(([s, v]) => [s, v.clients, mln(v.rev_prev12), mln(v.rev_cur12)])}
      />
    </>
  );
}

function AssortmentSection({ asm }) {
  const agg = (r) => [num(r.received), mln(r.cost_received), pct(r.st90_pct), pct(r.st180_pct), pct(r.st180_card_pct), r.revenue_per_rub_bought ?? "—", mln(r.stock_cost)];
  const aggHead = ["Пришло шт", "Закупка", "st90", "st180", "st180 по карте", "₽ на ₽ закупки", "Остаток"];
  const flagged = (asm.size_curve || []).filter((r) => r.verdict);
  const models = (rows) =>
    rows.map((r) => [r.brand, r.model, r.season, num(r.received), pct(r.st_to_date_pct), r.sold_out_sizes || "—", rub(r.stock_cost)]);
  const modelHead = ["Бренд", "Модель", "Сезон", "Пришло", "Продано", "Выбиты размеры", "Остаток"];
  return (
    <>
      <h3>Сезоны (брендовый товар)</h3>
      <Table
        head={["Сезон", "Моделей", ...aggHead, "Без бренда шт"]}
        rows={(asm.seasons || []).map((r) => [r.season, r.models, ...agg(r), num(r.unbranded_received)])}
      />
      <h3>Кандидаты на дозаказ</h3>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>Свежие модели, проданные на 60% и больше, с выбитыми размерами.</p>
      <Table head={modelHead} rows={models(asm.reorder_candidates || [])} />
      <h3>
        Мёртвый сток: {asm.dead.models} моделей, остаток {mln(asm.dead.stock_cost)}
      </h3>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>Продано не больше 20% за 180 дней. Для личных подборок, не для распродажи.</p>
      <Table head={modelHead} rows={models(asm.dead.top || [])} />
      <h3>Размерная сетка (сезоны {(asm.mature_seasons || []).join(", ")})</h3>
      <Table
        head={["Пол", "Категория", "Размер", "Доля прихода", "Доля продаж за 120 дн", "Индекс", "Распродан за 45 дн", "Вывод"]}
        rows={flagged.map((r) => [r.gender, r.category, r.size, pct(r.received_share_pct), pct(r.sold_share_pct), r.index, pct(r.fast_sellout_pct), r.verdict])}
      />
      <h3>Бренды</h3>
      <Table head={["Бренд", "Моделей", ...aggHead]} rows={(asm.brands || []).map((r) => [r.brand, r.models, ...agg(r)])} />
      <h3>Категории</h3>
      <Table head={["Пол", "Категория", ...aggHead]} rows={(asm.categories || []).map((r) => [r.gender, r.category, ...agg(r)])} />
    </>
  );
}

function WatchlistSection({ report }) {
  const list = report.watchlist || [];
  if (!list.length) return null;
  return (
    <>
      <div className="flex-gap" style={{ alignItems: "baseline", gap: "1rem" }}>
        <h3>Клиенты A на контроле ({list.length})</h3>
        <button type="button" className="secondary" onClick={() => downloadWatchlist(report)}>
          Скачать CSV
        </button>
      </div>
      <Table
        head={["Клиент", "Телефон", "Статус", "Последняя", "Прошлые 12 мес", "Последние 12 мес", "Размеры", "Подборка"]}
        rows={list.map((w) => [
          w.name,
          <span key="p" style={{ whiteSpace: "nowrap" }}>{w.phone || "—"}</span>,
          w.status,
          <span key="d" style={{ whiteSpace: "nowrap" }}>{w.last} ({w.days_since} дн)</span>,
          rub(w.rev_prev12),
          rub(w.rev_cur12),
          <span key="s" style={{ fontSize: "0.85rem" }}>{w.sizes}</span>,
          <ul key="k" style={{ margin: 0, paddingLeft: "1rem", fontSize: "0.85rem" }}>
            {(w.picks || []).map((p) => (
              <li key={p.name}>
                {p.name} — {rub(p.price)}
                {p.old ? " · старый" : ""}
              </li>
            ))}
          </ul>,
        ])}
      />
    </>
  );
}

export default function WeeklyInsight() {
  const [list, setList] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [report, setReport] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const loadList = useCallback(async () => {
    const data = await fetchWeeklyReports();
    setList(data);
    return data;
  }, []);

  useEffect(() => {
    loadList()
      .then((data) => {
        const first = data.items.find((r) => r.status === "done") || data.items[0];
        if (first) setSelectedId(first.id);
      })
      .catch((e) => setErr(e.message));
  }, [loadList]);

  useEffect(() => {
    if (!selectedId) return;
    fetchWeeklyReport(selectedId)
      .then(setReport)
      .catch((e) => setErr(e.message));
  }, [selectedId]);

  const running = list?.items?.some((r) => r.status === "running");
  useEffect(() => {
    if (!running) return undefined;
    const t = setInterval(async () => {
      try {
        const data = await loadList();
        const cur = data.items.find((r) => r.id === selectedId);
        if (cur && cur.status !== "running") setReport(await fetchWeeklyReport(selectedId));
      } catch (e) {
        setErr(e.message);
      }
    }, POLL_MS);
    return () => clearInterval(t);
  }, [running, selectedId, loadList]);

  async function runNow() {
    setBusy(true);
    setErr("");
    try {
      const row = await runWeeklyReport();
      await loadList();
      setSelectedId(row.id);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const m = report?.metrics;
  return (
    <section>
      <h2 style={{ marginTop: 0, marginBottom: "0.35rem" }}>Недельный отчёт</h2>
      <p style={{ color: "var(--muted)", marginTop: 0, marginBottom: "0.85rem", maxWidth: 760 }}>
        Данные МойСклад за прошлую неделю (пн–вс), 13 недель и 12 месяцев: продажи, клиенты A, сезоны, размеры, бренды.
        {list?.schedule_enabled
          ? ` Строится сам в понедельник с ${list.schedule_hour}:00 МСК.`
          : " Расписание выключено."}{" "}
        Те же отчёты читает MCP закупок: get_weekly_report.
      </p>
      {list && !list.moysklad_configured ? <p className="error">На сервере не задан MOYSKLAD_TOKEN.</p> : null}
      {list && !list.ai_configured ? (
        <p style={{ color: "var(--muted)" }}>Без ANTHROPIC_API_KEY текст собирается по правилам, без модели.</p>
      ) : null}

      <div className="flex-gap" style={{ flexWrap: "wrap", gap: "0.5rem", marginBottom: "0.75rem" }}>
        <button type="button" onClick={runNow} disabled={busy || running || !list?.moysklad_configured}>
          {running ? "Формируется…" : "Запустить сейчас"}
        </button>
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} disabled={!list?.items?.length}>
          {(list?.items || []).map((r) => (
            <option key={r.id} value={r.id}>
              Неделя с {r.week_start} · {STATUS[r.status] || r.status} · {TRIGGER[r.trigger] || r.trigger} · {fmtDateTime(r.started_at)}
            </option>
          ))}
        </select>
      </div>

      {err ? <p className="error">{err}</p> : null}
      {list && !list.items.length ? <p style={{ color: "var(--muted)" }}>Отчётов ещё нет.</p> : null}

      {report?.status === "running" ? (
        <p>Отчёт формируется — обычно 3–5 минут. Страница обновится сама.</p>
      ) : null}
      {report?.status === "error" ? <p className="error">Ошибка: {report.error}</p> : null}

      {report?.summary_md ? (
        <div className="wh-ai-msg__md" style={{ maxWidth: 860, marginBottom: "1.5rem" }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{report.summary_md}</ReactMarkdown>
          <p style={{ color: "var(--muted)", fontSize: "0.85rem" }}>
            {report.summary_model ? `Текст: ${report.summary_model}` : "Текст по правилам"} · запросов к МойСклад:{" "}
            {report.ms_requests ?? "—"} · готов {fmtDateTime(report.finished_at)}
          </p>
        </div>
      ) : null}

      {m ? (
        <>
          <WeekSection week={m.week} />
          <DynamicsSection dynamics={m.dynamics} />
          <OverallSection overall={m.overall} clients={m.clients} />
          <h3>Предложения по правилам</h3>
          <ul>
            {(m.suggestions || []).map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          {m.staff_feedback?.texts?.length ? (
            <>
              <h3>«Спрос» за неделю</h3>
              <Table head={["День", "Кто", "Текст"]} rows={m.staff_feedback.texts.map((t) => [t.day, t.author, t.text])} />
            </>
          ) : null}
          <WatchlistSection report={report} />
          <AssortmentSection asm={m.assortment} />
        </>
      ) : null}
    </section>
  );
}
