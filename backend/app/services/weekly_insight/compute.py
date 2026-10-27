"""Недельная аналитика: неделя, динамика, итог за 12 месяцев, клиенты, ассортимент.

Только расчёты над плоскими записями fetch.Dataset — без сети и базы.
Скидка до CARD_DISCOUNT_MAX % считается ценой по карте, выше — уценкой.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable

from app.services.weekly_insight.fetch import Dataset
from app.services.weekly_insight.parse import (
    NON_ASSORTMENT_TOP_FOLDERS,
    arrival_month,
    months_between,
    season_of,
    size_sort_key,
)

CARD_DISCOUNT_MAX = 20
PLACEHOLDER_RE = re.compile(r"^(отказался|покупатель|розничный покупатель)$", re.I)
NON_SIZED = {"Аксессуары", "Бижутерия", "Сумка", "Ремни", "Галстук", "Бабочка", "Кошелек", "Очки", "Зонт"}
SUMMER_ONLY = {"Бриджи, шорты"}
FAST_SELLOUT_DAYS = 45
SIZE_WINDOW_DAYS = 120
DYNAMICS_WEEKS = 13
WATCH_STATUSES = ("просрочил визит", "покупает меньше", "ушёл (>12 мес)")
G_LABEL = {"M": "муж", "W": "жен"}


@dataclass(frozen=True)
class Periods:
    week_start: date
    week_end: date
    cur_from: date
    prev_from: date
    history_from: date

    @classmethod
    def for_run(cls, run_day: date) -> "Periods":
        week_start = run_day - timedelta(days=run_day.weekday() + 7)
        week_end = week_start + timedelta(days=6)
        cur_from = week_end - timedelta(days=364)
        prev_from = cur_from - timedelta(days=365)
        return cls(week_start, week_end, cur_from, prev_from, prev_from - timedelta(days=120))


def _d(s: str) -> date:
    return date.fromisoformat(s[:10])


def _r(x: float | None, nd: int = 0) -> float | int | None:
    if x is None:
        return None
    return round(x, nd) if nd else int(round(x))


def _pct(a: float, b: float, nd: int = 1) -> float | None:
    return round(a / b * 100, nd) if b else None


def _change_pct(cur: float, prev: float) -> float | None:
    return round((cur / prev - 1) * 100, 1) if prev else None


def sales_block(lines: Iterable[dict]) -> dict:
    lines = list(lines)
    rev = sum(l["sum"] for l in lines)
    listed = sum(l["qty"] * l["list_price"] for l in lines)
    units = sum(l["qty"] for l in lines)
    checks = len({l["check_id"] for l in lines})
    markdown = sum(l["qty"] for l in lines if l["discount_pct"] > CARD_DISCOUNT_MAX)
    return {
        "revenue": _r(rev),
        "checks": checks,
        "units": _r(units),
        "avg_check": _r(rev / checks) if checks else None,
        "avg_discount_pct": _pct(listed - rev, listed),
        "markdown_units_pct": _pct(markdown, units),
    }


def _in(lines: list[dict], a: date, b: date) -> list[dict]:
    return [l for l in lines if a <= l["_day"] <= b]


def _is_named(line: dict) -> bool:
    name = (line.get("agent_name") or "").strip()
    return bool(line.get("agent_id")) and not PLACEHOLDER_RE.match(name)


# ---------- клиенты ----------


def client_profiles(lines: list[dict], catalog: dict[str, dict], p: Periods) -> list[dict]:
    by_client: dict[str, list[dict]] = defaultdict(list)
    for l in lines:
        if _is_named(l) and l["_day"] >= p.prev_from and l["_day"] <= p.week_end:
            by_client[l["agent_id"]].append(l)
    profiles = []
    for cid, ls in by_client.items():
        days = sorted({l["_day"] for l in ls})
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        genders = Counter(l["_gender"] for l in ls if l["_gender"] in ("M", "W"))
        sizes: dict[tuple, Counter] = defaultdict(Counter)
        for l in ls:
            if l["size"] and l["_category"] and l["_category"] not in NON_SIZED:
                sizes[(l["_gender"], l["_category"])][l["size"]] += l["qty"]
        items = sum(l["qty"] for l in ls)
        listed = sum(l["qty"] * l["list_price"] for l in ls)
        rev24 = sum(l["sum"] for l in ls)
        profiles.append(
            {
                "id": cid,
                "name": ls[-1].get("agent_name"),
                "phone": next((l.get("agent_phone") for l in reversed(ls) if l.get("agent_phone")), None),
                "rev24": rev24,
                "rev_cur": sum(l["sum"] for l in ls if l["_day"] >= p.cur_from),
                "rev_prev": sum(l["sum"] for l in ls if l["_day"] < p.cur_from),
                "visits": len(days),
                "last": days[-1],
                "days_since": (p.week_end - days[-1]).days,
                "median_gap": statistics.median(gaps) if gaps else None,
                "gender": genders.most_common(1)[0][0] if genders else None,
                "brands": Counter(l["_brand"] for l in ls if l["_brand"]),
                "cats": Counter(l["_category"] for l in ls if l["_category"]),
                "sizes": {k: v.most_common(1)[0][0] for k, v in sizes.items()},
                "avg_discount": _pct(listed - rev24, listed) or 0,
                "markdown_share": _pct(sum(l["qty"] for l in ls if l["discount_pct"] > CARD_DISCOUNT_MAX), items) or 0,
                "bought_products": {l["product_id"] for l in ls},
            }
        )
    profiles.sort(key=lambda x: -x["rev24"])
    n_a = max(1, round(len(profiles) * 0.2))
    for i, pr in enumerate(profiles):
        pr["segment"] = "A" if i < n_a else ("B" if i < n_a * 2.5 else "C")
        pr["status"] = _client_status(pr)
    return profiles


def _client_status(pr: dict) -> str:
    gap = pr["median_gap"]
    if pr["days_since"] > 365:
        return "ушёл (>12 мес)"
    if gap is None:
        return "одна покупка"
    if pr["days_since"] > max(1.5 * gap, 90):
        return "просрочил визит"
    if pr["rev_prev"] > 0 and pr["rev_cur"] < 0.5 * pr["rev_prev"]:
        return "покупает меньше"
    return "в ритме"


# ---------- склад по размерам ----------


def stock_index(ds: Dataset, today: date) -> dict[tuple, list[dict]]:
    idx: dict[tuple, list[dict]] = defaultdict(list)
    for s in ds.stock:
        c = ds.catalog.get(s["product_id"] or "") or {}
        if not c or not s["size"] or c.get("top") in NON_ASSORTMENT_TOP_FOLDERS:
            continue
        arr = arrival_month(c.get("article"), c.get("name"), today)
        idx[(c["gender"], c["category"], s["size"])].append(
            {**s, "brand": c.get("brand"), "category": c["category"], "age_m": months_between(arr, today) if arr else None}
        )
    return idx


def picks_for(pr: dict, idx: dict[tuple, list[dict]], today: date) -> list[dict]:
    off_season = SUMMER_ONLY if today.month in (9, 10, 11, 12, 1, 2, 3) else set()
    top_cats = [c for c, _ in pr["cats"].most_common(6)]
    cands = []
    for (g, cat), size in pr["sizes"].items():
        if cat in off_season:
            continue
        rank = top_cats.index(cat) if cat in top_cats else 6
        for s in idx.get((g, cat, size), []):
            if s["product_id"] in pr["bought_products"]:
                continue
            hit = s["brand"] in pr["brands"]
            cands.append(((3 if hit else 0) + (6 - rank) * 0.5, s, hit))
    cands.sort(key=lambda t: -t[0])
    seen: set = set()
    per_cat: Counter = Counter()
    fresh, old = [], []
    for _, s, hit in cands:
        if s["product_id"] in seen or per_cat[s["category"]] >= 2 or s["age_m"] is None:
            continue
        if s["age_m"] <= 6 and len(fresh) < 4:
            fresh.append((s, hit))
        elif s["age_m"] > 12 and len(old) < 3:
            old.append((s, hit))
        else:
            continue
        seen.add(s["product_id"])
        per_cat[s["category"]] += 1
    return [
        {"name": s["name"], "price": _r(s["sale_price"]), "age_m": s["age_m"], "brand_match": hit, "old": s["age_m"] > 12}
        for s, hit in fresh + old
    ]


# ---------- ассортимент по модификациям ----------


def variant_rows(ds: Dataset, lines: list[dict], today: date) -> list[dict]:
    variants: dict[str, dict] = {}
    for a in ds.arrivals:
        key = a["variant_key"]
        if not key or a["qty"] <= 0:
            continue
        d = _d(a["day"])
        v = variants.setdefault(
            key, {"received": 0.0, "cost_sum": 0.0, "first": d, "size": a["size"], "name": a["variant_name"], "product_id": a["product_id"], "sales": [], "stock": 0.0}
        )
        v["received"] += a["qty"]
        v["cost_sum"] += a["qty"] * a["cost"]
        v["first"] = min(v["first"], d)
    for l in lines:
        v = variants.get(l["variant_key"] or "")
        if v:
            v["sales"].append(l)
    for s in ds.stock:
        v = variants.get(s["variant_key"] or "")
        if v:
            v["stock"] += s["stock"]
    rows = []
    for v in variants.values():
        c = ds.catalog.get(v["product_id"] or "") or {}
        if not c or c.get("top") in NON_ASSORTMENT_TOP_FOLDERS:
            continue
        first = v["first"]
        if any(l["_day"] < first for l in v["sales"]):
            continue
        cum, sellout = 0.0, None
        for l in sorted(v["sales"], key=lambda x: x["_day"]):
            cum += l["qty"]
            if sellout is None and cum >= v["received"]:
                sellout = (l["_day"] - first).days

        def within(days: int, card: bool = False) -> float:
            return sum(
                l["qty"] for l in v["sales"]
                if (l["_day"] - first).days <= days and (not card or l["discount_pct"] <= CARD_DISCOUNT_MAX)
            )

        rows.append(
            {
                "product_id": v["product_id"],
                "model": c["name"],
                "brand": c.get("brand") or "—",
                "gender": c["gender"],
                "category": c["category"],
                "size": v["size"],
                "season": season_of(v["name"], first),
                "first": first,
                "age": (today - first).days,
                "received": v["received"],
                "unit_cost": v["cost_sum"] / v["received"],
                "sold": sum(l["qty"] for l in v["sales"]),
                "sold_card": sum(l["qty"] for l in v["sales"] if l["discount_pct"] <= CARD_DISCOUNT_MAX),
                "revenue": sum(l["sum"] for l in v["sales"]),
                "sold90": within(90),
                "sold180": within(180),
                "sold_size_window": within(SIZE_WINDOW_DAYS),
                "card180": within(180, card=True),
                "sellout_day": sellout,
                "stock": v["stock"],
            }
        )
    return rows


def assortment_agg(items: list[dict]) -> dict:
    rec = sum(r["received"] for r in items)
    cost = sum(r["received"] * r["unit_cost"] for r in items)
    e90 = [r for r in items if r["age"] >= 90]
    e180 = [r for r in items if r["age"] >= 180]
    rec90 = sum(r["received"] for r in e90)
    rec180 = sum(r["received"] for r in e180)
    sold = sum(r["sold"] for r in items)
    revenue = sum(r["revenue"] for r in items)
    return {
        "models": len({r["product_id"] for r in items}),
        "received": _r(rec),
        "cost_received": _r(cost),
        "st90_pct": _pct(sum(r["sold90"] for r in e90), rec90),
        "st180_pct": _pct(sum(r["sold180"] for r in e180), rec180),
        "st180_card_pct": _pct(sum(r["card180"] for r in e180), rec180),
        "st_to_date_pct": _pct(sold, rec),
        "card_share_of_sold_pct": _pct(sum(r["sold_card"] for r in items), sold),
        "revenue": _r(revenue),
        "revenue_per_rub_bought": round(revenue / cost, 2) if cost else None,
        "stock_units": _r(sum(r["stock"] for r in items)),
        "stock_cost": _r(sum(r["stock"] * r["unit_cost"] for r in items)),
    }


def _group(items: Iterable[dict], key) -> dict:
    g: dict[Any, list[dict]] = defaultdict(list)
    for r in items:
        g[key(r)].append(r)
    return g


def _season_order(season: str) -> tuple[int, int]:
    return (int(season[2:]), 0 if season.startswith("ВЛ") else 1)


def size_curve(curve_rows: list[dict]) -> list[dict]:
    out = []
    eligible = [r for r in curve_rows if r["size"] and r["age"] >= SIZE_WINDOW_DAYS and r["category"] not in NON_SIZED]
    for (g, cat), items in _group(eligible, lambda r: (r["gender"], r["category"])).items():
        rec_total = sum(r["received"] for r in items)
        sold_total = sum(r["sold_size_window"] for r in items)
        if rec_total < 40 or sold_total < 15:
            continue
        for size, its in sorted(_group(items, lambda r: r["size"]).items(), key=lambda kv: size_sort_key(kv[0])):
            rec = sum(r["received"] for r in its)
            sold = sum(r["sold_size_window"] for r in its)
            fast = sum(1 for r in its if r["sellout_day"] is not None and r["sellout_day"] <= FAST_SELLOUT_DAYS) / len(its)
            index = (sold / sold_total) / (rec / rec_total) if rec else 0
            verdict = ""
            if rec >= 8:
                if index >= 1.25 or (fast >= 0.35 and index >= 1):
                    verdict = "добавить"
                elif index <= 0.75 and fast < 0.15:
                    verdict = "сократить"
            out.append(
                {
                    "gender": G_LABEL.get(g, "-"),
                    "category": cat,
                    "size": size,
                    "received": _r(rec),
                    "received_share_pct": _pct(rec, rec_total),
                    "sold120": _r(sold),
                    "sold_share_pct": _pct(sold, sold_total),
                    "index": round(index, 2),
                    "fast_sellout_pct": _r(fast * 100),
                    "verdict": verdict,
                }
            )
    return out


def assortment_section(ds: Dataset, lines: list[dict], today: date) -> dict:
    """Только брендовый товар: свой мерч и реализация без поставщика искажают сезоны."""
    all_rows = variant_rows(ds, lines, today)
    rows = [r for r in all_rows if r["brand"] != "—"]
    unbranded = _group((r for r in all_rows if r["brand"] == "—"), lambda r: r["season"])
    seasons_all = sorted({r["season"] for r in rows}, key=_season_order)
    season_age = {s: statistics.median([r["age"] for r in rows if r["season"] == s]) for s in seasons_all}
    recent = seasons_all[-5:]
    mature = [s for s in seasons_all if season_age[s] >= SIZE_WINDOW_DAYS][-3:]
    curve_rows = [r for r in rows if r["season"] in mature]

    brands = []
    for b, items in _group(curve_rows, lambda r: r["brand"]).items():
        a = assortment_agg(items)
        if a["received"] >= 30:
            brands.append({"brand": b, **a})
    brands.sort(key=lambda r: -r["cost_received"])

    categories = []
    for (g, cat), items in _group(curve_rows, lambda r: (r["gender"], r["category"])).items():
        a = assortment_agg(items)
        if a["received"] >= 30:
            categories.append({"gender": G_LABEL.get(g, "-"), "category": cat, **a})
    categories.sort(key=lambda r: -r["cost_received"])

    models = []
    for pid, items in _group([r for r in rows if r["season"] in recent], lambda r: r["product_id"]).items():
        r0 = items[0]
        sold_out = sorted({r["size"] for r in items if r["size"] and r["stock"] <= 0 and r["sold"] > 0}, key=size_sort_key)
        models.append(
            {
                "model": r0["model"],
                "brand": r0["brand"],
                "gender": G_LABEL.get(r0["gender"], "-"),
                "category": r0["category"],
                "season": r0["season"],
                "age_days": min(r["age"] for r in items),
                "sold_out_sizes": ", ".join(sold_out),
                **assortment_agg(items),
            }
        )
    dead = sorted(
        (m for m in models if m["received"] >= 3 and m["st180_pct"] is not None and m["st180_pct"] <= 20),
        key=lambda m: -m["stock_cost"],
    )
    reorder = sorted(
        (m for m in models if m["age_days"] <= 200 and m["received"] >= 3 and (m["st_to_date_pct"] or 0) >= 60 and m["sold_out_sizes"]),
        key=lambda m: (-(m["st_to_date_pct"] or 0), -(m["card_share_of_sold_pct"] or 0)),
    )
    sized = [r for r in curve_rows if r["size"] and r["age"] >= SIZE_WINDOW_DAYS]
    return {
        "seasons": [
            {
                "season": s,
                **assortment_agg([r for r in rows if r["season"] == s]),
                "unbranded_received": _r(sum(r["received"] for r in unbranded.get(s, []))),
            }
            for s in recent
        ],
        "mature_seasons": mature,
        "categories": categories,
        "brands": brands,
        "size_curve": size_curve(curve_rows),
        "depth": {
            "model_sizes": len(sized),
            "single_unit_pct": _pct(sum(1 for r in sized if r["received"] == 1), len(sized)),
            "sold_out_45d_pct": _pct(
                sum(1 for r in sized if r["sellout_day"] is not None and r["sellout_day"] <= FAST_SELLOUT_DAYS), len(sized)
            ),
        },
        "dead": {
            "models": len(dead),
            "stock_cost": _r(sum(m["stock_cost"] for m in dead)),
            "top": dead[:25],
        },
        "reorder_candidates": reorder[:25],
    }


# ---------- сборка отчёта ----------


def _prepare_lines(ds: Dataset) -> list[dict]:
    out = []
    for l in ds.sales:
        c = ds.catalog.get(l["product_id"] or "") or {}
        out.append({**l, "_day": _d(l["day"]), "_gender": c.get("gender"), "_category": c.get("category"), "_brand": c.get("brand")})
    return out


def _top(lines: list[dict], key, n: int) -> list[dict]:
    acc: dict[Any, float] = defaultdict(float)
    for l in lines:
        acc[key(l)] += l["sum"]
    total = sum(acc.values())
    return [{"key": k, "revenue": _r(v), "share_pct": _pct(v, total)} for k, v in sorted(acc.items(), key=lambda kv: -kv[1])[:n]]


def build_report(
    ds: Dataset,
    run_day: date,
    *,
    prev_watchlist_ids: set[str] | None = None,
    staff_feedback: dict | None = None,
) -> tuple[dict, list[dict]]:
    """→ (metrics без ФИО, watchlist с ФИО и телефонами)."""
    p = Periods.for_run(run_day)
    lines = _prepare_lines(ds)
    upto = [l for l in lines if l["_day"] <= p.week_end]

    week = _in(upto, p.week_start, p.week_end)
    week_named = {l["agent_id"] for l in week if _is_named(l)}
    before = {l["agent_id"] for l in upto if _is_named(l) and l["_day"] < p.week_start}

    profiles = client_profiles(upto, ds.catalog, p)
    seg = {pr["id"]: pr["segment"] for pr in profiles}
    prev_ids = prev_watchlist_ids or set()
    returned = [l for l in week if l["agent_id"] in prev_ids]

    def shifted(days: int) -> dict:
        return sales_block(_in(upto, p.week_start - timedelta(days=days), p.week_end - timedelta(days=days)))

    prev4 = [shifted(7 * k) for k in range(1, 5)]
    arrivals_week = [a for a in ds.arrivals if p.week_start <= _d(a["day"]) <= p.week_end]
    week_section = {
        "period": {"from": p.week_start.isoformat(), "to": p.week_end.isoformat()},
        "sales": sales_block(week),
        "prev_week": prev4[0],
        "same_week_last_year": shifted(364),
        "avg_prev_4_weeks_revenue": _r(statistics.mean(w["revenue"] for w in prev4)),
        "buyers_named": len(week_named),
        "buyers_new": len(week_named - before),
        "buyers_a": sum(1 for cid in week_named if seg.get(cid) == "A"),
        "returned_from_prev_watchlist": {
            "clients": len({l["agent_id"] for l in returned}),
            "revenue": _r(sum(l["sum"] for l in returned)),
            "watchlist_size": len(prev_ids),
        },
        "top_categories": _top(week, lambda l: f'{G_LABEL.get(l["_gender"], "")} {l["_category"] or "—"}'.strip(), 8),
        "top_brands": _top(week, lambda l: l["_brand"] or "—", 8),
        "arrivals": {
            "units": _r(sum(a["qty"] for a in arrivals_week)),
            "cost": _r(sum(a["qty"] * a["cost"] for a in arrivals_week)),
            "models": len({a["product_id"] for a in arrivals_week}),
        },
    }

    dynamics = []
    for k in range(DYNAMICS_WEEKS - 1, -1, -1):
        a, b = p.week_start - timedelta(days=7 * k), p.week_end - timedelta(days=7 * k)
        blk = sales_block(_in(upto, a, b))
        ly = sales_block(_in(upto, a - timedelta(days=364), b - timedelta(days=364)))
        arr = sum(x["qty"] * x["cost"] for x in ds.arrivals if a <= _d(x["day"]) <= b)
        dynamics.append(
            {
                "week_start": a.isoformat(),
                "revenue": blk["revenue"],
                "revenue_last_year": ly["revenue"],
                "checks": blk["checks"],
                "avg_discount_pct": blk["avg_discount_pct"],
                "markdown_units_pct": blk["markdown_units_pct"],
                "arrivals_cost": _r(arr),
            }
        )

    cur = _in(upto, p.cur_from, p.week_end)
    prev = _in(upto, p.prev_from, p.cur_from - timedelta(days=1))
    bought_cur = sum(a["qty"] * a["cost"] for a in ds.arrivals if p.cur_from <= _d(a["day"]) <= p.week_end)
    bought_prev = sum(a["qty"] * a["cost"] for a in ds.arrivals if p.prev_from <= _d(a["day"]) < p.cur_from)
    pr_cur, pr_prev = ds.profit.get("cur") or {}, ds.profit.get("prev") or {}
    cogs_cur, cogs_prev = pr_cur.get("cogs", 0.0), pr_prev.get("cogs", 0.0)
    stock_now = sum(s["stock"] * s["cost"] for s in ds.stock)
    age_buckets: dict[str, list[dict]] = defaultdict(list)
    for l in cur:
        c = ds.catalog.get(l["product_id"] or "") or {}
        arr = arrival_month(c.get("article"), c.get("name"), l["_day"])
        m = months_between(arr, l["_day"]) if arr else None
        b = "без даты" if m is None else "0-3 мес" if m <= 3 else "4-12 мес" if m <= 12 else "13-24 мес" if m <= 24 else "25+ мес"
        age_buckets[b].append(l)
    cur_rev = sum(l["sum"] for l in cur)
    overall = {
        "period_cur": {"from": p.cur_from.isoformat(), "to": p.week_end.isoformat()},
        "sales_cur": sales_block(cur),
        "sales_prev": sales_block(prev),
        "revenue_change_pct": _change_pct(sum(l["sum"] for l in cur), sum(l["sum"] for l in prev)),
        "revenue_all_channels_cur": _r(pr_cur.get("revenue")),
        "revenue_all_channels_prev": _r(pr_prev.get("revenue")),
        "gross_margin_pct": _pct(pr_cur.get("revenue", 0) - cogs_cur, pr_cur.get("revenue", 0)),
        "cogs_cur": _r(cogs_cur),
        "cogs_prev": _r(cogs_prev),
        "bought_cost_cur": _r(bought_cur),
        "bought_cost_prev": _r(bought_prev),
        "stock_cost_now": _r(stock_now),
        "stock_cost_history": {k: _r(v) for k, v in sorted(ds.stock_cost_on.items())},
        "months_of_stock": round(stock_now / (cogs_cur / 12), 1) if cogs_cur else None,
        "sales_by_age_at_sale": {
            k: {**sales_block(v), "revenue_share_pct": _pct(sum(l["sum"] for l in v), cur_rev)}
            for k, v in sorted(age_buckets.items())
        },
    }

    idx = stock_index(ds, run_day)
    segments = {}
    for s in ("A", "B", "C"):
        grp = [pr for pr in profiles if pr["segment"] == s]
        segments[s] = {
            "clients": len(grp),
            "rev_prev12": _r(sum(pr["rev_prev"] for pr in grp)),
            "rev_cur12": _r(sum(pr["rev_cur"] for pr in grp)),
        }
    a_status = {}
    for st, grp in _group([pr for pr in profiles if pr["segment"] == "A"], lambda pr: pr["status"]).items():
        a_status[st] = {
            "clients": len(grp),
            "rev_prev12": _r(sum(pr["rev_prev"] for pr in grp)),
            "rev_cur12": _r(sum(pr["rev_cur"] for pr in grp)),
        }
    watch = [pr for pr in profiles if pr["segment"] == "A" and pr["status"] in WATCH_STATUSES]
    order = {s: i for i, s in enumerate(WATCH_STATUSES)}
    watch.sort(key=lambda pr: (order[pr["status"]], -pr["rev24"]))
    watchlist = []
    for pr in watch:
        watchlist.append(
            {
                "id": pr["id"],
                "name": pr["name"],
                "phone": pr["phone"],
                "status": pr["status"],
                "last": pr["last"].isoformat(),
                "days_since": pr["days_since"],
                "median_gap": _r(pr["median_gap"]),
                "rev_prev12": _r(pr["rev_prev"]),
                "rev_cur12": _r(pr["rev_cur"]),
                "visits": pr["visits"],
                "gender": G_LABEL.get(pr["gender"] or "", ""),
                "brands": [b for b, _ in pr["brands"].most_common(3)],
                "categories": [c for c, _ in pr["cats"].most_common(4)],
                "sizes": "; ".join(f"{c}: {s}" for (_, c), s in pr["sizes"].items()),
                "avg_discount_pct": _r(pr["avg_discount"]),
                "markdown_share_pct": _r(pr["markdown_share"]),
                "picks": picks_for(pr, idx, run_day),
            }
        )
    clients = {
        "named_clients_24m": len(profiles),
        "segments": segments,
        "a_status": a_status,
        "watchlist": {
            "clients": len(watchlist),
            "by_status": dict(Counter(w["status"] for w in watchlist)),
            "rev_prev12": _r(sum(w["rev_prev12"] for w in watchlist)),
            "rev_cur12": _r(sum(w["rev_cur12"] for w in watchlist)),
            "picks": sum(len(w["picks"]) for w in watchlist),
            "picks_old": sum(1 for w in watchlist for x in w["picks"] if x["old"]),
        },
    }

    metrics = {
        "run_day": run_day.isoformat(),
        "week": week_section,
        "dynamics": dynamics,
        "overall": overall,
        "clients": clients,
        "assortment": assortment_section(ds, upto, run_day),
        "staff_feedback": staff_feedback or {},
    }
    metrics["suggestions"] = rule_suggestions(metrics)
    return metrics, watchlist


def _fmt_mln(x: float | None) -> str:
    return f"{(x or 0) / 1e6:.1f} млн ₽"


def rule_suggestions(m: dict) -> list[str]:
    """Детерминированные подсказки — основа для текста модели и запасной вариант без неё."""
    out: list[str] = []
    o, w, cl, asm = m["overall"], m["week"], m["clients"], m["assortment"]
    if o["cogs_cur"] and o["bought_cost_cur"] > o["cogs_cur"] * 1.05:
        out.append(
            f"Закупка за 12 мес ({_fmt_mln(o['bought_cost_cur'])}) выше себестоимости продаж ({_fmt_mln(o['cogs_cur'])}); "
            f"запас — {o['months_of_stock']} мес продаж. Следующий заказ планировать от продаж, а не от прошлого заказа."
        )
    wl = cl["watchlist"]
    if wl["clients"]:
        out.append(
            f"{wl['clients']} клиентов A на контроле (было {_fmt_mln(wl['rev_prev12'])} за прошлые 12 мес, стало {_fmt_mln(wl['rev_cur12'])}). "
            "Раздать продавцам список на обзвон с подборкой."
        )
    ret = w["returned_from_prev_watchlist"]
    if ret["watchlist_size"]:
        out.append(f"Из прошлого списка вернулись {ret['clients']} из {ret['watchlist_size']} на {_fmt_mln(ret['revenue'])}.")
    if asm["dead"]["models"]:
        out.append(
            f"{asm['dead']['models']} моделей продали ≤20% за 180 дней, на складе {_fmt_mln(asm['dead']['stock_cost'])} — "
            "в личные подборки клиентам с нужным размером, не в публичную распродажу."
        )
    if asm["reorder_candidates"]:
        names = ", ".join(f"{r['brand']} {r['model']}" for r in asm["reorder_candidates"][:3])
        out.append(f"{len(asm['reorder_candidates'])} свежих моделей распроданы на ≥60% с выбитыми размерами — проверить дозаказ: {names}.")
    adds = [f"{r['gender']} {r['category']} {r['size']}" for r in asm["size_curve"] if r["verdict"] == "добавить"][:6]
    cuts = [f"{r['gender']} {r['category']} {r['size']}" for r in asm["size_curve"] if r["verdict"] == "сократить"][:6]
    if adds:
        out.append("Размеры добавить в заказ: " + "; ".join(adds) + ".")
    if cuts:
        out.append("Размеры сократить: " + "; ".join(cuts) + ".")
    weak = [b["brand"] for b in asm["brands"] if (b["revenue_per_rub_bought"] or 0) < 0.8 and (b["st180_pct"] or 100) < 35]
    if weak:
        out.append("Слабая отдача на рубль закупки: " + ", ".join(weak[:6]) + " — сократить или пересобрать выбор моделей.")
    fb = m.get("staff_feedback") or {}
    if fb.get("messages_week", 0) < 5:
        out.append(
            f"В «Спрос» за неделю {fb.get('messages_week', 0)} сообщений — упущенный спрос почти не фиксируется."
        )
    sw = w["sales"]
    if sw["markdown_units_pct"] and sw["markdown_units_pct"] > 45:
        out.append(f"На неделе {sw['markdown_units_pct']}% штук ушло с уценкой >20% — проверить, кому и почему.")
    return out
