"""Каталог semantic operations для router (короткие описания)."""

from __future__ import annotations

from typing import Any

OPERATION_CATALOG: list[dict[str, Any]] = [
    {
        "id": "revenue_series",
        "description": (
            "Торговая выручка по дням или месяцам (report sales plotseries). "
            "Args: date_from, date_to (YYYY-MM-DD), interval=day|month."
        ),
    },
    {
        "id": "dashboard_period",
        "description": (
            "KPI дашборда МойСклад: day|week|month. Args: period=day|week|month."
        ),
    },
    {
        "id": "profit_top_products",
        "description": (
            "Топ товаров по выручке/прибыли за период. "
            "Args: date_from, date_to, limit (default 15), store=antrasha|stock|all, sort=sell|profit."
        ),
    },
    {
        "id": "stock_snapshot",
        "description": (
            "Остатки склада. Args: store=antrasha|stock, mode=positive|low, limit (default 20)."
        ),
    },
    {
        "id": "brand_products",
        "description": (
            "Товары бренда (=поставщик counterparty, часто ИМЯ(муж)/ИМЯ(жен)). "
            "Args: brand (строка), gender=male|female|both (optional), limit."
        ),
    },
    {
        "id": "brand_sales",
        "description": (
            "Продажи/маржа бренда-поставщика за период или сезон ВЛ/ОЗ. "
            "Args: brand, date_from, date_to OR season=VL|OZ + year, gender=male|female|both."
        ),
    },
    {
        "id": "top_counterparties",
        "description": (
            "Топ покупателей (контрагентов) по выручке/прибыли за период. "
            "Args: date_from, date_to, limit (default 10)."
        ),
    },
    {
        "id": "customer_purchases",
        "description": (
            "Покупки конкретного контрагента за период с разрезом (размер/пол/поставщик если видно). "
            "Args: counterparty_id OR counterparty_name, date_from, date_to."
        ),
    },
    {
        "id": "open_orders",
        "description": "Открытые заказы покупателей. Args: limit (default 15).",
    },
]


def catalog_for_prompt() -> str:
    lines = []
    for op in OPERATION_CATALOG:
        lines.append(f"- {op['id']}: {op['description']}")
    return "\n".join(lines)


KNOWN_OPERATION_IDS: frozenset[str] = frozenset(op["id"] for op in OPERATION_CATALOG)
