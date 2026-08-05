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

log = logging.getLogger("app.warehouse_analytics.ops")
_TZ = ZoneInfo("Europe/Moscow")
_SEASON_RE = re.compile(r"(ВЛ|ОЗ)\s*(\d{2,4})", re.IGNORECASE)


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
    if "женск" in blob or "(жен" in blob:
        return "female"
    if "мужск" in blob or "(муж" in blob:
        return "male"
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


def matches_season_marker(text: str | None, season: str, year: int) -> bool:
    if not text:
        return False
    s = season.strip().upper()
    marker = "ВЛ" if s in ("VL", "ВЛ") else "ОЗ"
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
    # fallback substring
    return f"{marker}{yy2}" in text.upper().replace(" ", "") or f"{marker}{year}" in text.upper().replace(" ", "")


def run_operation(
    client: MoySkladAnalyticsClient,
    operation: str,
    args: dict[str, Any] | None,
    *,
    use_cache: bool = True,
    cache_ttl: float = 600.0,
) -> dict[str, Any]:
    args = dict(args or {})
    key = cache_key(f"{operation}:v2", args)
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
    data = client.get(
        "/report/sales/plotseries",
        params={
            "momentFrom": _moment(date_from),
            "momentTo": _moment(date_to, end=True),
            "interval": interval,
        },
    )
    series = []
    raw_series = data.get("series") if isinstance(data, dict) else None
    # API variants: series as list of {moment, sum/quantity} or nested
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
        "note": "Торговая выручка отчёта sales/plotseries (не сырые отгрузки).",
    }


def _op_dashboard_period(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    period = str(args.get("period") or "month").strip().lower()
    if period not in ("day", "week", "month"):
        period = "month"
    data = client.get(f"/report/dashboard/{period}")
    if not isinstance(data, dict):
        return {"period": period, "raw_type": type(data).__name__}
    # compact known fields
    out: dict[str, Any] = {"period": period}
    for key in (
        "sales",
        "orders",
        "money",
    ):
        block = data.get(key)
        if isinstance(block, dict):
            compact = {}
            for k, v in block.items():
                if isinstance(v, (int, float)):
                    compact[k] = money_rub(v) if "sum" in k.lower() or "amount" in k.lower() or k in ("sales", "profit") else v
                elif isinstance(v, dict):
                    compact[k] = {
                        sk: (money_rub(sv) if isinstance(sv, (int, float)) and ("sum" in sk.lower() or sk in ("sales", "profit", "amount")) else sv)
                        for sk, sv in list(v.items())[:20]
                    }
                else:
                    compact[k] = v
            out[key] = compact
    # fallback slice
    if len(out) == 1:
        out["preview"] = {k: data[k] for k in list(data.keys())[:12]}
    return out


def _op_profit_top_products(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    today = _today()
    date_to = _parse_day(args.get("date_to"), default=today)
    date_from = _parse_day(args.get("date_from"), default=date(today.year, today.month, 1))
    limit = min(MAX_TOP_ROWS, max(1, int(args.get("limit") or 15)))
    sort = str(args.get("sort") or "sell").strip().lower()
    order = "profit,desc" if sort == "profit" else "sellSum,desc"
    params: dict[str, Any] = {
        "momentFrom": _moment(date_from),
        "momentTo": _moment(date_to, end=True),
        "limit": limit,
        "order": order,
    }
    sid = _store_id(args.get("store"))
    if sid:
        params["filter"] = encode_filter([f"store={client.href('store', sid)}"])
    rows, size = client.get_rows("/report/profit/byproduct", params=params)
    items = []
    for row in rows[:limit]:
        brief = _assortment_brief(row)
        items.append(
            {
                **brief,
                "sell_quantity": row.get("sellQuantity"),
                "sell_sum": money_rub(row.get("sellSum")),
                "profit": money_rub(row.get("profit")),
                "margin": row.get("margin"),
                "gender": _gender_from_path(brief.get("path"), brief.get("name")),
            }
        )
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "store": args.get("store") or "antrasha",
        "sort": sort,
        "total_rows": size,
        "items": items,
    }


def _op_stock_snapshot(client: MoySkladAnalyticsClient, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(MAX_TOP_ROWS, max(1, int(args.get("limit") or 20)))
    mode = str(args.get("mode") or "positive").strip().lower()
    sid = _store_id(args.get("store")) or STORE_ANTRASHA_ID
    filters = [f"store={client.href('store', sid)}"]
    if mode in ("positive", "positiveonly", "gt0"):
        filters.append("quantityMode=positiveOnly")
    elif mode in ("low", "underminimum", "under"):
        filters.append("quantityMode=underMinimum")
    params = {
        "filter": encode_filter(filters),
        "limit": limit,
        "order": "stock,asc" if mode in ("low", "underminimum", "under") else "stock,desc",
    }
    rows, size = client.get_rows("/report/stock/all", params=params)
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
        "store": "stock" if sid == STORE_STOCK_ID else "antrasha",
        "mode": mode,
        "total_rows": size,
        "items": items,
    }


def _find_suppliers(client: MoySkladAnalyticsClient, brand: str, gender: str | None) -> list[dict[str, Any]]:
    rows, _ = client.get_rows(
        "/entity/counterparty",
        params={"search": brand, "limit": 50},
    )
    brand_l = brand.casefold()
    out = []
    for row in rows:
        name = str(row.get("name") or "")
        nl = name.casefold()
        if brand_l not in nl and not nl.startswith(brand_l[:4] if len(brand_l) >= 4 else brand_l):
            # soft: still include if search returned it
            pass
        g = None
        if "(жен" in nl or " жен" in nl:
            g = "female"
        elif "(муж" in nl or " муж" in nl:
            g = "male"
        if gender in ("male", "female") and g and g != gender:
            continue
        if gender in ("male", "female") and not g:
            # keep unmarked only for both
            continue
        out.append({"id": row.get("id"), "name": name, "gender": g})
    if gender in ("male", "female") and not out:
        # retry without gender strictness
        for row in rows:
            name = str(row.get("name") or "")
            if brand_l[:3] in name.casefold():
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
    brand = str(args.get("brand") or "").strip()
    if not brand:
        raise ValueError("brand required")
    today = _today()
    season = args.get("season")
    year = args.get("year")
    if season:
        y = int(year or today.year)
        date_from, date_to = season_dates(str(season), y)
        season_meta = {"season": str(season).upper(), "year": y}
    else:
        date_to = _parse_day(args.get("date_to"), default=today)
        date_from = _parse_day(args.get("date_from"), default=date(today.year, today.month, 1))
        season_meta = None
        y = today.year

    gender_s = str(args.get("gender") or "both").strip().lower()
    bp = _op_brand_products(client, {"brand": brand, "gender": gender_s, "limit": MAX_PRODUCTS_BRAND})
    product_ids = {p["id"] for p in bp["products"] if p.get("id")}
    # optional season filter on product names
    if season_meta:
        filtered = [
            p
            for p in bp["products"]
            if matches_season_marker(f"{p.get('name')} {p.get('article')}", str(season), int(season_meta["year"]))
        ]
        if filtered:
            product_ids = {p["id"] for p in filtered if p.get("id")}
            bp["season_filtered_products"] = len(filtered)
        else:
            bp["season_filtered_products"] = 0
            bp["season_note"] = "Маркер сезона в именах не найден — считаем весь ассортимент поставщика за даты сезона."

    # pull profit report and filter
    params: dict[str, Any] = {
        "momentFrom": _moment(date_from),
        "momentTo": _moment(date_to, end=True),
        "limit": 100,
        "order": "sellSum,desc",
    }
    params["filter"] = encode_filter([f"store={client.href('store', STORE_ANTRASHA_ID)}"])
    rows, _ = client.get_rows("/report/profit/byproduct", params=params)
    matched = []
    for row in rows:
        brief = _assortment_brief(row)
        href = brief.get("href") or ""
        pid = None
        m = re.search(
            r"/entity/(?:product|variant)/([0-9a-f-]{36})",
            str(href),
            re.I,
        )
        if m:
            pid = m.group(1).lower()
        # also try nested id
        ass = row.get("assortment") if isinstance(row.get("assortment"), dict) else {}
        if not pid and ass.get("id"):
            pid = str(ass.get("id")).lower()
        if product_ids and pid and pid not in product_ids:
            # variants: check product field
            continue
        if product_ids and not pid:
            continue
        if not product_ids:
            # no products found — empty
            continue
        matched.append(
            {
                **brief,
                "sell_quantity": row.get("sellQuantity"),
                "sell_sum": money_rub(row.get("sellSum")),
                "profit": money_rub(row.get("profit")),
                "product_id": pid,
            }
        )

    # If product_ids filter too strict (variants), fallback: match by supplier name in path — already filtered list
    total_sell = round(sum(x["sell_sum"] or 0 for x in matched), 2)
    total_profit = round(sum(x["profit"] or 0 for x in matched), 2)
    return {
        "brand": brand,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "season": season_meta,
        "suppliers": bp.get("suppliers"),
        "products_in_scope": len(product_ids),
        "matched_sales_rows": len(matched),
        "total_sell_sum": total_sell,
        "total_profit": total_profit,
        "top_items": matched[:20],
        "notes": [
            bp.get("note"),
            bp.get("season_note"),
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
        params={"filter": filt, "limit": 50, "expand": "positions.assortment", "order": "moment,desc"},
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
            "expand": "positions.assortment",
            "order": "moment,desc",
        },
    )

    lines: list[dict[str, Any]] = []

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
                lines.append(
                    {
                        "doc_type": doc_type,
                        "moment": doc.get("moment"),
                        "name": name,
                        "article": ass.get("article"),
                        "quantity": pos.get("quantity"),
                        "sum": money_rub(pos.get("price") and (pos.get("price") * (pos.get("quantity") or 1)) or pos.get("sum")),
                        "size": _size_from_name(name),
                        "gender": _gender_from_path(path, name),
                        "path": path,
                    }
                )

    _consume_docs(rows, "demand")
    _consume_docs(retail_rows, "retaildemand")
    lines = lines[:MAX_PURCHASE_LINES]

    by_gender: dict[str, float] = {}
    by_size: dict[str, float] = {}
    for ln in lines:
        g = ln.get("gender") or "unknown"
        by_gender[g] = round(by_gender.get(g, 0) + (ln.get("sum") or 0), 2)
        sz = ln.get("size") or "unknown"
        by_size[sz] = round(by_size.get(sz, 0) + (ln.get("sum") or 0), 2)

    return {
        "counterparty": cp,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "documents": {"demand": size, "retaildemand": retail_size},
        "lines_count": len(lines),
        "by_gender_sum": by_gender,
        "by_size_sum": by_size,
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
