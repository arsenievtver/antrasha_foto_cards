"""
Фундамент отчётов МойСклад Remap 1.2.

Опирается на официальную документацию:
https://dev.moysklad.ru/doc/api/remap/1.2/#/reports/report-stock#1-otchety
https://dev.moysklad.ru/doc/api/remap/1.2/#/reports/report-pnl

Правила:
- momentFrom / momentTo — query-параметры (НЕ внутри filter).
- filter — строка `key=value;key2=value2` (href сущностей полностью).
- Прибыльность и остатки поддерживают filter=supplier=…/counterparty/{id}.
- Сезон коллекции (ВЛ/ОЗ) в API прибыльности отдельным фильтром НЕ описан —
  сужаем ответ на нашей стороне (маркер / дата в артикуле).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.services.warehouse_analytics.constants import (
    MAX_BRAND_SALES_PAGES,
    MAX_BRAND_SALES_ROWS,
    MS_API_BASE,
    STORE_ANTRASHA_ID,
    STORE_STOCK_ID,
)
from app.services.warehouse_analytics.ms_client import (
    MoySkladAnalyticsClient,
    encode_filter,
    money_rub,
)

ProfitEndpoint = Literal[
    "byproduct",
    "byvariant",
    "byemployee",
    "bycounterparty",
    "bysaleschannel",
]
StockMode = Literal["all", "positiveOnly", "negativeOnly", "empty", "nonEmpty", "underMinimum"]
QuantityMode = StockMode


def moment(d: date, *, end: bool = False) -> str:
    if end:
        return f"{d.isoformat()} 23:59:59"
    return f"{d.isoformat()} 00:00:00"


def entity_href(entity: str, entity_id: str) -> str:
    return f"{MS_API_BASE}/entity/{entity}/{entity_id}"


def resolve_store_id(store: str | None) -> str | None:
    """antrasha|stock|all|uuid → store id или None (все склады)."""
    if store is None:
        return STORE_ANTRASHA_ID
    key = str(store).strip().lower()
    if key in ("all", "any", "*"):
        return None
    if key in ("antrasha", "антраша", "main", "default"):
        return STORE_ANTRASHA_ID
    if key in ("stock", "сток"):
        return STORE_STOCK_ID
    if len(key) == 36 and key.count("-") == 4:
        return key
    return STORE_ANTRASHA_ID


@dataclass
class ProfitFilters:
    """Фильтры отчёта Прибыльность (документация report-pnl)."""

    supplier_ids: list[str] = field(default_factory=list)
    store_ids: list[str] = field(default_factory=list)
    product_folder_ids: list[str] = field(default_factory=list)
    with_subfolders: bool | None = None
    counterparty_ids: list[str] = field(default_factory=list)
    organization_ids: list[str] = field(default_factory=list)
    retail_store_ids: list[str] = field(default_factory=list)
    project_ids: list[str] = field(default_factory=list)
    sales_channel_ids: list[str] = field(default_factory=list)
    product_hrefs: list[str] = field(default_factory=list)
    entity_type: str | None = None  # demand | retailDemand | …
    agent_tag: str | None = None

    def to_parts(self) -> list[str]:
        parts: list[str] = []
        for sid in self.supplier_ids:
            parts.append(f"supplier={entity_href('counterparty', sid)}")
        for sid in self.store_ids:
            parts.append(f"store={entity_href('store', sid)}")
        for fid in self.product_folder_ids:
            parts.append(f"productFolder={entity_href('productfolder', fid)}")
        if self.product_folder_ids and self.with_subfolders is not None:
            parts.append(f"withSubFolders={'true' if self.with_subfolders else 'false'}")
        for cid in self.counterparty_ids:
            parts.append(f"counterparty={entity_href('counterparty', cid)}")
        for oid in self.organization_ids:
            parts.append(f"organization={entity_href('organization', oid)}")
        for rid in self.retail_store_ids:
            parts.append(f"retailStore={entity_href('retailstore', rid)}")
        for pid in self.project_ids:
            parts.append(f"project={entity_href('project', pid)}")
        for sc in self.sales_channel_ids:
            parts.append(f"salesChannel={entity_href('saleschannel', sc)}")
        for href in self.product_hrefs:
            parts.append(f"product={href}")
        if self.entity_type:
            parts.append(f"entityType={self.entity_type}")
        if self.agent_tag:
            parts.append(f"agentTag={self.agent_tag}")
        return parts


@dataclass
class StockFilters:
    """Фильтры отчёта Остатки (документация report-stock)."""

    supplier_ids: list[str] = field(default_factory=list)
    store_ids: list[str] = field(default_factory=list)
    product_folder_ids: list[str] = field(default_factory=list)
    with_subfolders: bool | None = None
    stock_mode: StockMode | None = None
    quantity_mode: QuantityMode | None = None
    search: str | None = None
    archived: bool | None = None
    reserve_only: bool | None = None
    in_transit_only: bool | None = None

    def to_parts(self) -> list[str]:
        parts: list[str] = []
        for sid in self.supplier_ids:
            parts.append(f"supplier={entity_href('counterparty', sid)}")
        for sid in self.store_ids:
            parts.append(f"store={entity_href('store', sid)}")
        for fid in self.product_folder_ids:
            parts.append(f"productFolder={entity_href('productfolder', fid)}")
        if self.product_folder_ids and self.with_subfolders is not None:
            parts.append(f"withSubFolders={'true' if self.with_subfolders else 'false'}")
        if self.stock_mode:
            parts.append(f"stockMode={self.stock_mode}")
        if self.quantity_mode:
            parts.append(f"quantityMode={self.quantity_mode}")
        if self.search:
            parts.append(f"search={self.search}")
        if self.archived is not None:
            parts.append(f"archived={'true' if self.archived else 'false'}")
        if self.reserve_only:
            parts.append("reserveOnly=true")
        if self.in_transit_only:
            parts.append("inTransitOnly=true")
        return parts


def fetch_profit_rows(
    client: MoySkladAnalyticsClient,
    *,
    date_from: date,
    date_to: date,
    filters: ProfitFilters | None = None,
    endpoint: ProfitEndpoint = "byproduct",
    limit: int = MAX_BRAND_SALES_ROWS,
    max_pages: int = MAX_BRAND_SALES_PAGES,
) -> tuple[list[dict[str, Any]], int]:
    """
    GET /report/profit/{endpoint}
    momentFrom/momentTo — отдельно; filter — documented fields incl. supplier.
    """
    path = f"/report/profit/{endpoint}"
    filt = encode_filter((filters or ProfitFilters()).to_parts())
    rows: list[dict[str, Any]] = []
    offset = 0
    total = 0
    page_limit = max(1, min(1000, int(limit)))
    for _ in range(max(1, max_pages)):
        params: dict[str, Any] = {
            "momentFrom": moment(date_from),
            "momentTo": moment(date_to, end=True),
            "limit": page_limit,
            "offset": offset,
        }
        if filt:
            params["filter"] = filt
        batch, size = client.get_rows(path, params=params)
        total = size
        rows.extend(batch)
        offset += len(batch)
        if not batch or offset >= size:
            break
    return rows, total


def fetch_stock_rows(
    client: MoySkladAnalyticsClient,
    *,
    filters: StockFilters | None = None,
    group_by: Literal["product", "variant", "consignment"] = "product",
    limit: int = 100,
    offset: int = 0,
    order: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """GET /report/stock/all — в т.ч. filter=supplier."""
    params: dict[str, Any] = {
        "limit": max(1, min(1000, int(limit))),
        "offset": max(0, int(offset)),
        "groupBy": group_by,
    }
    filt = encode_filter((filters or StockFilters()).to_parts())
    if filt:
        params["filter"] = filt
    if order:
        params["order"] = order
    return client.get_rows("/report/stock/all", params=params)


def fetch_sales_plotseries(
    client: MoySkladAnalyticsClient,
    *,
    date_from: date,
    date_to: date,
    interval: Literal["hour", "day", "month"] = "day",
    store_id: str | None = None,
    retail_store_id: str | None = None,
) -> dict[str, Any]:
    """GET /report/sales/plotseries."""
    params: dict[str, Any] = {
        "momentFrom": moment(date_from),
        "momentTo": moment(date_to, end=True),
        "interval": interval,
    }
    parts: list[str] = []
    if store_id:
        parts.append(f"store={entity_href('store', store_id)}")
    if retail_store_id:
        parts.append(f"retailStore={entity_href('retailstore', retail_store_id)}")
    if parts:
        params["filter"] = encode_filter(parts)
    data = client.get("/report/sales/plotseries", params=params)
    return data if isinstance(data, dict) else {}


def fetch_dashboard(client: MoySkladAnalyticsClient, period: Literal["day", "week", "month"]) -> dict[str, Any]:
    data = client.get(f"/report/dashboard/{period}")
    return data if isinstance(data, dict) else {}


def normalize_profit_row(row: dict[str, Any]) -> dict[str, Any]:
    """Строка profit/byproduct → компактный dict в рублях."""
    ass = row.get("assortment") if isinstance(row.get("assortment"), dict) else {}
    name = ass.get("name") if ass else row.get("name")
    article = ass.get("article") if ass else (row.get("article") or row.get("code"))
    path = ass.get("pathName") if ass else row.get("pathName")
    meta = ass.get("meta") if isinstance(ass.get("meta"), dict) else {}
    href = meta.get("href")
    pid = None
    if href:
        import re

        m = re.search(r"/entity/(?:product|variant)/([0-9a-f-]{36})", str(href), re.I)
        if m:
            pid = m.group(1).lower()
    if not pid and ass.get("id"):
        pid = str(ass["id"]).lower()
    return {
        "name": name,
        "article": article,
        "path": path,
        "href": href,
        "product_id": pid,
        "sell_quantity": row.get("sellQuantity") or 0,
        "sell_sum": money_rub(row.get("sellSum")),
        "sell_cost_sum": money_rub(row.get("sellCostSum")),
        "profit": money_rub(row.get("profit")),
        "return_quantity": row.get("returnQuantity") or 0,
        "return_sum": money_rub(row.get("returnSum")),
    }
