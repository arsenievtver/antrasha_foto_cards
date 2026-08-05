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
# Aligned with MoySklad folder split (июль 2026).
ORDER_AMOUNT_EUR = {
    "men_outerwear": 2480.8,
    "men_jackets": 3581.6,
    "men_tshirts": 5629.5,
    "men_pants": 9622.9,
    "men_shorts": 1607.6,
    "men_knitwear": 1708.6,
    "men_shirts": 2897.6,
    "men_suits": 2418.2,
    "men_shoes": 1288.8,
    "women_outerwear": 1038.7,
    "women_jackets": 3353.1,
    "women_tshirts": 3125.1,
    "women_blouses": 2596.9,
    "women_knitwear": 2746.7,
    "women_pants": 7429.1,
    "women_shorts": 522.0,
    "women_dresses": 2825.1,
    "women_skirts": 1112.4,
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
        "name": "Брюки, джинсы муж",
        "moy_sklad_id": "46b4f0d3-5708-11e9-9ff4-315000d079ad",
    },
    {
        "key": "men_shorts",
        "gender": "men",
        "name": "Бриджи, шорты муж",
        "moy_sklad_id": "55edd126-8bff-11f1-0a80-142f000aee50",
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
        "name": "Брюки, джинсы жен",
        "moy_sklad_id": "78fabba1-9e44-11e9-9ff4-31500007d6c1",
    },
    {
        "key": "women_shorts",
        "gender": "women",
        "name": "Бриджи, шорты жен",
        "moy_sklad_id": "4643b20e-8bfa-11f1-0a80-18830009f9ac",
    },
    {
        "key": "women_dresses",
        "gender": "women",
        "name": "Платья жен",
        "moy_sklad_id": "65dca14b-8bfd-11f1-0a80-0fbf000a6721",
    },
    {
        "key": "women_skirts",
        "gender": "women",
        "name": "Юбки жен",
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


def sold_vl25_26_by_size(items_sales: list[dict]) -> dict[str, int]:
    sold: dict[str, int] = defaultdict(int)
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
    return dict(sold)


def metrics_table(
    by_size_ss: dict[str, dict],
    stock_vl25_26: dict[str, int],
    sold: dict[str, int],
):
    """Table columns:
    - sold_total: ВЛ2025+ВЛ2026 net sales
    - stock_total: all SS stock (same F+O as comment)
    - received_total: sold + stock of ВЛ2025+ВЛ2026 only
      (two-season intake; may be << stock_total when old SS tails remain)
    """
    sizes = sorted(
        set(by_size_ss) | set(sold) | set(stock_vl25_26), key=size_sort_key
    )
    rows = []
    chart_labels = []
    chart_sold = []
    for size in sizes:
        s = int(sold.get(size) or 0)
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


def _median_int(vals: list[int]) -> int:
    if not vals:
        return 0
    xs = sorted(vals)
    return xs[len(xs) // 2]


def make_comment(
    by_size: dict[str, dict],
    sold: dict[str, int],
    stock_two: dict[str, int],
) -> tuple[str, list[str], list[str]]:
    """Hints: sales first, then coverage vs stock, then VL2026 fresh.
    Never weaken the sales core.
    """
    all_sizes = sorted(
        set(by_size) | set(sold) | set(stock_two), key=size_sort_key
    )
    # ensure stock map covers sizes that only appear in sales
    for s in all_sizes:
        by_size.setdefault(s, {"fresh": 0, "old": 0, "total": 0})

    sizes_pos = [s for s in all_sizes if by_size[s]["total"] > 0 or sold.get(s, 0) > 0]
    total = sum(by_size[s]["total"] for s in sizes_pos)
    fresh = sum(by_size[s]["fresh"] for s in sizes_pos)
    old = sum(by_size[s]["old"] for s in sizes_pos)

    sold_pos = {s: int(sold.get(s) or 0) for s in sizes_pos if int(sold.get(s) or 0) > 0}
    median_sold = _median_int(list(sold_pos.values())) if sold_pos else 0
    max_sold = max(sold_pos.values()) if sold_pos else 0
    # Sales core: never weaken. Median sellers + anyone near the top.
    core = {
        s
        for s, q in sold_pos.items()
        if (median_sold > 0 and q >= median_sold)
        or (max_sold > 0 and q >= max_sold * 0.4)
    }

    # --- Усилить: demand exists, thin cover vs sales; boost low VL2026 ---
    min_sold = 1
    if median_sold > 0:
        min_sold = max(1, min(3, median_sold // 2 or 1))
    reinforce_scored: list[tuple[str, float]] = []
    for s in sizes_pos:
        so = int(sold.get(s) or 0)
        if so < min_sold:
            continue  # weak/no sales signal — do not reinforce
        st = by_size[s]["total"]
        fr = by_size[s]["fresh"]
        cover = st / so
        # need thin cover or running out of fresh relative to demand
        thin = cover <= 1.0 or st <= max(2, so // 3)
        low_fresh = fr == 0 or fr < max(1, so // 4)
        if not (thin or low_fresh):
            continue
        score = so / (st + 1)
        if fr == 0:
            score *= 1.45
        elif fr < so * 0.25:
            score *= 1.2
        if cover <= 0.5:
            score *= 1.25
        # prefer real demand over tiny-sold edge sizes
        if so >= median_sold and median_sold > 0:
            score *= 1.15
        reinforce_scored.append((s, score))

    reinforce_scored.sort(key=lambda x: (-x[1], -int(sold.get(x[0]) or 0)))
    reinforce = [s for s, _ in reinforce_scored[:4]]

    # --- Ослабить: not core, not reinforce; weak sell-through / fat leftover ---
    stock_vals = [by_size[s]["total"] for s in sizes_pos if by_size[s]["total"] > 0]
    median_stock = _median_int(stock_vals)
    weaken_scored: list[tuple[str, float]] = []
    for s in sizes_pos:
        if s in core or s in reinforce:
            continue
        so = int(sold.get(s) or 0)
        st = by_size[s]["total"]
        fr = by_size[s]["fresh"]
        ol = by_size[s]["old"]
        st_two = int(stock_two.get(s) or 0)
        if st <= 0:
            continue
        if st < max(3, median_stock):
            continue
        intake = so + st_two
        sell_through = (so / intake) if intake > 0 else 0.0
        cover = (st / so) if so > 0 else 99.0
        # require clear overstock vs sales; old tails boost score only
        overstock = so == 0 or cover >= 2.0 or sell_through <= 0.35
        if not overstock:
            continue
        score = st * (1.0 - min(sell_through, 1.0)) + ol * 1.5
        if so == 0:
            score += st * 2
        if ol >= max(fr, 1) and ol >= 3:
            score *= 1.2
        weaken_scored.append((s, score))

    weaken_scored.sort(key=lambda x: (-x[1], -by_size[x[0]]["old"]))
    weaken = [s for s, _ in weaken_scored[:3]]

    def fmt(s: str) -> str:
        v = by_size[s]
        return f"{s} ({v['fresh']};{v['old']})"

    reinforce_txt = (
        ", ".join(fmt(s) for s in reinforce) if reinforce else "нет явных"
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
        sold = sold_vl25_26_by_size(sales.get("items") or [])
        comment, reinforce, weaken = make_comment(by_size, sold, stock_two)
        rows, labels, sold_qty = metrics_table(by_size, stock_two, sold)
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
                "Усилить/Ослабить: sales-first + cover vs stock + VL2026 fresh; "
                "never weaken sales core"
            ),
            "hint_rule": (
                "reinforce: sold>=min threshold, thin stock vs sales "
                "(boost if low/zero VL2026); "
                "weaken: not sales-core, clear overstock vs sales "
                "(old SS boosts score); "
                "sales core = sold>=median or sold>=40% of max"
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
            "ms_folder_split": (
                "июль 2026: брюки/джинсы ≠ бриджи/шорты; платья ≠ юбки. "
                "Sales/stock for split cats from name-heuristic of pre-split dumps "
                "(product moved with history in MS; size analytics rebuilt)."
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
    for key in (
        "men_pants",
        "men_shorts",
        "women_pants",
        "women_shorts",
        "women_dresses",
        "women_skirts",
    ):
        c = next(x for x in out_cats if x["key"] == key)
        st = c["stock_totals"]
        assert st["total"] == st["fresh_vl26"] + st["old"]
        print(
            f"\n=== {c['name']} €{c['order_amount_eur']} ===\n{c['comment']}\n"
            f"reinforce={c['reinforce_sizes']} weaken={c['weaken_sizes']}"
        )
        for row in c["size_summary_rows"][:6]:
            print(" ", row)


if __name__ == "__main__":
    main()
