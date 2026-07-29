# -*- coding: utf-8 -*-
"""Rebuild VL2027 order guidance: SS-only stock, VL25+VL26 table/chart, order EUR."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

RAW = Path(__file__).resolve().parent / "raw"
OUT_TMP = Path(__file__).resolve().parent / "procurement_comments_vl2027_with_size_charts.json"
OUT_BACKEND = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "app"
    / "data"
    / "order_guidance_vl2027.json"
)

SEASON_TAG_RE = re.compile(r"(ВЛ|ОЗ)\s*20?(\d{2})", re.I)
SS_TEXT_RE = re.compile(r"весна[\s\-–]*лето", re.I)
AW_TEXT_RE = re.compile(r"осень[\s\-–]*зима", re.I)
PAREN_RE = re.compile(r"\(([^)]+)\)")
DATE_RE = re.compile(r"(?:^|/)(\d{2})\.(\d{2})(?:\b|$)")
LETTER_ORDER = {
    "XXS": 0,
    "XS": 1,
    "S": 2,
    "M": 3,
    "L": 4,
    "XL": 5,
    "XXL": 6,
    "XXXL": 7,
}
COLOR_WORDS = {
    "бежевый",
    "серый",
    "черный",
    "чёрный",
    "белый",
    "синий",
    "голубой",
    "красный",
    "зеленый",
    "зелёный",
    "коричневый",
    "бордовый",
    "розовый",
    "желтый",
    "жёлтый",
    "оранжевый",
    "фиолетовый",
    "хаки",
    "молочный",
    "кремовый",
    "песочный",
    "оливковый",
    "терракотовый",
    "графит",
}

# Scenario B ~60k EUR from Excel sheet 5. Кат_B_60k
# Pants = jeans + shorts; dresses = dresses + skirts
ORDER_AMOUNT_EUR = {
    "men_outerwear": 2480.8,
    "men_jackets": 3581.6,
    "men_tshirts": 5629.5,
    "men_pants": 11230.5,  # 9622.9 + 1607.6
    "men_knitwear": 1708.6,
    "men_shirts": 2897.6,
    "men_suits": 2418.2,
    "men_shoes": 1288.8,
    "women_outerwear": 1038.7,
    "women_jackets": 3353.1,
    "women_tshirts": 3125.1,
    "women_blouses": 2596.9,
    "women_knitwear": 2746.7,
    "women_pants": 7951.1,  # 7429.1 + 522.0
    "women_dresses": 3937.5,  # 2825.1 + 1112.4
    "women_shoes": 519.9,
    "accessories": 1223.2,
}

CATEGORIES = [
    {
        "key": "men_outerwear",
        "gender": "men",
        "name": "Верхняя одежда муж",
        "moy_sklad_id": "0ebca617-f97a-11e9-0a80-0579004f6022",
    },
    {
        "key": "men_jackets",
        "gender": "men",
        "name": "Пиджаки, жакеты, бомбер муж",
        "moy_sklad_id": "009bd151-b37b-11e9-9ff4-3150003a1bb1",
    },
    {
        "key": "men_tshirts",
        "gender": "men",
        "name": "Футболки, поло муж",
        "moy_sklad_id": "46a5c5b7-5708-11e9-9ff4-315000d0798d",
    },
    {
        "key": "men_pants",
        "gender": "men",
        "name": "Брюки, джинсы, бриджи, шорты муж",
        "moy_sklad_id": "46b4f0d3-5708-11e9-9ff4-315000d079ad",
    },
    {
        "key": "men_knitwear",
        "gender": "men",
        "name": "Трикотаж муж",
        "moy_sklad_id": "7958c78e-9e44-11e9-9ff4-31500007d713",
    },
    {
        "key": "men_shirts",
        "gender": "men",
        "name": "Рубашки муж",
        "moy_sklad_id": "797d0e35-9e44-11e9-9ff4-31500007d733",
    },
    {
        "key": "men_suits",
        "gender": "men",
        "name": "Костюмы муж",
        "moy_sklad_id": "eec41100-9847-11eb-0a80-0616000ac009",
    },
    {
        "key": "men_shoes",
        "gender": "men",
        "name": "Обувь муж",
        "moy_sklad_id": "f8fae156-b37a-11e9-9ff4-3150003a11ec",
    },
    {
        "key": "women_outerwear",
        "gender": "women",
        "name": "Верхняя одежда жен",
        "moy_sklad_id": "0dea4445-f97a-11e9-0a80-0579004f5ecf",
    },
    {
        "key": "women_jackets",
        "gender": "women",
        "name": "Пиджаки, жакеты, бомбер жен",
        "moy_sklad_id": "79292943-9e44-11e9-9ff4-31500007d6f3",
    },
    {
        "key": "women_tshirts",
        "gender": "women",
        "name": "Футболки, поло жен",
        "moy_sklad_id": "f7b6946e-b37a-11e9-9ff4-3150003a0ff5",
    },
    {
        "key": "women_blouses",
        "gender": "women",
        "name": "Блузки, рубашки жен",
        "moy_sklad_id": "21e1d207-b53f-11e9-9ff4-31500015315b",
    },
    {
        "key": "women_knitwear",
        "gender": "women",
        "name": "Трикотаж жен",
        "moy_sklad_id": "cd27a401-d3a6-11e9-0a80-02690003e199",
    },
    {
        "key": "women_pants",
        "gender": "women",
        "name": "Брюки, джинсы, бриджи, шорты жен",
        "moy_sklad_id": "78fabba1-9e44-11e9-9ff4-31500007d6c1",
    },
    {
        "key": "women_dresses",
        "gender": "women",
        "name": "Платья, юбки жен",
        "moy_sklad_id": "26114fa1-a495-11e9-9ff4-3150000fa9a1",
    },
    {
        "key": "women_shoes",
        "gender": "women",
        "name": "Обувь жен",
        "moy_sklad_id": "79419e87-9e44-11e9-9ff4-31500007d6fe",
    },
    {
        "key": "accessories",
        "gender": "unisex",
        "name": "Аксессуары",
        "moy_sklad_id": "82adf299-8e8b-11e9-9ff4-31500007fc47",
    },
]

PERIOD_FROM = "2025-02-01"
PERIOD_TO = "2026-07-29"
AS_OF = "29.07.2026"


def is_size_token(token: str) -> bool:
    t = (token or "").strip()
    if not t:
        return False
    if t.lower() in COLOR_WORDS:
        return False
    if SEASON_TAG_RE.fullmatch(t):
        return False
    if re.search(r"весна|лето|осень|зима|притален|пуховик", t, re.I):
        return False
    if t.upper() in LETTER_ORDER:
        return True
    return bool(re.fullmatch(r"\d{1,3}(?:/\d{1,3})?|\d{2}-\d{2}|\d+(?:[.,]\d+)?", t))


def size_sort_key(size: str):
    s = size.strip()
    up = s.upper()
    if up in LETTER_ORDER:
        return (1, LETTER_ORDER[up], s)
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if nums:
        return (0, nums, s)
    return (2, [9999], s)


def extract_size(name: str) -> str | None:
    for m in reversed(list(PAREN_RE.finditer(name or ""))):
        parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
        for token in reversed(parts):
            if is_size_token(token):
                return token
    return None


def season_kind(name: str) -> str | None:
    """Return 'ss', 'aw', or None if unclassified."""
    n = name or ""
    if AW_TEXT_RE.search(n) or re.search(r"ОЗ\s*20?\d{2}", n, re.I):
        return "aw"
    if SS_TEXT_RE.search(n) or re.search(r"ВЛ\s*20?\d{2}", n, re.I):
        return "ss"
    return None


def vl_year(name: str) -> int | None:
    """Return 2-digit year for ВЛ season tag, else None."""
    m = SEASON_TAG_RE.search(name or "")
    if not m:
        return None
    if m.group(1).upper() != "ВЛ":
        return None
    return int(m.group(2))


def is_ss_item(name: str) -> bool:
    return season_kind(name) == "ss"


def is_vl26(name: str) -> bool:
    return vl_year(name) == 26


def is_vl25_or_26(name: str) -> bool:
    y = vl_year(name)
    return y in (25, 26)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pick_sales_path(key: str) -> Path:
    preferred = RAW / f"{key}_sales_feb2025.json"
    if preferred.is_file():
        return preferred
    return RAW / f"{key}_sales.json"


def stock_ss_by_size(items: list[dict]) -> dict[str, dict]:
    by = defaultdict(lambda: {"fresh": 0, "old": 0, "total": 0})
    for it in items:
        if it.get("type") not in (None, "variant", "product"):
            # keep variants; products without size skipped later
            pass
        name = it.get("name") or ""
        if not is_ss_item(name):
            continue
        size = extract_size(name)
        if not size:
            continue
        qty = int(
            it.get("quantity")
            if it.get("quantity") is not None
            else (it.get("stock") or 0)
        )
        if qty <= 0:
            continue
        if is_vl26(name):
            by[size]["fresh"] += qty
        else:
            by[size]["old"] += qty
        by[size]["total"] += qty
    # enforce identity
    for v in by.values():
        v["total"] = v["fresh"] + v["old"]
    return dict(by)


def stock_vl25_26_by_size(items: list[dict]) -> dict[str, int]:
    """Current stock pcs of ВЛ2025+ВЛ2026 only, by size."""
    by: dict[str, int] = defaultdict(int)
    for it in items:
        name = it.get("name") or ""
        if not is_vl25_or_26(name):
            continue
        size = extract_size(name)
        if not size:
            continue
        qty = int(
            it.get("quantity")
            if it.get("quantity") is not None
            else (it.get("stock") or 0)
        )
        if qty > 0:
            by[size] += qty
    return dict(by)


def metrics_table(
    by_size_ss: dict[str, dict],
    stock_vl25_26: dict[str, int],
    items_sales: list[dict],
):
    """Table columns:
    - sold_total: ВЛ2025+ВЛ2026 net sales
    - stock_total: all SS stock (same F+O as comment)
    - received_total: sold + stock of ВЛ2025+ВЛ2026 only
      (two-season intake; may be << stock_total when old SS tails remain)
    """
    sold = defaultdict(int)
    for it in items_sales:
        name = it.get("name") or ""
        if not is_vl25_or_26(name):
            continue
        size = extract_size(name)
        if not size:
            continue
        qty = int(it.get("sellQuantity") or 0)
        ret = int(it.get("returnQuantity") or 0)
        net = qty - ret
        if net > 0:
            sold[size] += net

    sizes = sorted(
        set(by_size_ss) | set(sold) | set(stock_vl25_26), key=size_sort_key
    )
    rows = []
    chart_labels = []
    chart_sold = []
    for size in sizes:
        s = sold[size]
        st_ss = int((by_size_ss.get(size) or {}).get("total") or 0)
        st_two = int(stock_vl25_26.get(size) or 0)
        if s <= 0 and st_ss <= 0 and st_two <= 0:
            continue
        rows.append(
            {
                "size": size,
                "received_total": s + st_two,
                "sold_total": s,
                "stock_total": st_ss,
            }
        )
        if s > 0:
            chart_labels.append(size)
            chart_sold.append(s)
    return rows, chart_labels, chart_sold


def make_comment(by_size: dict[str, dict]) -> tuple[str, list[str], list[str]]:
    sizes = [(s, v) for s, v in by_size.items() if v["total"] > 0]
    total = sum(v["total"] for _, v in sizes)
    fresh = sum(v["fresh"] for _, v in sizes)
    old = sum(v["old"] for _, v in sizes)
    assert total == fresh + old

    sizes_sorted = sorted(sizes, key=lambda x: (x[1]["fresh"], -x[1]["total"]))
    reinforce: list[str] = []
    for s, v in sizes_sorted:
        if v["fresh"] == 0:
            reinforce.append(s)
        if len(reinforce) >= 4:
            break
    if len(reinforce) < 4:
        for s, _v in sizes_sorted:
            if s in reinforce:
                continue
            reinforce.append(s)
            if len(reinforce) >= 4:
                break

    vals = sorted(v["total"] for _, v in sizes)
    median = vals[len(vals) // 2] if vals else 0
    weaken_cands = [
        (s, v)
        for s, v in sizes
        if v["fresh"] > 0
        and v["old"] >= v["fresh"]
        and v["total"] >= median
        and s not in reinforce
    ]
    weaken = [
        s
        for s, _ in sorted(
            weaken_cands, key=lambda x: (-x[1]["old"], -x[1]["total"])
        )[:3]
    ]

    def fmt(s: str) -> str:
        v = by_size[s]
        return f"{s} ({v['fresh']};{v['old']})"

    reinforce_txt = (
        ", ".join(fmt(s) for s in reinforce) if reinforce else "нет данных"
    )
    comment = (
        f"Остатки: {total} шт ({fresh};{old}) {fresh}-ВЛ2026; {old}-старые. "
        f"Усилить: {reinforce_txt}. "
        + (
            f"Ослабить: {', '.join(fmt(s) for s in weaken)}."
            if weaken
            else "Ослабить: нет явных."
        )
    )
    return comment, reinforce, weaken


def main() -> None:
    out_cats = []
    for cat in CATEGORIES:
        key = cat["key"]
        stock_path = RAW / f"{key}_stock.json"
        sales_path = pick_sales_path(key)
        if not stock_path.is_file():
            raise SystemExit(f"missing stock: {stock_path}")
        if not sales_path.is_file():
            raise SystemExit(f"missing sales: {sales_path}")

        stock = load_json(stock_path)
        sales = load_json(sales_path)
        by_size = stock_ss_by_size(stock.get("items") or [])
        stock_two = stock_vl25_26_by_size(stock.get("items") or [])
        comment, reinforce, weaken = make_comment(by_size)
        rows, labels, sold_qty = metrics_table(
            by_size, stock_two, sales.get("items") or []
        )
        fresh = sum(v["fresh"] for v in by_size.values())
        old = sum(v["old"] for v in by_size.values())
        total = fresh + old

        out_cats.append(
            {
                "key": key,
                "name": cat["name"],
                "gender": cat["gender"],
                "moy_sklad_id": cat["moy_sklad_id"],
                "order_amount_eur": ORDER_AMOUNT_EUR[key],
                "comment": comment,
                "reinforce_sizes": reinforce,
                "weaken_sizes": weaken,
                "stock_totals": {
                    "total": total,
                    "fresh_vl26": fresh,
                    "old": old,
                },
                "size_summary_rows": rows,
                "size_sales_chart": {
                    "period": {"from": PERIOD_FROM, "to": PERIOD_TO},
                    "axis_x": "size_asc",
                    "axis_y": "sellQuantity_pcs",
                    "seasons": ["ВЛ2026", "ВЛ2025"],
                    "labels": labels,
                    "sellQuantity": sold_qty,
                },
            }
        )

    payload = {
        "meta": {
            "as_of": AS_OF,
            "sales_period": {"from": PERIOD_FROM, "to": PERIOD_TO},
            "scenario": "B_60k",
            "comment_format": (
                "Остатки: N шт (F;O) F-ВЛ2026; O-старые. "
                "Усилить: size (F;O)... Ослабить: size (F;O)..."
            ),
            "stock_rule": "only spring-summer (ВЛ / весна-лето); exclude ОЗ / осень-зима",
            "fresh_definition": "ВЛ2026 within SS stock",
            "old_definition": "other SS seasons (ВЛ2025 and older SS)",
            "table_rule": (
                "sold_total = ВЛ2025+ВЛ2026 net sales; "
                "stock_total = all SS stock (same F+O as comment); "
                "received_total = sold_total + stock of ВЛ2025+ВЛ2026 only "
                "(two-season intake; may be less than stock_total if old SS tails)"
            ),
            "chart_rule": (
                "per category; X = sizes ascending; "
                "Y = sold pcs of ВЛ2025+ВЛ2026 for Feb 2025–now"
            ),
        },
        "categories": out_cats,
    }

    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    OUT_TMP.write_text(text, encoding="utf-8")
    OUT_BACKEND.parent.mkdir(parents=True, exist_ok=True)
    OUT_BACKEND.write_text(text, encoding="utf-8")
    print("saved", OUT_TMP)
    print("saved", OUT_BACKEND)
    print("categories", len(out_cats))
    for key in ("men_pants", "women_pants", "men_tshirts"):
        c = next(x for x in out_cats if x["key"] == key)
        st = c["stock_totals"]
        assert st["total"] == st["fresh_vl26"] + st["old"]
        for row in c["size_summary_rows"]:
            assert row["sold_total"] >= 0
            assert row["stock_total"] >= 0
            assert row["received_total"] >= row["sold_total"]
        print(
            f"\n=== {c['name']} €{c['order_amount_eur']} ===\n{c['comment']}\n"
            f"rows={len(c['size_summary_rows'])} chart={list(zip(c['size_sales_chart']['labels'], c['size_sales_chart']['sellQuantity']))[:8]}"
        )


if __name__ == "__main__":
    main()
