"""Оценка заказа ВЛ27: ВЛ2025 и ВЛ2026 на одну дату (25 октября года сезона), жакеты = лёгкая верхняя одежда."""
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
exec(open(Path(__file__).parent / "validate_weekly.py").read().split("t = time.time()")[0])
from app.services.weekly_insight.compute import CARD_DISCOUNT_MAX, _prepare_lines, variant_rows  # noqa: E402

TODAY = date(2026, 10, 27)
EUR = 105.0
lines = _prepare_lines(ds)
OUTER = {"Верхняя одежда", "Пиджаки, жакеты", "Пиджаки, жакеты, бомбер"}
CUT = {"ВЛ2025": date(2025, 10, 25), "ВЛ2026": date(2026, 10, 25)}

rows = [r for r in variant_rows(ds, lines, TODAY) if r["season"] in CUT and r["brand"] != "—"]
keys = {r["product_id"] for r in rows}
by_variant = defaultdict(list)
for l in lines:
    by_variant[l["variant_key"]].append(l)
# variant_rows не отдаёт ключ модификации — восстановим через приходы
vk_of = defaultdict(set)
for a in ds.arrivals:
    if a["product_id"] in keys:
        vk_of[a["product_id"]].add(a["variant_key"])


def cat(c):
    return "Жакеты+верхняя" if c in OUTER else c


def agg(items, season):
    cut = CUT[season]
    rec = sum(r["received"] for r in items)
    cost = sum(r["received"] * r["unit_cost"] for r in items)
    pids = {r["product_id"] for r in items}
    ls = [l for p in pids for vk in vk_of[p] for l in by_variant.get(vk, []) if l["_day"] <= cut]
    sold = sum(l["qty"] for l in ls)
    card = sum(l["qty"] for l in ls if l["discount_pct"] <= CARD_DISCOUNT_MAX)
    rev = sum(l["sum"] for l in ls)
    return cost, rec, sold / rec * 100 if rec else 0, card / rec * 100 if rec else 0, rev / cost if cost else 0


def line(name, items, season):
    cost, rec, st, card, rpr = agg(items, season)
    return f"  {name[:26]:26} {cost/EUR/1000:5.1f}т€ {rec:5.0f}шт  продано {st:4.0f}%  по карте {card:4.0f}%  ₽/₽ {rpr:4.2f}"


for season in CUT:
    srows = [r for r in rows if r["season"] == season]
    print(f"\n=== {season}, продажи по {CUT[season]}")
    print(line("ИТОГО", srows, season))
    g = defaultdict(list)
    for r in srows:
        g[r["brand"].split("(")[0].strip().upper()].append(r)
    for b, rs in sorted(g.items(), key=lambda kv: -sum(r["received"] * r["unit_cost"] for r in kv[1])):
        if sum(r["received"] * r["unit_cost"] for r in rs) > 100000:
            print(line(b, rs, season))
    for gender in ("M", "W"):
        g = defaultdict(list)
        for r in srows:
            if r["gender"] == gender:
                g[cat(r["category"])].append(r)
        print(f" -- категории {gender}")
        for c, rs in sorted(g.items(), key=lambda kv: -sum(r["received"] * r["unit_cost"] for r in kv[1])):
            if sum(r["received"] * r["unit_cost"] for r in rs) > 80000:
                print(line(c, rs, season))
