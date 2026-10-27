"""Прогон backend weekly_insight.compute на локальной выгрузке (для сверки с итерациями 2–3)."""
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.weekly_insight.compute import build_report  # noqa: E402
from app.services.weekly_insight.fetch import Dataset  # noqa: E402

D = Path(__file__).parent / "data"
catalog = json.load(open(D / "catalog.json"))
arr_raw = json.load(open(D / "arrivals.json"))
stock_raw = json.load(open(D / "stock_variants.json"))
sales_raw = json.load(open(D / "sales_lines.json"))

name_to_key = {}
for a in arr_raw:
    name_to_key.setdefault(a["variant_name"], a["variant_id"])
for s in stock_raw:
    name_to_key.setdefault(s["name"], s["id"])
by_base = {}
for pid, c in catalog.items():
    by_base.setdefault(c["name"], pid)
key_to_pid = {s["id"]: s["product_id"] for s in stock_raw if s["product_id"]}
for l in sales_raw:
    if l["product_id"]:
        key_to_pid.setdefault(name_to_key.get(l["variant_name"]), l["product_id"])

ds = Dataset(catalog=catalog)
ds.sales = [
    {
        "check_id": l["check_id"], "day": l["moment"][:10], "agent_id": l["agent_id"], "agent_name": l["agent"],
        "agent_phone": None, "product_id": l["product_id"], "variant_key": name_to_key.get(l["variant_name"], l["variant_name"]),
        "variant_name": l["variant_name"], "size": l["size"], "qty": l["qty"], "list_price": l["list_price"],
        "discount_pct": l["discount_pct"], "sum": l["sum"],
    }
    for l in sales_raw
]
ds.arrivals = [
    {
        "day": a["moment"][:10], "variant_key": a["variant_id"], "variant_name": a["variant_name"],
        "product_id": key_to_pid.get(a["variant_id"]) or by_base.get(a["base_name"]), "size": a["size"],
        "qty": a["qty"], "cost": a["cost"],
    }
    for a in arr_raw
]
ds.stock = [
    {"variant_key": s["id"], "name": s["name"], "product_id": s["product_id"], "size": s["size"], "stock": s["stock"], "cost": s["cost"], "sale_price": s["sale_price"]}
    for s in stock_raw
]
ds.profit = {"cur": {"cogs": 16_700_000, "revenue": 40_000_000}, "prev": {"cogs": 19_100_000, "revenue": 44_600_000}}

t = time.time()
metrics, watch = build_report(ds, date(2026, 10, 27), prev_watchlist_ids={w for w in []}, staff_feedback={"messages_week": 1})
print("sec", round(time.time() - t, 2))
out = Path(__file__).parent / "iter4_weekly_result.json"
out.write_text(json.dumps({"metrics": metrics, "watch_n": len(watch), "watch0": watch[:1]}, ensure_ascii=False, indent=1, default=str))
m = metrics
print(json.dumps({k: m["week"][k] for k in ("period", "sales", "prev_week", "same_week_last_year", "buyers_named", "buyers_new", "buyers_a", "arrivals")}, ensure_ascii=False))
print("overall", json.dumps({k: v for k, v in m["overall"].items() if k != "sales_by_age_at_sale"}, ensure_ascii=False))
print("age", json.dumps(m["overall"]["sales_by_age_at_sale"], ensure_ascii=False))
print("clients", json.dumps(m["clients"], ensure_ascii=False))
print("seasons", json.dumps(m["assortment"]["seasons"], ensure_ascii=False))
print("depth", m["assortment"]["depth"], "dead", m["assortment"]["dead"]["models"], m["assortment"]["dead"]["stock_cost"], "reorder", len(m["assortment"]["reorder_candidates"]))
print("dyn", [(d["week_start"], d["revenue"], d["revenue_last_year"]) for d in m["dynamics"]])
print("\n".join(m["suggestions"]))
print(json.dumps(watch[:1], ensure_ascii=False, default=str))
