# -*- coding: utf-8 -*-
"""Build buyer comments + ascending size sales charts per category."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

RAW = Path(
    "/Users/alekseiarsenev/WebstormProjects/antrasha_tinder/.tmp_ms/raw"
)
OUT = Path(
    "/Users/alekseiarsenev/WebstormProjects/antrasha_tinder/"
    ".tmp_ms/procurement_comments_vl2027_with_size_charts.json"
)

SEASON_TAG_RE = re.compile(r"(ВЛ|ОЗ)\s*20?(\d{2})", re.I)
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
    "бежевый",
    "хаки",
    "молочный",
    "кремовый",
    "песочный",
    "оливковый",
    "терракотовый",
    "графит",
    "белый",
    "чёрный",
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


def parse_month_year(src: str):
    m = DATE_RE.search(src or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def is_fresh_vl26(name: str, article: str) -> bool:
    sm = SEASON_TAG_RE.search(name or "")
    if not sm:
        return False
    season = sm.group(1).upper()
    yy = int(sm.group(2))
    if not (season == "ВЛ" and yy == 26):
        return False
    dt = parse_month_year(article or "")
    if not dt:
        return False
    return dt[0] in (2, 3, 4, 5, 6, 7, 8)


def is_size_token(token: str) -> bool:
    t = (token or "").strip()
    if not t:
        return False
    if t.lower() in COLOR_WORDS:
        return False
    if SEASON_TAG_RE.fullmatch(t):
        return False
    # reject season phrases / nested-paren debris like "осень-зима(2016"
    if re.search(r"весна|лето|осень|зима|притален|пуховик", t, re.I):
        return False
    if t.upper() in LETTER_ORDER:
        return True
    # numeric sizes / jeans like 42, 42/34, 36/34, 46/48
    return bool(re.fullmatch(r"\d{1,3}(?:/\d{1,3})?", t))


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
    """Size = last size-like comma token inside (...); skip color/season tokens."""
    for m in reversed(list(PAREN_RE.finditer(name or ""))):
        inner = m.group(1)
        parts = [p.strip() for p in inner.split(",") if p.strip()]
        for token in reversed(parts):
            if is_size_token(token):
                return token
    return None


def load_raw(key: str, kind: str) -> dict:
    path = RAW / f"{key}_{kind}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def stock_by_size(items: list[dict]) -> dict[str, dict]:
    by = defaultdict(lambda: {"fresh": 0, "old": 0, "total": 0})
    for it in items:
        if it.get("type") != "variant":
            continue
        name = it.get("name") or ""
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
        article = it.get("article") or it.get("code") or ""
        if is_fresh_vl26(name, article):
            by[size]["fresh"] += qty
        else:
            by[size]["old"] += qty
        by[size]["total"] += qty
    return dict(by)


def sales_by_size(items: list[dict]) -> dict[str, int]:
    by = defaultdict(int)
    for it in items:
        name = it.get("name") or ""
        size = extract_size(name)
        if not size:
            continue
        qty = int(it.get("sellQuantity") or 0)
        ret = int(it.get("returnQuantity") or 0)
        net = qty - ret
        if net > 0:
            by[size] += net
    return dict(by)


def make_comment(by_size: dict[str, dict]) -> tuple[str, list[str], list[str]]:
    sizes = [(s, v) for s, v in by_size.items() if v["total"] > 0]
    total = sum(v["total"] for _, v in sizes)
    fresh = sum(v["fresh"] for _, v in sizes)
    old = sum(v["old"] for _, v in sizes)

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
        f"Остатки на июль: всего {total} шт; ({fresh};{old}) {fresh} шт - ВЛ2026; "
        f"{old} шт - старые. "
        f"Усилить: {reinforce_txt}. "
        + (
            f"Ослабить: {', '.join(fmt(s) for s in weaken)}."
            if weaken
            else "Ослабить: нет явных."
        )
    )
    return comment, reinforce, weaken


def ascending_chart(sales: dict[str, int]) -> dict:
    labels = sorted(sales.keys(), key=size_sort_key)
    return {
        "period": {"from": "2026-03-01", "to": "2026-07-29"},
        "axis_x": "size_asc",
        "axis_y": "sellQuantity_pcs",
        "labels": labels,
        "sellQuantity": [sales[s] for s in labels],
    }


def main() -> None:
    out_cats = []
    for cat in CATEGORIES:
        stock = load_raw(cat["key"], "stock")
        sales = load_raw(cat["key"], "sales")
        by_size = stock_by_size(stock["items"])
        sold = sales_by_size(sales["items"])
        comment, reinforce, weaken = make_comment(by_size)
        chart = ascending_chart(sold)
        out_cats.append(
            {
                "key": cat["key"],
                "name": cat["name"],
                "gender": cat["gender"],
                "moy_sklad_id": cat["moy_sklad_id"],
                "comment": comment,
                "reinforce_sizes": reinforce,
                "weaken_sizes": weaken,
                "stock_totals": {
                    "total": sum(v["total"] for v in by_size.values()),
                    "fresh_vl26": sum(v["fresh"] for v in by_size.values()),
                    "old": sum(v["old"] for v in by_size.values()),
                },
                "size_sales_chart": chart,
            }
        )

    payload = {
        "meta": {
            "as_of": "29.07.2026",
            "sales_period": {"from": "2026-03-01", "to": "2026-07-29"},
            "comment_format": (
                "Остатки на июль: всего N шт; (F;O) F шт - ВЛ2026; O шт - старые. "
                "Усилить: size (F;O)... Ослабить: size (F;O)..."
            ),
            "chart_rule": (
                "per category; X = sizes ascending (small→large); "
                "Y = sold pcs Mar–now"
            ),
            "fresh_definition": "ВЛ2026 + month in article Feb–Aug",
            "raw_dir": str(RAW),
        },
        "categories": out_cats,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT)
    print("categories", len(out_cats))
    for key in ("men_pants", "women_pants"):
        c = next(x for x in out_cats if x["key"] == key)
        print("\n===", c["name"], "===")
        print(c["comment"])
        ch = c["size_sales_chart"]
        pairs = list(zip(ch["labels"], ch["sellQuantity"]))
        print("chart (size→qty):", ", ".join(f"{s}:{q}" for s, q in pairs))


if __name__ == "__main__":
    main()
