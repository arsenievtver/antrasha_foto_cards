#!/usr/bin/env python3
"""Слить recovery Cursor + Cloud в scripts/procurement-recovery/merged/."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

OUT = Path(__file__).resolve().parent / "merged"
CUR = Path.home() / "Downloads/antrasha-procurement-recovery-2026-10-11"
CLD = Path.home() / "Downloads/Резерв Антраша/1_PWA_из_базы_дашборда"


def norm_cursor(name: str) -> list[dict]:
    p = CUR / name
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(d, dict) and "items" in d:
        return d["items"]
    return d if isinstance(d, list) else []


def norm_cloud(name: str) -> list[dict]:
    p = CLD / name
    if not p.exists():
        return []
    best: dict[str, dict] = {}
    for row in json.loads(p.read_text(encoding="utf-8")):
        pld = row.get("payload") or row
        rid = pld.get("id") or row.get("external_id")
        if not rid:
            continue
        fa = row.get("fetched_at") or pld.get("updated_at") or pld.get("created_at") or ""
        if rid not in best or str(fa) > str(best[rid]["_fa"]):
            best[rid] = {**pld, "_fa": fa}
    for v in best.values():
        v.pop("_fa", None)
    return list(best.values())


def merge_entity(cursor_file: str, cloud_file: str) -> list[dict]:
    c = {x["id"]: x for x in norm_cursor(cursor_file)}
    d = {x["id"]: x for x in norm_cloud(cloud_file)}
    out: list[dict] = []
    for i in set(c) | set(d):
        if i in c and i in d:
            cu, du = c[i], d[i]
            u_c = cu.get("updated_at") or cu.get("created_at") or ""
            u_d = du.get("updated_at") or du.get("created_at") or du.get("paid_on") or ""
            out.append(du if str(u_d) >= str(u_c) else cu)
        elif i in d:
            out.append(d[i])
        else:
            out.append(c[i])
    return out


def main() -> None:
    pairs = [
        ("seasons.json", "season.json"),
        ("brands.json", "brand.json"),
        ("categories.json", "category.json"),
        ("fx_rates.json", "fx_rate.json"),
        ("orders.json", "order.json"),
        ("payments.json", "payment.json"),
        ("shipments.json", "shipment.json"),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    totals: dict[str, list] = {}
    for cf, df in pairs:
        key = cf.replace(".json", "")
        totals[key] = merge_entity(cf, df)
        (OUT / cf).write_text(
            json.dumps(totals[key], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    pay = sum(Decimal(str(p["amount_eur"])) for p in totals["payments"])
    ord_eur = sum(Decimal(str(o["amount_eur"])) for o in totals["orders"])
    meta = {
        "sources": [str(CUR), str(CLD)],
        "counts": {k: len(v) for k, v in totals.items()},
        "orders_eur": str(ord_eur),
        "payments_eur": str(pay),
    }
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print("written", OUT)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
