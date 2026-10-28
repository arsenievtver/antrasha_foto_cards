"""Итерация 5: глубина модели и провал октября (поздняя коллекция или волна клиентов A в сентябре)."""
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
exec(open(Path(__file__).parent / "validate_weekly.py").read().split("t = time.time()")[0])  # ds, catalog
from app.services.weekly_insight.compute import CARD_DISCOUNT_MAX, _prepare_lines, variant_rows  # noqa: E402
from app.services.weekly_insight.parse import season_of  # noqa: E402

TODAY = date(2026, 10, 27)
lines = _prepare_lines(ds)
out = {}

# ---------- сезон каждой модификации ----------
first_arr = {}
for a in ds.arrivals:
    if a["variant_key"] and a["qty"] > 0:
        d = date.fromisoformat(a["day"])
        first_arr[a["variant_key"]] = min(first_arr.get(a["variant_key"], d), d)
names = {a["variant_key"]: a["variant_name"] for a in ds.arrivals}
season_by_key = {k: season_of(names.get(k), d) for k, d in first_arr.items()}


def branded(pid):
    c = catalog.get(pid or "") or {}
    return bool(c.get("brand")) and c.get("top") not in ("Товар ТО", "Сертификат", "Сертификаты")


# ---------- 2. Поздняя коллекция: приход ОЗ на даты ----------
def cum_arrivals(season, upto):
    u = c = 0.0
    for a in ds.arrivals:
        if a["qty"] > 0 and season_by_key.get(a["variant_key"]) == season and date.fromisoformat(a["day"]) <= upto and branded(a["product_id"]):
            u += a["qty"]; c += a["qty"] * a["cost"]
    return round(u), round(c)


def cum_sold(season, upto):
    return round(sum(l["qty"] for l in lines if season_by_key.get(l["variant_key"]) == season and l["_day"] <= upto))


arr = {}
for y in (2025, 2026):
    s = f"ОЗ{y}"
    pts = {}
    for md in ("08-01", "08-15", "09-01", "09-15", "10-01", "10-15", "10-25"):
        d = date.fromisoformat(f"{y}-{md}")
        u, c = cum_arrivals(s, d)
        pts[md] = {"arrived_units": u, "arrived_cost": c, "on_hand_units": u - cum_sold(s, d)}
    pts["final"] = dict(zip(("arrived_units", "arrived_cost"), cum_arrivals(s, date(y + 1, 3, 1) if y == 2025 else TODAY)))
    arr[s] = pts
out["autumn_arrivals"] = arr


# ---------- выручка по периодам: новая коллекция / прочее, карта / уценка ----------
def blk(ls):
    rev = sum(l["sum"] for l in ls)
    listed = sum(l["qty"] * l["list_price"] for l in ls)
    return {
        "revenue": round(rev),
        "checks": len({l["check_id"] for l in ls}),
        "buyers": len({l["agent_id"] for l in ls if l["agent_id"]}),
        "disc_pct": round((listed - rev) / listed * 100, 1) if listed else None,
        "markdown_rev_pct": round(sum(l["sum"] for l in ls if l["discount_pct"] > CARD_DISCOUNT_MAX) / rev * 100, 1) if rev else None,
    }


def period(y, a, b):
    return [l for l in lines if date.fromisoformat(f"{y}-{a}") <= l["_day"] <= date.fromisoformat(f"{y}-{b}")]


PER = {"aug": ("08-01", "08-31"), "sep": ("09-01", "09-30"), "oct1_25": ("10-01", "10-25"), "sep_oct25": ("09-01", "10-25")}
months = {}
for y in (2024, 2025, 2026):
    for k, (a, b) in PER.items():
        if y == 2024 and k == "aug":
            continue
        ls = period(y, a, b)
        new = [l for l in ls if season_by_key.get(l["variant_key"]) == f"ОЗ{y}"]
        months[f"{y}_{k}"] = {**blk(ls), "new_collection": blk(new)}
out["periods"] = months


# ---------- волна клиентов A ----------
def segment_a(y):
    """A — верхние 20% по выручке за 12 мес до 1 августа (до самой волны)."""
    a, b = date(y - 1, 8, 1), date(y, 7, 31)
    rev = defaultdict(float)
    for l in lines:
        if a <= l["_day"] <= b and l["agent_id"]:
            rev[l["agent_id"]] += l["sum"]
    ranked = sorted(rev, key=lambda k: -rev[k])
    return set(ranked[: max(1, round(len(ranked) * 0.2))]), rev


wave = {}
for y in (2025, 2026):
    A, base = segment_a(y)
    sep = period(y, "09-01", "09-30")
    octo = period(y, "10-01", "10-25")
    bought_sep = {l["agent_id"] for l in sep if l["agent_id"] in A}
    bought_oct = {l["agent_id"] for l in octo if l["agent_id"] in A}
    aug = period(y, "08-01", "08-31")
    wave[y] = {
        "A_size": len(A),
        "A_base_rev_12m": round(sum(base[k] for k in A)),
        "A_rev": {
            "aug": round(sum(l["sum"] for l in aug if l["agent_id"] in A)),
            "sep": round(sum(l["sum"] for l in sep if l["agent_id"] in A)),
            "oct1_25": round(sum(l["sum"] for l in octo if l["agent_id"] in A)),
        },
        "nonA_rev": {
            "aug": round(sum(l["sum"] for l in aug if l["agent_id"] not in A)),
            "sep": round(sum(l["sum"] for l in sep if l["agent_id"] not in A)),
            "oct1_25": round(sum(l["sum"] for l in octo if l["agent_id"] not in A)),
        },
        "A_buyers": {"aug": len({l["agent_id"] for l in aug if l["agent_id"] in A}), "sep": len(bought_sep), "oct1_25": len(bought_oct)},
        "A_sep_and_oct": len(bought_sep & bought_oct),
        "A_sep_or_oct": len(bought_sep | bought_oct),
        "A_rev_per_sep_buyer_sep": round(sum(l["sum"] for l in sep if l["agent_id"] in A) / max(1, len(bought_sep))),
    }
out["a_wave"] = wave

# Кто в сентябре 2026 «сделал» рекорд: топ-покупатели и их прошлогодний ритм
A26, _ = segment_a(2026)
sep26 = period(2026, "09-01", "09-30")
by = defaultdict(float)
for l in sep26:
    by[l["agent_id"]] += l["sum"]
top = sorted(by.items(), key=lambda kv: -kv[1])[:15]
oct25 = {l["agent_id"] for l in period(2025, "10-01", "10-31")}
sep25 = {l["agent_id"] for l in period(2025, "09-01", "09-30")}
out["sep26_top_buyers"] = [
    {"rev_sep26": round(v), "is_A": k in A26, "bought_sep25": k in sep25, "bought_oct25": k in oct25,
     "bought_oct26": any(l["agent_id"] == k for l in period(2026, "10-01", "10-27"))}
    for k, v in top if k
]
out["sep26_top15_share_pct"] = round(sum(v for _, v in top) / sum(by.values()) * 100, 1)
sep25_by = defaultdict(float)
for l in period(2025, "09-01", "09-30"):
    sep25_by[l["agent_id"]] += l["sum"]
out["sep25_top15_share_pct"] = round(sum(v for _, v in sorted(sep25_by.items(), key=lambda kv: -kv[1])[:15]) / sum(sep25_by.values()) * 100, 1)

# ---------- 1. Глубина модели ----------
rows = [r for r in variant_rows(ds, lines, TODAY) if r["brand"] != "—" and r["season"] in ("ОЗ2024", "ВЛ2025", "ОЗ2025", "ВЛ2026") and r["age"] >= 180]
models = defaultdict(list)
for r in rows:
    models[r["product_id"]].append(r)


def bucket(n):
    return "1-2" if n <= 2 else "3-4" if n <= 4 else "5-6" if n <= 6 else "7-9" if n <= 9 else "10+"


dep = defaultdict(lambda: {"models": 0, "units": 0, "sold180": 0, "card180": 0, "sold_all": 0, "card_all": 0, "cost": 0.0, "rev": 0.0, "stock": 0, "fast_out": 0})
for pid, rs in models.items():
    n = sum(r["received"] for r in rs)
    d = dep[(rs[0]["category"] in ("Верхняя одежда",), bucket(n))]
    d["models"] += 1
    d["units"] += n
    d["sold180"] += sum(r["sold180"] for r in rs)
    d["card180"] += sum(r["card180"] for r in rs)
    d["sold_all"] += sum(r["sold"] for r in rs)
    d["card_all"] += sum(r["sold_card"] for r in rs)
    d["cost"] += sum(r["received"] * r["unit_cost"] for r in rs)
    d["rev"] += sum(r["revenue"] for r in rs)
    d["stock"] += sum(r["stock"] for r in rs)
dep_out = []
for (outer, b), d in sorted(dep.items()):
    dep_out.append({
        "outerwear": outer, "units_per_model": b, "models": d["models"], "units": round(d["units"]),
        "st180_pct": round(d["sold180"] / d["units"] * 100, 1), "st180_card_pct": round(d["card180"] / d["units"] * 100, 1),
        "st_to_date_pct": round(d["sold_all"] / d["units"] * 100, 1), "card_share_of_sold_pct": round(d["card_all"] / max(1, d["sold_all"]) * 100, 1),
        "rev_per_rub": round(d["rev"] / d["cost"], 2), "left_units_pct": round(d["stock"] / d["units"] * 100, 1),
    })
out["depth_by_units_per_model"] = dep_out

# Модели, распроданные целиком по карте за 60 дней — «могли бы продать ещё»
hot = 0; hot_units = 0; total_models = len(models)
for pid, rs in models.items():
    n = sum(r["received"] for r in rs)
    ok = all(r["sellout_day"] is not None and r["sellout_day"] <= 60 for r in rs) and sum(r["sold_card"] for r in rs) >= 0.8 * n
    if ok:
        hot += 1; hot_units += n
out["hot_models"] = {"models": hot, "of": total_models, "units": hot_units}

# Сколько штук в одной модели-размере
per_size = Counter(min(int(r["received"]), 3) for r in rows if r["size"])
out["units_per_model_size"] = {("3+" if k == 3 else str(k)): v for k, v in sorted(per_size.items())}

Path(__file__).with_name("iter5_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
print(json.dumps(out, ensure_ascii=False, indent=1, default=str))
