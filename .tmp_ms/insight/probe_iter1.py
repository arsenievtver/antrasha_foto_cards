"""Итерация 1: клиенты (концентрация, отток) и склад (возраст, категории)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date

from ms_mcp import HERE, MsMcp

PLACEHOLDER = re.compile(r"отказал|розничн|покупател|аноним|без имени|^-$|^\.$|клиент$", re.I)
ARRIVAL = re.compile(r"/(\d{2})\.(\d{2})(?:\s|$)")
TODAY = date(2026, 10, 27)

m = MsMcp()
out: dict = {}


def customers(date_from: str, date_to: str) -> dict[str, dict]:
    rows = m.call_all("report_profit_bycounterparty", {"momentFrom": date_from, "momentTo": date_to})
    return {r["counterpartyId"]: r for r in rows}


cur = customers("2025-10-01 00:00:00", "2026-09-30")
prev = customers("2024-10-01 00:00:00", "2025-09-30")


def summarize(rows: dict[str, dict]) -> dict:
    named = {k: r for k, r in rows.items() if not PLACEHOLDER.search(r["name"] or "")}
    anon = {k: r for k, r in rows.items() if k not in named}
    total = sum(r["sellSum"] - r["returnSum"] for r in rows.values())
    named_sum = sum(r["sellSum"] - r["returnSum"] for r in named.values())
    ranked = sorted((r["sellSum"] - r["returnSum"] for r in named.values()), reverse=True)
    n = len(ranked)

    def top_share(frac: float) -> float:
        k = max(1, round(n * frac))
        return round(sum(ranked[:k]) / named_sum * 100, 1) if named_sum else 0

    buckets = defaultdict(lambda: [0, 0.0])
    for r in named.values():
        c = r["salesCount"]
        b = "1" if c == 1 else "2" if c == 2 else "3-5" if c <= 5 else "6+"
        buckets[b][0] += 1
        buckets[b][1] += r["sellSum"] - r["returnSum"]
    return {
        "revenue_net": round(total),
        "anon_names": sorted({r["name"] for r in anon.values()}),
        "anon_revenue_share_pct": round((total - named_sum) / total * 100, 1) if total else 0,
        "named_customers": n,
        "top10pct_share_of_named_pct": top_share(0.10),
        "top20pct_share_of_named_pct": top_share(0.20),
        "by_purchase_count": {k: {"customers": v[0], "revenue": round(v[1])} for k, v in sorted(buckets.items())},
    }


out["customers_cur_12m"] = summarize(cur)
out["customers_prev_12m"] = summarize(prev)

prev_named = {k: r for k, r in prev.items() if not PLACEHOLDER.search(r["name"] or "")}
cur_named = {k for k, r in cur.items() if not PLACEHOLDER.search(r["name"] or "")}
prev_ranked = sorted(prev_named.values(), key=lambda r: r["sellSum"] - r["returnSum"], reverse=True)
top_prev = prev_ranked[: max(1, len(prev_ranked) // 5)]
lost_top = [r for r in top_prev if r["counterpartyId"] not in cur_named]
out["retention"] = {
    "prev_named": len(prev_named),
    "returned_in_cur": sum(1 for k in prev_named if k in cur_named),
    "top20pct_prev": len(top_prev),
    "top20pct_prev_revenue": round(sum(r["sellSum"] - r["returnSum"] for r in top_prev)),
    "top20pct_lost": len(lost_top),
    "top20pct_lost_prev_revenue": round(sum(r["sellSum"] - r["returnSum"] for r in lost_top)),
    "new_in_cur": sum(1 for k in cur_named if k not in prev_named),
}

folders = m.call_all("productfolder_list", {"fields": ["name", "pathName"]}, page=100)
stock_rows = []
for f in folders:
    rows = m.call_all(
        "report_stock_all",
        {"stockMode": "positiveOnly", "groupBy": "product", "productFolderId": f["id"], "withSubFolders": False},
    )
    path = "/".join(p for p in [f.get("pathName"), f["name"]] if p)
    for r in rows:
        r["folder"] = path
        stock_rows.append(r)


def age_bucket(article: str | None, name: str | None) -> str:
    mm = ARRIVAL.search(f"{article or ''} ") or ARRIVAL.search(f"{name or ''} ")
    if not mm:
        return "без даты"
    month, yy = int(mm.group(1)), int(mm.group(2))
    if not 1 <= month <= 12:
        return "без даты"
    months = (TODAY.year - (2000 + yy)) * 12 + TODAY.month - month
    if months < 0:
        return "без даты"
    if months <= 6:
        return "0-6 мес"
    if months <= 12:
        return "7-12 мес"
    if months <= 24:
        return "13-24 мес"
    return "25+ мес"


def agg(key_fn) -> dict:
    acc = defaultdict(lambda: {"models": 0, "units": 0, "cost": 0.0, "retail": 0.0})
    for r in stock_rows:
        a = acc[key_fn(r)]
        a["models"] += 1
        a["units"] += r["stock"]
        a["cost"] += r["stock"] * (r.get("price") or 0)
        a["retail"] += r["stock"] * (r.get("salePrice") or 0)
    return {
        k: {**v, "cost": round(v["cost"]), "retail": round(v["retail"])}
        for k, v in sorted(acc.items(), key=lambda kv: -kv[1]["cost"])
    }


out["stock_total"] = agg(lambda r: "всё")
out["stock_by_age"] = agg(lambda r: age_bucket(r.get("article"), r.get("name")))
out["stock_by_top_folder"] = agg(lambda r: r["folder"].split("/")[0])
out["stock_by_folder"] = agg(lambda r: r["folder"])
out["stock_by_folder_age"] = agg(lambda r: f'{r["folder"].split("/")[0]} | {age_bucket(r.get("article"), r.get("name"))}')

(HERE / "iter1_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "stock_by_folder"}, ensure_ascii=False, indent=1))
