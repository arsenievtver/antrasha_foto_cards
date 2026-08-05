"""Каталог semantic operations + JSON Schema для Anthropic tool-use."""

from __future__ import annotations

from typing import Any

OPERATION_CATALOG: list[dict[str, Any]] = [
    {
        "id": "revenue_series",
        "description": (
            "Торговая выручка магазина по дням/месяцам (отчёт sales plotseries). "
            "Не путать с сырыми отгрузками."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
                "interval": {
                    "type": "string",
                    "enum": ["day", "month", "year"],
                    "description": "Гранулярность ряда",
                },
            },
            "required": ["date_from", "date_to", "interval"],
            "additionalProperties": False,
        },
    },
    {
        "id": "dashboard_period",
        "description": "KPI дашборда МойСклад за день / неделю / месяц.",
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {"type": "string", "enum": ["day", "week", "month"]},
            },
            "required": ["period"],
            "additionalProperties": False,
        },
    },
    {
        "id": "profit_top_products",
        "description": "Топ товаров по выручке или прибыли за период (склад Антраша по умолчанию).",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
                "store": {"type": "string", "enum": ["antrasha", "stock", "all"]},
                "sort": {"type": "string", "enum": ["sell", "profit"]},
            },
            "required": ["date_from", "date_to"],
            "additionalProperties": False,
        },
    },
    {
        "id": "stock_snapshot",
        "description": "Снимок остатков склада (positive или low).",
        "input_schema": {
            "type": "object",
            "properties": {
                "store": {"type": "string", "enum": ["antrasha", "stock"]},
                "mode": {"type": "string", "enum": ["positive", "low"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "required": ["store", "mode"],
            "additionalProperties": False,
        },
    },
    {
        "id": "brand_products",
        "description": (
            "Товары бренда. Бренд в учёте = поставщик (часто ИМЯ(муж)/ИМЯ(жен)), не папка."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "brand": {"type": "string"},
                "gender": {"type": "string", "enum": ["male", "female", "both"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 80},
            },
            "required": ["brand"],
            "additionalProperties": False,
        },
    },
    {
        "id": "brand_sales",
        "description": (
            "Продажи/маржа бренда (=Поставщик) как отчёт Прибыльность: "
            "filter=supplier + период. Сезон ВЛ/ОЗ — коллекция по маркеру или дате в артикуле (/02.26). "
            "В ответе: total_*, by_category, top_items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "brand": {"type": "string", "description": "Имя поставщика/бренда, напр. Roy Robson"},
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "season": {"type": "string", "enum": ["VL", "OZ", "ВЛ", "ОЗ"]},
                "year": {"type": "integer"},
                "gender": {"type": "string", "enum": ["male", "female", "both"]},
                "store": {
                    "type": "string",
                    "enum": ["antrasha", "stock", "all"],
                    "description": "Склад; all = как в UI без фильтра склада",
                },
            },
            "required": ["brand"],
            "additionalProperties": False,
        },
    },
    {
        "id": "top_counterparties",
        "description": (
            "Топ покупателей (контрагентов) по сумме продаж за период. "
            "Сортировка по сумме на бэкенде. В ответе есть best и items[0]=лидер."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "required": ["date_from", "date_to"],
            "additionalProperties": False,
        },
    },
    {
        "id": "customer_purchases",
        "description": (
            "Детализация покупок КОНКРЕТНОГО контрагента. "
            "В ответе: lines с brand/supplier (= поле «Поставщик»), by_brand_sum. "
            "Вызывай ТОЛЬКО с реальным counterparty_id (UUID) из top_counterparties "
            "или с точным именем из вопроса. Никаких placeholder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "counterparty_id": {
                    "type": "string",
                    "description": "UUID контрагента из предыдущего tool result",
                },
                "counterparty_name": {
                    "type": "string",
                    "description": "Имя только если пользователь сам его назвал",
                },
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "id": "open_orders",
        "description": "Открытые заказы покупателей.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 25},
            },
            "additionalProperties": False,
        },
    },
]


def catalog_for_prompt() -> str:
    return "\n".join(f"- {op['id']}: {op['description']}" for op in OPERATION_CATALOG)


KNOWN_OPERATION_IDS: frozenset[str] = frozenset(op["id"] for op in OPERATION_CATALOG)


def anthropic_tools() -> list[dict[str, Any]]:
    """Узкие tools для Messages API (не MCP)."""
    tools = []
    for op in OPERATION_CATALOG:
        tools.append(
            {
                "name": op["id"],
                "description": op["description"],
                "input_schema": op["input_schema"],
            }
        )
    return tools
