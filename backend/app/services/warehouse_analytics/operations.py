"""Исполнение semantic operations против МойСклад REST."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.services.warehouse_analytics.cache import ANALYTICS_CACHE, cache_key
from app.services.warehouse_analytics.constants import (
    MAX_PRODUCTS_BRAND,
    MAX_PURCHASE_LINES,
    MAX_SERIES_POINTS,
    MAX_TOP_ROWS,
    RETAILSTORE_ANTRASHA_ID,
    STORE_ANTRASHA_ID,
    STORE_STOCK_ID,
)
from app.services.warehouse_analytics.ms_client import (
    MoySkladAnalyticsClient,
    encode_filter,
    money_rub,
)
from app.services.warehouse_analytics.ms_reports import (
    ProfitFilters,
    StockFilters,
    fetch_dashboard,
    fetch_profit_rows,
    fetch_sales_plotseries,
    fetch_stock_rows,
    normalize_profit_row,
    resolve_store_id,
)

log = logging.getLogger("app.warehouse_analytics.ops")
_TZ = ZoneInfo("Europe/Moscow")
_SEASON_RE = re.compile(r"(ВЛ|ОЗ)\s*(\d{2,4})", re.IGNORECASE)
# Дата коллекции в артикуле: …/02.26 или …/06.26
_ARTICLE_DATE_RE = re.compile(r"(?:^|/|\s)(\d{2})\.(\d{2})(?:\s|$|/)", re.IGNORECASE)


def _today() -> date:
    return datetime.now(_TZ).date()


def _parse_day(s: str | None, *, default: date | None = None) -> date:
    if not s or not str(s).strip():
        if default is None:
            raise ValueError("date required")
        return default
    return date.fromisoformat(str(s).strip()[:10])


def _moment(d: date, end: bool = False) -> str:
    if end:
        return f"{d.isoformat()} 23:59:59"
    return f"{d.isoformat()} 00:00:00"


def _store_id(store: str | None) -> str | None:
    key = (store or "antrasha").strip().lower()
    if key in ("antrasha", "антраша", "main", "default"):
        return STORE_ANTRASHA_ID
    if key in ("stock", "сток"):
        return STORE_STOCK_ID
    if key in ("all", "any", "*"):
        return None
    # raw uuid
    if re.fullmatch(r"[0-9a-f-]{36}", key, re.I):
        return key.lower()
    return STORE_ANTRASHA_ID


def _assortment_brief(row: dict[str, Any]) -> dict[str, Any]:
    ass = row.get("assortment") if isinstance(row.get("assortment"), dict) else row
    name = ass.get("name") if isinstance(ass, dict) else None
    article = ass.get("article") if isinstance(ass, dict) else None
    path = ass.get("pathName") if isinstance(ass, dict) else None
    meta = ass.get("meta") if isinstance(ass, dict) and isinstance(ass.get("meta"), dict) else {}
    href = meta.get("href")
    return {
        "name": name,
        "article": article,
        "path": path,
        "href": href,
    }


def _gender_from_path(path: str | None, name: str | None = None) -> str | None:
    blob = f"{path or ''} {name or ''}".casefold()
    if "женск" in blob or "(жен" in blob or re.search(r"(?:^|[\s,/(-])жен(?:ск|\b|[)\s,]|$)", blob):
        return "female"
    if "мужск" in blob or "(муж" in blob or re.search(r"(?:^|[\s,/(-])муж(?:ск|\b|[)\s,]|$)", blob):
        return "male"
    return None


def _brand_key(supplier_name: str | None) -> str | None:
    """Нормализация бренда: DUNO(муж) → DUNO (пол у поставщика — суффикс учёта)."""
    if not supplier_name or not str(supplier_name).strip():
        return None
    name = str(supplier_name).strip()
    cleaned = re.sub(r"\s*[\(（]\s*(муж|жен|м|ж)\s*[\)）]\s*$", "", name, flags=re.I).strip()
    return cleaned or name


def _supplier_from_assortment(ass: dict[str, Any]) -> dict[str, Any] | None:
    """Бренд ANTRASHA = поле supplier у товара (или у product у модификации)."""
    candidates: list[dict[str, Any]] = [ass]
    product = ass.get("product")
    if isinstance(product, dict):
        candidates.append(product)
    for node in candidates:
        sup = node.get("supplier")
        if not isinstance(sup, dict):
            continue
        name = str(sup.get("name") or "").strip()
        sid = sup.get("id")
        if not sid:
            href = ""
            meta = sup.get("meta") if isinstance(sup.get("meta"), dict) else {}
            href = str(meta.get("href") or "")
            m = re.search(r"/counterparty/([0-9a-f-]{36})", href, re.I)
            if m:
                sid = m.group(1)
        if name or sid:
            return {"id": sid, "name": name or None, "brand": _brand_key(name)}
    return None


def _size_from_name(name: str | None) -> str | None:
    if not name:
        return None
    # типичные «… 48», «… M», «size 42»
    m = re.search(r"(?:^|[\s/(-])((?:XXL|XL|XS|S|M|L)|(?:3[2-9]|4[0-9]|5[0-8]))(?:$|[\s/)-])", name, re.I)
    return m.group(1).upper() if m else None


def season_dates(season: str, year: int) -> tuple[date, date]:
    s = season.strip().upper()
    if s in ("VL", "ВЛ"):
        return date(year, 2, 1), date(year, 8, 31)
    if s in ("OZ", "ОЗ"):
        return date(year, 9, 1), date(year + 1, 1, 31)
    raise ValueError(f"unknown season {season}")


def article_collection_season(text: str | None) -> tuple[str, int] | None:
    """Сезон коллекции из даты в артикуле/имени: /02.26 → (VL, 2026), /11.25 → (OZ, 2025)."""
    if not text:
        return None
    matches = list(_ARTICLE_DATE_RE.finditer(str(text).replace(" ", "")))
    if not matches:
        matches = list(_ARTICLE_DATE_RE.finditer(str(text)))
    if not matches:
        return None
    m = matches[-1]
    mm, yy = int(m.group(1)), int(m.group(2))
    year = 2000 + yy
    if 2 <= mm <= 8:
        return ("VL", year)
    if mm == 1:
        return ("OZ", year - 1)
    if mm >= 9:
        return ("OZ", year)
    return None


def matches_season_marker(text: str | None, season: str, year: int) -> bool:
    if not text:
        return False
    s = season.strip().upper()
    marker = "ВЛ" if s in ("VL", "ВЛ") else "ОЗ"
    want = "VL" if marker == "ВЛ" else "OZ"
    yy2 = str(year % 100).zfill(2)
    yy4 = str(year)
    for m in _SEASON_RE.finditer(text):
        kind, yraw = m.group(1).upper(), m.group(2)
        if kind != marker:
            continue
        y = int(yraw)
        if y < 100:
            y += 2000
        if y == year or str(y).endswith(yy2) or yy4 in yraw:
            return True
    if f"{marker}{yy2}" in text.upper().replace(" ", "") or f"{marker}{year}" in text.upper().replace(" ", ""):
        return True
    coll = article_collection_season(text)
    return bool(coll and coll[0] == want and coll[1] == year)


def _category_from_path(path: str | None) -> str:
    if not path:
        return "без категории"
    parts = [p for p in str(path).split("/") if p.strip()]
    return parts[-1] if parts else "без категории"


def run_operation(
    client: MoySkladAnalyticsClient,
    operation: str,
    args: dict[str, Any] | None,
    *,
    use_cache: bool = True,
    cache_ttl: float = 600.0,
) -> dict[str, Any]:
    args = dict(args or {})
    key = cache_key(f"{operation}:v3", args)
    if use_cache:
        hit = ANALYTICS_CACHE.get(key)
        if hit is not None:
            out = dict(hit)
            out["cache_hit"] = True
            return out

    handlers = {
        "revenue_series": _op_revenue_series,
        "dashboard_period": _op_dashboard_period,
        "profit_top_products": _op_profit_top_products,
        "stock_snapshot": _op_stock_snapshot,
        "brand_products": _op_brand_products,
        "brand_sales": _op_brand_sales,
        "top_counterparties": _op_top_counterparties,
        "customer_purchases": _op_customer_purchases,
        "open_orders": _op_open_orders,
    }
    fn = handlers.get(operation)
    if not fn:
        raise ValueError(f"Unknown operation: {operation}")
    result = fn(client, args)
    result["operation"] = operation
    result["cache_hit"] = False
    if use_cache:
        ANALYTICS_CACHE.set(key, result, ttl_sec=cache_ttl)
    return result


def _op_revenue_series(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    today = _today()
    date_to = _parse_day(args.get("date_to"), default=today)
    date_from = _parse_day(args.get("date_from"), default=date_to - timedelta(days=29))
    interval = str(args.get("interval") or "day").strip().lower()
    if interval not in ("day", "month", "year"):
        interval = "day"
    # plotseries API: hour|day|month (year → month)
    api_interval: Any = "month" if interval == "year" else interval
    if api_interval not in ("hour", "day", "month"):
        api_interval = "day"
    store_id = resolve_store_id(args.get("store") or "antrasha")
    data = fetch_sales_plotseries(
        client,
        date_from=date_from,
        date_to=date_to,
        interval=api_interval,
        store_id=store_id,
    )
    series = []
    raw_series = data.get("series") if isinstance(data, dict) else None
    if isinstance(raw_series, list):
        for point in raw_series[:MAX_SERIES_POINTS]:
            if not isinstance(point, dict):
                continue
            series.append(
                {
                    "moment": point.get("date") or point.get("moment") or point.get("period"),
                    "sum": money_rub(point.get("sum") or point.get("sellSum") or point.get("salesSum")),
                    "quantity": point.get("quantity") or point.get("sellQuantity"),
                }
            )
    elif isinstance(data, dict) and isinstance(data.get("rows"), list):
        for point in data["rows"][:MAX_SERIES_POINTS]:
            if isinstance(point, dict):
                series.append(
                    {
                        "moment": point.get("date") or point.get("moment"),
                        "sum": money_rub(point.get("sum") or point.get("sellSum")),
                        "quantity": point.get("quantity"),
                    }
                )
    total = sum(p["sum"] or 0 for p in series)
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "interval": interval,
        "points": series,
        "total_sum": round(total, 2),
        "method": "report/sales/plotseries",
        "note": "Торговая выручка отчёта sales/plotseries (не сырые отгрузки).",
    }


def _op_dashboard_period(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    period = str(args.get("period") or "month").strip().lower()
    if period not in ("day", "week", "month"):
        period = "month"
    data = fetch_dashboard(client, period)  # type: ignore[arg-type]
    if not isinstance(data, dict):
        return {"period": period, "raw_type": type(data).__name__}
    out: dict[str, Any] = {"period": period, "method": f"report/dashboard/{period}"}
    for key in (
        "sales",
        "orders",
        "money",
    ):
        block = data.get(key)
        if isinstance(block, dict):
            compact = {}
            for k, v in block.items():
                if isinstance(v, (int, float)) and k.lower().endswith(("sum", "amount", "credit", "debit")):
                    compact[k] = money_rub(v)
                else:
                    compact[k] = v
            out[key] = compact
        elif block is not None:
            out[key] = block
    return out


def _op_profit_top_products(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    today = _today()
    date_to = _parse_day(args.get("date_to"), default=today)
    date_from = _parse_day(args.get("date_from"), default=date(today.year, today.month, 1))
    limit = min(MAX_TOP_ROWS, max(1, int(args.get("limit") or 15)))
    sort = str(args.get("sort") or "sell").strip().lower()
    store_id = resolve_store_id(args.get("store") or "antrasha")
    filt = ProfitFilters(store_ids=[store_id] if store_id else [])
    rows, size = fetch_profit_rows(
        client,
        date_from=date_from,
        date_to=date_to,
        filters=filt,
        limit=max(limit, 50),
        max_pages=1,
    )
    # API order param unreliable — sort locally
    key_fn = (lambda r: float(r.get("profit") or 0)) if sort == "profit" else (lambda r: float(r.get("sellSum") or 0))
    rows = sorted(rows, key=key_fn, reverse=True)
    items = []
    for row in rows[:limit]:
        fields = normalize_profit_row(row)
        items.append(
            {
                **fields,
                "category": _category_from_path(fields.get("path") if isinstance(fields.get("path"), str) else None),
                "gender": _gender_from_path(
                    fields.get("path") if isinstance(fields.get("path"), str) else None,
                    fields.get("name") if isinstance(fields.get("name"), str) else None,
                ),
                "margin": row.get("margin"),
            }
        )
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "store": args.get("store") or "antrasha",
        "sort": sort,
        "total_rows": size,
        "items": items,
        "method": "report/profit/byproduct",
    }


def _op_stock_snapshot(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(MAX_TOP_ROWS, max(1, int(args.get("limit") or 20)))
    mode = str(args.get("mode") or "positive").strip().lower()
    store_id = resolve_store_id(args.get("store") or "antrasha")
    qmode = None
    if mode in ("positive", "positiveonly", "gt0"):
        qmode = "positiveOnly"
    elif mode in ("low", "underminimum", "under"):
        qmode = "underMinimum"
    supplier_ids: list[str] = []
    brand = str(args.get("brand") or "").strip()
    if brand:
        for sup in _find_suppliers(client, brand, None):
            if sup.get("id"):
                supplier_ids.append(str(sup["id"]))
    filt = StockFilters(
        store_ids=[store_id] if store_id else [],
        supplier_ids=supplier_ids,
        quantity_mode=qmode,  # type: ignore[arg-type]
    )
    rows, size = fetch_stock_rows(
        client,
        filters=filt,
        group_by="product",
        limit=limit,
        order="stock,asc" if mode in ("low", "underminimum", "under") else "stock,desc",
    )
    items = []
    for row in rows[:limit]:
        brief = _assortment_brief(row)
        stock = row.get("stock") if row.get("stock") is not None else row.get("quantity")
        items.append(
            {
                **brief,
                "stock": stock,
                "reserve": row.get("reserve"),
                "in_transit": row.get("inTransit"),
                "gender": _gender_from_path(brief.get("path"), brief.get("name")),
            }
        )
    return {
        "store": "stock" if store_id == STORE_STOCK_ID else ("all" if not store_id else "antrasha"),
        "mode": mode,
        "brand": brand or None,
        "total_rows": size,
        "items": items,
        "method": "report/stock/all",
    }


def _find_suppliers(client: MoySkladAnalyticsClient, brand: str, gender: str | None) -> list[dict[str, Any]]:
    rows, _ = client.get_rows(
        "/entity/counterparty",
        params={"search": brand, "limit": 50},
    )
    brand_l = brand.casefold().strip()
    brand_key = (_brand_key(brand) or brand).casefold()
    scored: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        name = str(row.get("name") or "")
        nl = name.casefold()
        key = (_brand_key(name) or name).casefold()
        g = None
        if "(жен" in nl or " жен" in nl:
            g = "female"
        elif "(муж" in nl or " муж" in nl:
            g = "male"
        if gender in ("male", "female") and g and g != gender:
            continue
        score = 0
        if nl == brand_l or key == brand_key:
            score = 100
        elif nl.startswith(brand_l) or key.startswith(brand_key):
            score = 80
        elif brand_l in nl or brand_key in key:
            score = 60
        elif brand_l[:4] and brand_l[:4] in nl:
            score = 20
        else:
            score = 10  # search hit
        if gender in ("male", "female") and not g and score < 80:
            continue
        scored.append((score, {"id": row.get("id"), "name": name, "gender": g}))
    scored.sort(key=lambda x: (-x[0], str(x[1].get("name") or "")))
    out = [item for _, item in scored]
    if gender in ("male", "female") and not out:
        for row in rows:
            name = str(row.get("name") or "")
            if brand_key[:3] in (_brand_key(name) or name).casefold():
                out.append({"id": row.get("id"), "name": name, "gender": None})
    return out[:6]


def _op_brand_products(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    brand = str(args.get("brand") or "").strip()
    if not brand:
        raise ValueError("brand required")
    gender = args.get("gender")
    gender_s = str(gender).strip().lower() if gender else "both"
    if gender_s not in ("male", "female", "both"):
        gender_s = "both"
    limit = min(MAX_PRODUCTS_BRAND, max(1, int(args.get("limit") or 50)))
    suppliers = _find_suppliers(client, brand, None if gender_s == "both" else gender_s)
    products: list[dict[str, Any]] = []
    for sup in suppliers:
        sid = sup.get("id")
        if not sid:
            continue
        href = client.href("counterparty", str(sid))
        rows, size = client.get_rows(
            "/entity/product",
            params={
                "filter": f"supplier={href}",
                "limit": min(100, limit),
            },
        )
        for row in rows:
            name = str(row.get("name") or "")
            path = str(row.get("pathName") or "") if row.get("pathName") else None
            g = _gender_from_path(path, name) or sup.get("gender")
            if gender_s in ("male", "female") and g and g != gender_s:
                continue
            products.append(
                {
                    "id": row.get("id"),
                    "name": name,
                    "article": row.get("article"),
                    "path": path,
                    "gender": g,
                    "supplier": sup.get("name"),
                    "supplier_id": sid,
                }
            )
            if len(products) >= limit:
                break
        if len(products) >= limit:
            break
    return {
        "brand": brand,
        "gender": gender_s,
        "suppliers": suppliers,
        "products_count": len(products),
        "products": products[:limit],
        "note": "Бренд = поставщик (supplier), не папка товаров.",
    }


def _op_brand_sales(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    """
    Как UI «Прибыльность» (Remap report-pnl):
    GET /report/profit/byproduct?momentFrom&momentTo&filter=supplier=…[;store=…]
    Сезон коллекции — пост-фильтр (в API отдельного filter «сезон» нет).
    """
    brand = str(args.get("brand") or "").strip()
    if not brand:
        raise ValueError("brand required")
    today = _today()
    season = args.get("season")
    year = args.get("year")
    if season:
        y = int(year or today.year)
        date_from, date_to = season_dates(str(season), y)
        if date_to > today:
            date_to = today
        season_meta: dict[str, Any] | None = {"season": str(season).upper(), "year": y}
    else:
        date_to = _parse_day(args.get("date_to"), default=today)
        date_from = _parse_day(args.get("date_from"), default=date(today.year, today.month, 1))
        season_meta = None

    if args.get("date_from"):
        date_from = _parse_day(args.get("date_from"))
    if args.get("date_to"):
        date_to = _parse_day(args.get("date_to"))

    gender_s = str(args.get("gender") or "both").strip().lower()
    if gender_s not in ("male", "female", "both"):
        gender_s = "both"
    store = str(args.get("store") or "antrasha").strip().lower()
    store_id = resolve_store_id(store)

    suppliers = _find_suppliers(client, brand, None if gender_s == "both" else gender_s)
    if not suppliers:
        return {
            "brand": brand,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
            "season": season_meta,
            "suppliers": [],
            "matched_sales_rows": 0,
            "total_sell_sum": 0,
            "total_profit": 0,
            "total_sell_quantity": 0,
            "by_category": [],
            "top_items": [],
            "notes": ["Поставщик (бренд) не найден в МойСклад."],
            "method": "report/profit/byproduct+filter=supplier",
        }

    supplier_ids = [str(s["id"]) for s in suppliers if s.get("id")]
    # Один запрос на всех поставщиков бренда (DUNO муж+жен) — API допускает несколько supplier=
    raw_rows, _total = fetch_profit_rows(
        client,
        date_from=date_from,
        date_to=date_to,
        filters=ProfitFilters(
            supplier_ids=supplier_ids,
            store_ids=[store_id] if store_id else [],
        ),
    )

    items: list[dict[str, Any]] = []
    season_note = None
    for row in raw_rows:
        fields = normalize_profit_row(row)
        path = fields.get("path") if isinstance(fields.get("path"), str) else None
        name = fields.get("name") if isinstance(fields.get("name"), str) else None
        fields["category"] = _category_from_path(path)
        fields["gender"] = _gender_from_path(path, name)
        if gender_s in ("male", "female"):
            g = fields.get("gender")
            if g and g != gender_s:
                continue
        if season_meta:
            blob = f"{fields.get('name') or ''} {fields.get('article') or ''}"
            if not matches_season_marker(blob, str(season_meta["season"]), int(season_meta["year"])):
                continue
        items.append(fields)

    if season_meta and raw_rows and not items:
        season_note = (
            "По маркеру сезона/дате в артикуле строк не осталось — "
            "проверьте season/year или смотрите продажи поставщика без фильтра коллекции."
        )

    items.sort(key=lambda x: -(x.get("sell_sum") or 0))
    total_sell = round(sum(x.get("sell_sum") or 0 for x in items), 2)
    total_profit = round(sum(x.get("profit") or 0 for x in items), 2)
    total_qty = round(sum(float(x.get("sell_quantity") or 0) for x in items), 3)
    total_cost = round(sum(x.get("sell_cost_sum") or 0 for x in items), 2)

    by_cat: dict[str, dict[str, float]] = {}
    for it in items:
        cat = str(it.get("category") or "без категории")
        bucket = by_cat.setdefault(cat, {"sell_sum": 0.0, "profit": 0.0, "sell_quantity": 0.0, "skus": 0})
        bucket["sell_sum"] = round(bucket["sell_sum"] + (it.get("sell_sum") or 0), 2)
        bucket["profit"] = round(bucket["profit"] + (it.get("profit") or 0), 2)
        bucket["sell_quantity"] = round(bucket["sell_quantity"] + float(it.get("sell_quantity") or 0), 3)
        bucket["skus"] += 1
    by_category = [
        {"category": k, **v}
        for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1]["sell_sum"])
    ]

    sold_skus = len(
        {
            (it.get("article") or it.get("name") or "").casefold()
            for it in items
            if it.get("article") or it.get("name")
        }
    )

    return {
        "brand": brand,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "season": season_meta,
        "store": store,
        "suppliers": suppliers,
        "matched_sales_rows": len(items),
        "sold_skus": sold_skus,
        "total_sell_quantity": total_qty,
        "total_sell_sum": total_sell,
        "total_sell_cost_sum": total_cost,
        "total_profit": total_profit,
        "by_category": by_category,
        "top_items": items[:25],
        "method": "report/profit/byproduct+filter=supplier",
        "notes": [
            "Бренд = Поставщик. Remap: filter=supplier (docs report-pnl).",
            "Сезон коллекции: маркер ВЛ/ОЗ или /MM.YY в артикуле (в API filter «сезон» нет).",
            season_note,
        ],
    }


def _op_top_counterparties(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    today = _today()
    date_to = _parse_day(args.get("date_to"), default=today)
    date_from = _parse_day(args.get("date_from"), default=date(today.year, today.month, 1))
    limit = min(MAX_TOP_ROWS, max(1, int(args.get("limit") or 10)))
    # API order= часто игнорируется — тянем пачку и сортируем сами.
    fetch_limit = min(100, max(limit * 5, 50))
    rows, size = client.get_rows(
        "/report/profit/bycounterparty",
        params={
            "momentFrom": _moment(date_from),
            "momentTo": _moment(date_to, end=True),
            "limit": fetch_limit,
        },
    )
    items = []
    for row in rows:
        cp = row.get("counterparty") if isinstance(row.get("counterparty"), dict) else {}
        meta = cp.get("meta") if isinstance(cp.get("meta"), dict) else {}
        href = meta.get("href")
        cid = cp.get("id")
        if not cid and href:
            m = re.search(r"/entity/counterparty/([0-9a-f-]{36})", str(href), re.I)
            if m:
                cid = m.group(1).lower()
        name = cp.get("name")
        sell = money_rub(row.get("sellSum"))
        # отсечь пустых / нулевых
        if sell is None or sell <= 0:
            continue
        items.append(
            {
                "id": cid,
                "name": name,
                "href": href,
                "sell_sum": sell,
                "profit": money_rub(row.get("profit")),
                "sell_quantity": row.get("sellQuantity"),
            }
        )
    items.sort(key=lambda x: float(x.get("sell_sum") or 0), reverse=True)
    top = items[:limit]
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "total_rows": size,
        "fetched": len(items),
        "sorted_by": "sell_sum_desc",
        "best": top[0] if top else None,
        "items": top,
        "note": "Топ по sellSum отчёта profit/bycounterparty (сортировка на бэкенде).",
    }


def _resolve_counterparty(
    client: MoySkladAnalyticsClient,
    *,
    counterparty_id: str | None,
    counterparty_name: str | None,
) -> dict[str, Any]:
    cid = (counterparty_id or "").strip()
    if cid and re.fullmatch(r"[0-9a-f-]{36}", cid, re.I):
        data = client.get(f"/entity/counterparty/{cid}")
        if isinstance(data, dict) and data.get("id"):
            return {"id": data.get("id"), "name": data.get("name")}
    name = (counterparty_name or "").strip()
    if not name or _looks_like_placeholder(name):
        raise ValueError("counterparty_id or counterparty_name required")
    rows, _ = client.get_rows("/entity/counterparty", params={"search": name, "limit": 10})
    if not rows:
        raise LookupError(f"Контрагент не найден: {name}")
    name_l = name.casefold()
    for row in rows:
        if str(row.get("name") or "").casefold() == name_l:
            return {"id": row.get("id"), "name": row.get("name")}
    return {"id": rows[0].get("id"), "name": rows[0].get("name")}


def _looks_like_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    if not s:
        return True
    if s.startswith("<<") and s.endswith(">>"):
        return True
    low = s.casefold()
    return any(
        x in low
        for x in (
            "top_counterparty",
            "step_1",
            "step1",
            "placeholder",
            "from_previous",
            "todo",
            "{{",
            "}}",
        )
    )


def _op_customer_purchases(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    today = _today()
    date_to = _parse_day(args.get("date_to"), default=today)
    date_from = _parse_day(args.get("date_from"), default=date(today.year, today.month, 1))
    cp = _resolve_counterparty(
        client,
        counterparty_id=str(args["counterparty_id"]) if args.get("counterparty_id") else None,
        counterparty_name=str(args["counterparty_name"]) if args.get("counterparty_name") else None,
    )
    agent_href = client.href("counterparty", str(cp["id"]))
    # retail demands
    filt = encode_filter(
        [
            f"agent={agent_href}",
            f"moment>={_moment(date_from)}",
            f"moment<={_moment(date_to, end=True)}",
        ]
    )
    rows, size = client.get_rows(
        "/entity/demand",
        params={
            "filter": filt,
            "limit": 50,
            "expand": "positions.assortment.supplier,positions.assortment.product.supplier",
            "order": "moment,desc",
        },
    )
    # also try retaildemand
    retail_rows, retail_size = client.get_rows(
        "/entity/retaildemand",
        params={
            "filter": encode_filter(
                [
                    f"agent={agent_href}",
                    f"moment>={_moment(date_from)}",
                    f"moment<={_moment(date_to, end=True)}",
                    f"retailStore={client.href('retailstore', RETAILSTORE_ANTRASHA_ID)}",
                ]
            ),
            "limit": 50,
            "expand": "positions.assortment.supplier,positions.assortment.product.supplier",
            "order": "moment,desc",
        },
    )

    lines: list[dict[str, Any]] = []

    def _line_sum(pos: dict[str, Any]) -> float | None:
        if pos.get("sum") is not None:
            return money_rub(pos.get("sum"))
        price = pos.get("price")
        qty = pos.get("quantity") or 1
        if price is not None:
            return money_rub(price * qty)
        return None

    def _consume_docs(docs: list[dict[str, Any]], doc_type: str) -> None:
        for doc in docs:
            positions = doc.get("positions")
            pos_rows = []
            if isinstance(positions, dict) and isinstance(positions.get("rows"), list):
                pos_rows = positions["rows"]
            for pos in pos_rows:
                if not isinstance(pos, dict):
                    continue
                ass = pos.get("assortment") if isinstance(pos.get("assortment"), dict) else {}
                name = str(ass.get("name") or "")
                path = str(ass.get("pathName") or "") if ass.get("pathName") else None
                supplier = _supplier_from_assortment(ass)
                brand = (supplier or {}).get("brand")
                lines.append(
                    {
                        "doc_type": doc_type,
                        "moment": doc.get("moment"),
                        "name": name,
                        "article": ass.get("article"),
                        "quantity": pos.get("quantity"),
                        "sum": _line_sum(pos),
                        "size": _size_from_name(name),
                        "gender": _gender_from_path(path, name),
                        "path": path,
                        "supplier": (supplier or {}).get("name"),
                        "brand": brand,
                    }
                )

    _consume_docs(rows, "demand")
    _consume_docs(retail_rows, "retaildemand")
    lines = lines[:MAX_PURCHASE_LINES]

    by_gender: dict[str, float] = {}
    by_size: dict[str, float] = {}
    by_brand: dict[str, float] = {}
    for ln in lines:
        g = ln.get("gender") or "unknown"
        by_gender[g] = round(by_gender.get(g, 0) + (ln.get("sum") or 0), 2)
        sz = ln.get("size") or "unknown"
        by_size[sz] = round(by_size.get(sz, 0) + (ln.get("sum") or 0), 2)
        brand = ln.get("brand") or "unknown"
        by_brand[brand] = round(by_brand.get(brand, 0) + (ln.get("sum") or 0), 2)

    return {
        "counterparty": cp,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "documents": {"demand": size, "retaildemand": retail_size},
        "lines_count": len(lines),
        "by_gender_sum": by_gender,
        "by_size_sum": by_size,
        "by_brand_sum": by_brand,
        "brand_definition": (
            "Бренд = марка = поставщик = поле «Поставщик» (supplier) карточки товара. "
            "Смотри lines[].brand / by_brand_sum."
        ),
        "lines": lines,
    }


def _op_open_orders(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(MAX_TOP_ROWS, max(1, int(args.get("limit") or 15)))
    rows, size = client.get_rows(
        "/entity/customerorder",
        params={
            "limit": limit,
            "order": "moment,desc",
            "filter": "isDeleted=false",
        },
    )
    items = []
    for row in rows[:limit]:
        state = row.get("state") if isinstance(row.get("state"), dict) else {}
        agent = row.get("agent") if isinstance(row.get("agent"), dict) else {}
        items.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "moment": row.get("moment"),
                "sum": money_rub(row.get("sum")),
                "state": state.get("name"),
                "agent": agent.get("name"),
            }
        )
    return {"total_rows": size, "items": items}
