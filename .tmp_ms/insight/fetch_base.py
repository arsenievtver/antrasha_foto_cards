"""Выгрузка базовых таблиц из МойСклад в .tmp_ms/insight/data/*.json.

catalog.json      — модели: артикул, группа, пол, категория, бренд
sales_lines.json  — строки чеков: дата, клиент, модель, размер, цена по прайсу, скидка, сумма
stock_variants.json — текущий остаток по размерам с себестоимостью
"""

from __future__ import annotations

import json
import sys

from ms_common import base_name, category_of, gender_of, size_of
from ms_mcp import HERE, MsMcp

DATA = HERE / "data"
DATA.mkdir(exist_ok=True)

DATE_FROM = sys.argv[1] if len(sys.argv) > 1 else "2024-07-01"
DATE_TO = sys.argv[2] if len(sys.argv) > 2 else "2026-10-26"

SKIP_TOP = {"Сертификат", "Сертификаты"}

m = MsMcp()

products = m.call_all(
    "product_list",
    {"archived": True, "expand": "supplier", "fields": ["name", "article", "pathName", "supplier"]},
    page=100,
)
catalog = {}
for p in products:
    path = p.get("pathName") or ""
    sup = p.get("supplier") or {}
    catalog[p["id"]] = {
        "name": p.get("name"),
        "article": p.get("article"),
        "path": path,
        "top": path.split("/")[0] if path else "",
        "gender": gender_of(path),
        "category": category_of(path),
        "brand": (sup.get("name") or "").strip() or None,
    }
by_name = {}
for pid, c in catalog.items():
    by_name.setdefault((c["name"] or "").strip(), pid)
(DATA / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False))
print("catalog", len(catalog), file=sys.stderr)


def resolve(ass: dict) -> str | None:
    if ass.get("id") in catalog:
        return ass["id"]
    return by_name.get(base_name(ass.get("name") or ""))


checks = m.call_all(
    "retaildemand_list",
    {
        "momentFrom": DATE_FROM,
        "momentTo": DATE_TO,
        "expand": "positions.assortment",
        "includeTotals": False,
        "sortBy": "moment",
        "sortOrder": "asc",
    },
    page=100,
)
lines = []
unresolved = 0
for ch in checks:
    if not ch.get("applicable", True):
        continue
    for pos in ch.get("positions") or []:
        ass = pos.get("assortment") or {}
        pid = resolve(ass)
        if pid is None:
            unresolved += 1
        c = catalog.get(pid) or {}
        if c.get("top") in SKIP_TOP:
            continue
        qty = pos.get("quantity") or 0
        list_price = (pos.get("price") or 0) / 100
        disc = pos.get("discount") or 0
        lines.append(
            {
                "check_id": ch["id"],
                "moment": ch["moment"],
                "agent_id": ch.get("agentId"),
                "agent": ch.get("agentName"),
                "product_id": pid,
                "variant_name": ass.get("name"),
                "size": size_of(ass.get("name"), ass.get("characteristics")),
                "qty": qty,
                "list_price": list_price,
                "discount_pct": disc,
                "sum": round(qty * list_price * (1 - disc / 100), 2),
            }
        )
(DATA / "sales_lines.json").write_text(json.dumps(lines, ensure_ascii=False))
print("checks", len(checks), "lines", len(lines), "unresolved", unresolved, file=sys.stderr)

stock = m.call_all("report_stock_all", {"stockMode": "positiveOnly", "groupBy": "variant"})
stock_rows = []
for r in stock:
    pid = catalog.get(r["id"]) and r["id"] or by_name.get(base_name(r.get("name") or ""))
    stock_rows.append(
        {
            "id": r["id"],
            "name": r.get("name"),
            "product_id": pid,
            "size": size_of(r.get("name"), None),
            "stock": r.get("stock"),
            "cost": r.get("price"),
            "sale_price": r.get("salePrice"),
        }
    )
(DATA / "stock_variants.json").write_text(json.dumps(stock_rows, ensure_ascii=False))
print("stock variants", len(stock_rows), "unresolved", sum(1 for s in stock_rows if not s["product_id"]), file=sys.stderr)
