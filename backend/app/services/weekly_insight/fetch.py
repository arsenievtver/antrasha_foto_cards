"""Выгрузка из МойСклад Remap 1.2 в плоские записи для недельной аналитики.

Суммы API — в копейках, здесь переводятся в рубли. Около 70–100 запросов на прогон.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.warehouse_analytics.ms_client import MoySkladAnalyticsClient, MoySkladAnalyticsError
from app.services.weekly_insight.parse import (
    CERTIFICATE_TOP_FOLDERS,
    base_name,
    brand_key,
    category_of,
    gender_of,
    size_of,
)

log = logging.getLogger("app.weekly_insight.fetch")

_ID_RE = re.compile(r"/entity/(product|variant|service|bundle|counterparty)/([0-9a-f-]{36})", re.I)
_RETRIES_429 = 6
_PAUSE_SEC = 0.12


@dataclass
class Dataset:
    catalog: dict[str, dict] = field(default_factory=dict)
    sales: list[dict] = field(default_factory=list)
    arrivals: list[dict] = field(default_factory=list)
    stock: list[dict] = field(default_factory=list)
    stock_cost_on: dict[str, float] = field(default_factory=dict)
    profit: dict[str, dict[str, float]] = field(default_factory=dict)


def href_id(obj: Any) -> tuple[str | None, str | None]:
    """(тип, id) из meta.href сущности."""
    if not isinstance(obj, dict):
        return None, None
    meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
    m = _ID_RE.search(str(meta.get("href") or ""))
    if not m:
        return None, None
    return m.group(1).lower(), m.group(2).lower()


def _moment(d: date, end: bool = False) -> str:
    return f"{d.isoformat()} {'23:59:59' if end else '00:00:00'}"


def _rub(v: Any) -> float:
    try:
        return float(v or 0) / 100.0
    except (TypeError, ValueError):
        return 0.0


def _nested_rows(value: Any) -> tuple[list[dict], int]:
    """positions в ответе списка: {meta: {size}, rows: [...]} или уже список."""
    if isinstance(value, list):
        return [r for r in value if isinstance(r, dict)], len(value)
    if isinstance(value, dict):
        rows = value.get("rows") if isinstance(value.get("rows"), list) else []
        meta = value.get("meta") if isinstance(value.get("meta"), dict) else {}
        return [r for r in rows if isinstance(r, dict)], int(meta.get("size") or len(rows))
    return [], 0


class MsFetcher:
    def __init__(self, client: MoySkladAnalyticsClient) -> None:
        self.client = client
        self.requests = 0

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        for attempt in range(_RETRIES_429 + 1):
            try:
                self.requests += 1
                data = self.client.get(path, params=params)
                time.sleep(_PAUSE_SEC)
                return data
            except MoySkladAnalyticsError as e:
                if e.status != 429 or attempt == _RETRIES_429:
                    raise
                time.sleep(3.0 * (attempt + 1))
        raise RuntimeError("unreachable")

    def rows_all(self, path: str, params: dict[str, Any], *, page: int = 1000, max_pages: int = 300) -> list[dict]:
        out: list[dict] = []
        offset = 0
        for _ in range(max_pages):
            data = self._get(path, {**params, "limit": page, "offset": offset})
            rows = data.get("rows") if isinstance(data, dict) else None
            rows = [r for r in rows or [] if isinstance(r, dict)]
            out.extend(rows)
            meta = data.get("meta") if isinstance(data, dict) and isinstance(data.get("meta"), dict) else {}
            size = int(meta.get("size") or 0)
            offset += len(rows)
            if not rows or offset >= size:
                break
        return out

    # ---------- справочники ----------

    def catalog(self) -> dict[str, dict]:
        products = self.rows_all("/entity/product", {"filter": "archived=true;archived=false"})
        supplier_ids = sorted({sid for p in products if (sid := href_id(p.get("supplier"))[1])})
        suppliers: dict[str, str] = {}
        for i in range(0, len(supplier_ids), 40):
            chunk = supplier_ids[i : i + 40]
            rows = self.rows_all("/entity/counterparty", {"filter": ";".join(f"id={s}" for s in chunk)}, page=100)
            for r in rows:
                suppliers[str(r.get("id")).lower()] = str(r.get("name") or "")
        catalog = {}
        for p in products:
            path = str(p.get("pathName") or "")
            catalog[str(p["id"]).lower()] = {
                "name": str(p.get("name") or "").strip(),
                "article": p.get("article"),
                "path": path,
                "top": path.split("/")[0] if path else "",
                "gender": gender_of(path),
                "category": category_of(path),
                "brand": brand_key(suppliers.get(href_id(p.get("supplier"))[1] or "")),
            }
        return catalog

    # ---------- документы ----------

    def _documents(self, entity: str, date_from: date, date_to: date, expand: str) -> list[dict]:
        docs = self.rows_all(
            f"/entity/{entity}",
            {
                "filter": f"moment>={_moment(date_from)};moment<={_moment(date_to, end=True)}",
                "expand": expand,
                "order": "moment,asc",
            },
            page=100,
        )
        for d in docs:
            rows, size = _nested_rows(d.get("positions"))
            if size > len(rows):
                rows = self.rows_all(f"/entity/{entity}/{d['id']}/positions", {"expand": "assortment"}, page=1000)
            d["_positions"] = rows
        return [d for d in docs if d.get("applicable", True)]

    @staticmethod
    def _product_of(assortment: dict, catalog: dict[str, dict], by_name: dict[str, str]) -> tuple[str | None, str | None]:
        """(variant_key, product_id) позиции."""
        kind, own_id = href_id(assortment)
        own_id = own_id or (str(assortment.get("id")).lower() if assortment.get("id") else None)
        if kind == "variant":
            _, pid = href_id(assortment.get("product"))
            return own_id, pid or by_name.get(base_name(assortment.get("name")))
        if own_id in catalog:
            return own_id, own_id
        return own_id, by_name.get(base_name(assortment.get("name")))

    def sales(self, date_from: date, date_to: date, catalog: dict[str, dict]) -> list[dict]:
        by_name = _by_name(catalog)
        lines = []
        for doc in self._documents("retaildemand", date_from, date_to, "positions.assortment,agent"):
            agent = doc.get("agent") if isinstance(doc.get("agent"), dict) else {}
            for pos in doc["_positions"]:
                ass = pos.get("assortment") if isinstance(pos.get("assortment"), dict) else {}
                vkey, pid = self._product_of(ass, catalog, by_name)
                if (catalog.get(pid) or {}).get("top") in CERTIFICATE_TOP_FOLDERS:
                    continue
                qty = float(pos.get("quantity") or 0)
                price = _rub(pos.get("price"))
                disc = float(pos.get("discount") or 0)
                lines.append(
                    {
                        "check_id": doc.get("id"),
                        "day": str(doc.get("moment") or "")[:10],
                        "agent_id": str(agent.get("id") or "").lower() or None,
                        "agent_name": agent.get("name"),
                        "agent_phone": agent.get("phone"),
                        "product_id": pid,
                        "variant_key": vkey,
                        "variant_name": ass.get("name"),
                        "size": size_of(ass.get("name"), ass.get("characteristics")),
                        "qty": qty,
                        "list_price": price,
                        "discount_pct": disc,
                        "sum": round(qty * price * (1 - disc / 100), 2),
                    }
                )
        return lines

    def arrivals(self, date_from: date, date_to: date, catalog: dict[str, dict]) -> list[dict]:
        by_name = _by_name(catalog)
        rows = []
        for entity in ("enter", "supply"):
            for doc in self._documents(entity, date_from, date_to, "positions.assortment"):
                for pos in doc["_positions"]:
                    ass = pos.get("assortment") if isinstance(pos.get("assortment"), dict) else {}
                    vkey, pid = self._product_of(ass, catalog, by_name)
                    rows.append(
                        {
                            "day": str(doc.get("moment") or "")[:10],
                            "variant_key": vkey,
                            "variant_name": ass.get("name"),
                            "product_id": pid,
                            "size": size_of(ass.get("name"), ass.get("characteristics")),
                            "qty": float(pos.get("quantity") or 0),
                            "cost": _rub(pos.get("price")),
                        }
                    )
        return rows

    # ---------- отчёты ----------

    def stock_variants(self, catalog: dict[str, dict], known: dict[str, str]) -> list[dict]:
        """known: variant_key → product_id из чеков и приходов."""
        by_name = _by_name(catalog)
        rows = self.rows_all("/report/stock/all", {"groupBy": "variant", "filter": "stockMode=positiveOnly"})
        out = []
        for r in rows:
            kind, vid = href_id(r)
            pid = vid if kind == "product" else known.get(vid or "") or by_name.get(base_name(r.get("name")))
            out.append(
                {
                    "variant_key": vid,
                    "name": r.get("name"),
                    "product_id": pid,
                    "size": size_of(r.get("name")),
                    "stock": float(r.get("stock") or 0),
                    "cost": _rub(r.get("price")),
                    "sale_price": _rub(r.get("salePrice")),
                }
            )
        return out

    def stock_cost_on(self, on: date) -> float:
        rows = self.rows_all(
            "/report/stock/all",
            {"groupBy": "product", "filter": f"stockMode=positiveOnly;moment={_moment(on, end=True)}"},
        )
        return round(sum(float(r.get("stock") or 0) * _rub(r.get("price")) for r in rows), 2)

    def profit(self, date_from: date, date_to: date) -> dict[str, float]:
        """Себестоимость и выручка за вычетом возвратов — все каналы, включая сертификаты."""
        rows = self.rows_all(
            "/report/profit/byproduct",
            {"momentFrom": _moment(date_from), "momentTo": _moment(date_to, end=True)},
        )
        return {
            "cogs": round(sum(_rub(r.get("sellCostSum")) - _rub(r.get("returnCostSum")) for r in rows), 2),
            "revenue": round(sum(_rub(r.get("sellSum")) - _rub(r.get("returnSum")) for r in rows), 2),
        }


def _by_name(catalog: dict[str, dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pid, c in catalog.items():
        out.setdefault(c["name"], pid)
    return out


def load_dataset(client: MoySkladAnalyticsClient, *, today: date, history_from: date, windows: dict[str, tuple[date, date]], stock_dates: list[date]) -> tuple[Dataset, int]:
    f = MsFetcher(client)
    ds = Dataset()
    ds.catalog = f.catalog()
    log.info("weekly_insight: catalog %s", len(ds.catalog))
    ds.sales = f.sales(history_from, today, ds.catalog)
    log.info("weekly_insight: sales lines %s", len(ds.sales))
    ds.arrivals = f.arrivals(history_from, today, ds.catalog)
    log.info("weekly_insight: arrival lines %s", len(ds.arrivals))
    known = {r["variant_key"]: r["product_id"] for r in ds.sales + ds.arrivals if r["variant_key"] and r["product_id"]}
    ds.stock = f.stock_variants(ds.catalog, known)
    for d in stock_dates:
        ds.stock_cost_on[d.isoformat()] = f.stock_cost_on(d)
    for name, (a, b) in windows.items():
        ds.profit[name] = f.profit(a, b)
    return ds, f.requests
