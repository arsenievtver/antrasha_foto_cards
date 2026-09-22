"""Инструменты MCP закупок.

Пишут и читают через те же функции, что админка, поэтому проверки курса,
предоплаты и совпадения сезона с заказом не расходятся. Удаления нет.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.deps import AdminPrincipal
from app.mcp_procurement.registry import SCOPE_WRITE, ToolArgumentError, check_limit, tool
from app.routers import admin as admin_router
from app.routers import admin_procurement as procurement
from app.schemas.admin import AdminBrandCreateRequest, AdminBrandUpdateRequest
from app.schemas.procurement import (
    FxRateCreateRequest,
    FxRateUpdateRequest,
    OrderCreateRequest,
    OrderUpdateRequest,
    PaymentCreateRequest,
    PaymentUpdateRequest,
    SeasonCreateRequest,
    SeasonUpdateRequest,
    ShipmentCreateRequest,
    ShipmentUpdateRequest,
)
from app.services.mcp_keys import McpActor

# Эндпоинты админки проверяют право до входа в функцию. Сюда попадает уже
# проверенный ключ, а сами функции principal только принимают и не читают.
_PRODUCT = AdminPrincipal(role="superuser", user=None)

_UUID = {"type": "string", "format": "uuid"}
_DATE = {"type": "string", "format": "date"}
_MONEY = {"type": "number"}
_GENDER = {
    "type": "string",
    "enum": ["men", "women", "mixed"],
    "description": "men, women или mixed",
}


def _dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, str):
        return detail
    return str(detail)


def _body(model, data: dict):
    # null в аргументах — то же, что поле не передали: админка так и трактует
    # отсутствие значения, а bool-флаги вроде clear_order null не принимают.
    cleaned = {key: value for key, value in data.items() if value is not None}
    try:
        return model.model_validate(cleaned)
    except ValidationError as exc:
        parts = []
        for err in exc.errors():
            loc = ".".join(str(item) for item in err["loc"]) or "body"
            parts.append(f"{loc}: {err['msg']}")
        raise ToolArgumentError("; ".join(parts)) from exc


def _uuid(value: str, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise ToolArgumentError(f"{name} должен быть UUID") from exc


def _optional_uuid(value: str | None, name: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return _uuid(value, name)


def _run(db: Session, fn, *args, principal_arg: str = "_su", **kwargs):
    kwargs["db"] = db
    kwargs[principal_arg] = _PRODUCT
    try:
        return _dump(fn(*args, **kwargs))
    except HTTPException as exc:
        db.rollback()
        raise ToolArgumentError(_detail(exc)) from exc


def _skip(skip: int) -> int:
    if isinstance(skip, bool) or not isinstance(skip, int) or skip < 0:
        raise ToolArgumentError("skip должен быть целым >= 0")
    return skip


# --- Сезоны ----------------------------------------------------------------


@tool(
    "list_seasons",
    "Все сезоны закупок: название, код, активность, показ на PWA (is_primary), "
    "сезон «Для заказа» (is_order_plan) и sort_order. Список полный.",
    {"type": "object", "properties": {}, "required": []},
)
def list_seasons(db: Session, _actor: McpActor):
    return _run(db, procurement.list_seasons)


@tool(
    "create_season",
    "Создать сезон. name и code уникальны. is_order_plan=true снимет этот флаг "
    "с другого сезона: такой сезон может быть только один. Удалить сезон этим "
    "инструментом нельзя.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Например «Весна-Лето 2027»"},
            "code": {"type": "string", "description": "Короткий код, например ВЛ2027"},
            "is_active": {"type": "boolean"},
            "is_primary": {
                "type": "boolean",
                "description": "Показывать на дашборде PWA",
            },
            "is_order_plan": {
                "type": "boolean",
                "description": "Сезон раздела «Для заказа». Только один.",
            },
            "sort_order": {"type": "integer", "description": "Больше — выше в списках"},
        },
        "required": ["name", "code"],
    },
    scope=SCOPE_WRITE,
)
def create_season(db: Session, _actor: McpActor, **fields):
    return _run(db, procurement.create_season, _body(SeasonCreateRequest, fields))


@tool(
    "update_season",
    "Изменить сезон. Передавайте только поля, которые нужно поменять. "
    "is_order_plan=true перенесёт флаг с прежнего сезона. Удаления нет.",
    {
        "type": "object",
        "properties": {
            "season_id": {**_UUID, "description": "id сезона"},
            "name": {"type": "string"},
            "code": {"type": "string"},
            "is_active": {"type": "boolean"},
            "is_primary": {"type": "boolean"},
            "is_order_plan": {"type": "boolean"},
            "sort_order": {"type": "integer"},
        },
        "required": ["season_id"],
    },
    scope=SCOPE_WRITE,
)
def update_season(db: Session, _actor: McpActor, season_id: str, **fields):
    return _run(
        db,
        procurement.update_season,
        _uuid(season_id, "season_id"),
        _body(SeasonUpdateRequest, fields),
    )


# --- Бренды ----------------------------------------------------------------


@tool(
    "list_brands",
    "Все бренды закупок: id и название. Список полный, по имени.",
    {"type": "object", "properties": {}, "required": []},
)
def list_brands(db: Session, _actor: McpActor):
    return _run(db, admin_router.list_brands, principal_arg="_principal")


@tool(
    "create_brand",
    "Создать бренд. Название уникально. Удалить бренд этим инструментом нельзя.",
    {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Название бренда"},
        },
        "required": ["name"],
    },
    scope=SCOPE_WRITE,
)
def create_brand(db: Session, _actor: McpActor, **fields):
    return _run(
        db,
        admin_router.create_brand,
        _body(AdminBrandCreateRequest, fields),
        principal_arg="_principal",
    )


@tool(
    "update_brand",
    "Переименовать бренд. Название на уже загруженных фото обновится вместе с ним. "
    "Удаления нет.",
    {
        "type": "object",
        "properties": {
            "brand_id": {**_UUID, "description": "id бренда"},
            "name": {"type": "string"},
        },
        "required": ["brand_id", "name"],
    },
    scope=SCOPE_WRITE,
)
def update_brand(db: Session, _actor: McpActor, brand_id: str, **fields):
    return _run(
        db,
        admin_router.update_brand,
        _uuid(brand_id, "brand_id"),
        _body(AdminBrandUpdateRequest, fields),
        principal_arg="_principal",
    )


# --- Категории (справочник для строк заказа) ------------------------------


@tool(
    "list_categories",
    "Закупочные категории для строк заказа. Берите id отсюда. "
    "gender: men, women или unisex. active_only=true оставит только активные.",
    {
        "type": "object",
        "properties": {
            "gender": {
                "type": "string",
                "enum": ["men", "women", "unisex"],
            },
            "active_only": {"type": "boolean"},
        },
        "required": [],
    },
)
def list_categories(
    db: Session,
    _actor: McpActor,
    gender: str | None = None,
    active_only: bool = False,
):
    if gender is not None and gender not in ("men", "women", "unisex"):
        raise ToolArgumentError("gender: men, women или unisex")
    return _run(
        db,
        procurement.list_categories,
        gender=gender,
        active_only=bool(active_only),
    )


# --- Заказы ----------------------------------------------------------------


@tool(
    "list_brand_orders",
    "Заказы брендам. В каждой строке суммы заказа, оплат, предоплат, поставок "
    "и остатки balance_to_pay_eur / balance_to_ship_eur. Фильтры необязательны. "
    "Ответ содержит total — если shown меньше, поднимите skip.",
    {
        "type": "object",
        "properties": {
            "season_id": _UUID,
            "brand_id": _UUID,
            "gender": _GENDER,
            "skip": {"type": "integer"},
            "limit": {"type": "integer", "description": "1–200, по умолчанию 50"},
        },
        "required": [],
    },
)
def list_brand_orders(
    db: Session,
    _actor: McpActor,
    season_id: str | None = None,
    brand_id: str | None = None,
    gender: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    if gender is not None and gender not in ("men", "women", "mixed"):
        raise ToolArgumentError("gender: men, women или mixed")
    return _run(
        db,
        procurement.list_brand_orders,
        season_id=_optional_uuid(season_id, "season_id"),
        brand_id=_optional_uuid(brand_id, "brand_id"),
        gender=gender,
        skip=_skip(skip),
        limit=check_limit(limit),
    )


@tool(
    "get_brand_order",
    "Один заказ со строками категорий и фактом оплат и поставок.",
    {
        "type": "object",
        "properties": {"order_id": _UUID},
        "required": ["order_id"],
    },
)
def get_brand_order(db: Session, _actor: McpActor, order_id: str):
    return _run(db, procurement.get_brand_order, _uuid(order_id, "order_id"))


@tool(
    "create_brand_order",
    "Создать заказ бренду на сезон. Либо amount_eur, либо lines с category_id — "
    "если есть строки, сумма заказа считается по ним. Курс можно не передавать: "
    "подставится справочник на ordered_on или на сегодня. "
    "Предоплата здесь — план (has_prepayment, prepayment_amount_eur, "
    "prepayment_due_on). Факт оплаты — отдельный инструмент create_payment "
    "с kind=prepayment. Удалить заказ нельзя.",
    {
        "type": "object",
        "properties": {
            "season_id": _UUID,
            "brand_id": _UUID,
            "gender": _GENDER,
            "ordered_on": _DATE,
            "amount_eur": _MONEY,
            "eur_rub_rate": {"type": "number", "description": "Если пусто — курс из справочника"},
            "has_prepayment": {"type": "boolean"},
            "prepayment_amount_eur": _MONEY,
            "prepayment_due_on": _DATE,
            "comment": {"type": "string"},
            "lines": {
                "type": "array",
                "description": "Строки по категориям. Сумма заказа станет их суммой.",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_id": _UUID,
                        "amount_eur": _MONEY,
                        "comment": {"type": "string"},
                    },
                    "required": ["category_id", "amount_eur"],
                },
            },
        },
        "required": ["season_id", "brand_id"],
    },
    scope=SCOPE_WRITE,
)
def create_brand_order(db: Session, _actor: McpActor, **fields):
    return _run(db, procurement.create_brand_order, _body(OrderCreateRequest, fields))


@tool(
    "update_brand_order",
    "Изменить заказ. Передавайте только нужные поля. Если передан lines, строки "
    "заменяются целиком, а сумма пересчитывается. Пустой lines требует amount_eur. "
    "Удаления нет.",
    {
        "type": "object",
        "properties": {
            "order_id": _UUID,
            "season_id": _UUID,
            "brand_id": _UUID,
            "gender": _GENDER,
            "ordered_on": _DATE,
            "amount_eur": _MONEY,
            "eur_rub_rate": {"type": "number"},
            "has_prepayment": {"type": "boolean"},
            "prepayment_amount_eur": _MONEY,
            "prepayment_due_on": _DATE,
            "comment": {"type": "string"},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category_id": _UUID,
                        "amount_eur": _MONEY,
                        "comment": {"type": "string"},
                    },
                    "required": ["category_id", "amount_eur"],
                },
            },
        },
        "required": ["order_id"],
    },
    scope=SCOPE_WRITE,
)
def update_brand_order(db: Session, _actor: McpActor, order_id: str, **fields):
    return _run(
        db,
        procurement.update_brand_order,
        _uuid(order_id, "order_id"),
        _body(OrderUpdateRequest, fields),
    )


# --- Оплаты ----------------------------------------------------------------


@tool(
    "list_payments",
    "Оплаты брендам. kind: prepayment или main. amount_rub посчитан по курсу "
    "документа. Фильтры необязательны.",
    {
        "type": "object",
        "properties": {
            "season_id": _UUID,
            "brand_id": _UUID,
            "order_id": _UUID,
            "kind": {"type": "string", "enum": ["prepayment", "main"]},
            "skip": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": [],
    },
)
def list_payments(
    db: Session,
    _actor: McpActor,
    season_id: str | None = None,
    brand_id: str | None = None,
    order_id: str | None = None,
    kind: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    if kind is not None and kind not in ("prepayment", "main"):
        raise ToolArgumentError("kind: prepayment или main")
    return _run(
        db,
        procurement.list_payments,
        season_id=_optional_uuid(season_id, "season_id"),
        brand_id=_optional_uuid(brand_id, "brand_id"),
        order_id=_optional_uuid(order_id, "order_id"),
        kind=kind,
        skip=_skip(skip),
        limit=check_limit(limit),
    )


@tool(
    "get_payment",
    "Одна оплата бренду.",
    {
        "type": "object",
        "properties": {"payment_id": _UUID},
        "required": ["payment_id"],
    },
)
def get_payment(db: Session, _actor: McpActor, payment_id: str):
    return _run(db, procurement.get_payment, _uuid(payment_id, "payment_id"))


@tool(
    "create_payment",
    "Записать оплату бренду. kind=prepayment — факт предоплаты, kind=main — "
    "основная оплата. season_id и brand_id обязательны. Если указан order_id, "
    "сезон и бренд должны совпасть с заказом. Курс можно не передавать. "
    "Удалить оплату нельзя.",
    {
        "type": "object",
        "properties": {
            "order_id": _UUID,
            "season_id": _UUID,
            "brand_id": _UUID,
            "paid_on": _DATE,
            "kind": {"type": "string", "enum": ["prepayment", "main"]},
            "amount_eur": _MONEY,
            "eur_rub_rate": {"type": "number"},
            "comment": {"type": "string"},
        },
        "required": ["season_id", "brand_id", "paid_on", "amount_eur"],
    },
    scope=SCOPE_WRITE,
)
def create_payment(db: Session, _actor: McpActor, **fields):
    return _run(db, procurement.create_payment, _body(PaymentCreateRequest, fields))


@tool(
    "update_payment",
    "Изменить оплату. Передавайте только нужные поля. clear_order=true отвяжет "
    "оплату от заказа. Рубли пересчитаются по текущим сумме и курсу. Удаления нет.",
    {
        "type": "object",
        "properties": {
            "payment_id": _UUID,
            "order_id": _UUID,
            "season_id": _UUID,
            "brand_id": _UUID,
            "paid_on": _DATE,
            "kind": {"type": "string", "enum": ["prepayment", "main"]},
            "amount_eur": _MONEY,
            "eur_rub_rate": {"type": "number"},
            "comment": {"type": "string"},
            "clear_order": {"type": "boolean"},
        },
        "required": ["payment_id"],
    },
    scope=SCOPE_WRITE,
)
def update_payment(db: Session, _actor: McpActor, payment_id: str, **fields):
    return _run(
        db,
        procurement.update_payment,
        _uuid(payment_id, "payment_id"),
        _body(PaymentUpdateRequest, fields),
    )


# --- Поставки --------------------------------------------------------------


@tool(
    "list_shipments",
    "Поставки от брендов: сумма в евро, вес, курс, рубли, логистика и "
    "is_delivered. В пути (is_delivered=false) не входит в отгруженное по заказу.",
    {
        "type": "object",
        "properties": {
            "season_id": _UUID,
            "brand_id": _UUID,
            "order_id": _UUID,
            "skip": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": [],
    },
)
def list_shipments(
    db: Session,
    _actor: McpActor,
    season_id: str | None = None,
    brand_id: str | None = None,
    order_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    return _run(
        db,
        procurement.list_shipments,
        season_id=_optional_uuid(season_id, "season_id"),
        brand_id=_optional_uuid(brand_id, "brand_id"),
        order_id=_optional_uuid(order_id, "order_id"),
        skip=_skip(skip),
        limit=check_limit(limit),
    )


@tool(
    "get_shipment",
    "Одна поставка.",
    {
        "type": "object",
        "properties": {"shipment_id": _UUID},
        "required": ["shipment_id"],
    },
)
def get_shipment(db: Session, _actor: McpActor, shipment_id: str):
    return _run(db, procurement.get_shipment, _uuid(shipment_id, "shipment_id"))


@tool(
    "create_shipment",
    "Создать поставку. season_id, brand_id, shipped_on и amount_eur обязательны. "
    "order_id необязателен и должен совпасть по сезону и бренду. "
    "is_delivered по умолчанию true. logistics_amount_rub и logistics_paid_on — "
    "оплата логистики в рублях, отдельно от оплаты бренду. Курс можно не передавать. "
    "Удалить поставку нельзя.",
    {
        "type": "object",
        "properties": {
            "order_id": _UUID,
            "season_id": _UUID,
            "brand_id": _UUID,
            "shipped_on": _DATE,
            "amount_eur": _MONEY,
            "weight_kg": {"type": "number"},
            "eur_rub_rate": {"type": "number"},
            "comment": {"type": "string"},
            "logistics_amount_rub": {"type": "number"},
            "logistics_paid_on": _DATE,
            "is_delivered": {"type": "boolean"},
        },
        "required": ["season_id", "brand_id", "shipped_on", "amount_eur"],
    },
    scope=SCOPE_WRITE,
)
def create_shipment(db: Session, _actor: McpActor, **fields):
    return _run(db, procurement.create_shipment, _body(ShipmentCreateRequest, fields))


@tool(
    "update_shipment",
    "Изменить поставку. Передавайте только нужные поля. clear_order=true отвяжет "
    "поставку от заказа. Рубли пересчитаются. Удаления нет.",
    {
        "type": "object",
        "properties": {
            "shipment_id": _UUID,
            "order_id": _UUID,
            "season_id": _UUID,
            "brand_id": _UUID,
            "shipped_on": _DATE,
            "amount_eur": _MONEY,
            "weight_kg": {"type": "number"},
            "eur_rub_rate": {"type": "number"},
            "comment": {"type": "string"},
            "logistics_amount_rub": {"type": "number"},
            "logistics_paid_on": _DATE,
            "is_delivered": {"type": "boolean"},
            "clear_order": {"type": "boolean"},
        },
        "required": ["shipment_id"],
    },
    scope=SCOPE_WRITE,
)
def update_shipment(db: Session, _actor: McpActor, shipment_id: str, **fields):
    return _run(
        db,
        procurement.update_shipment,
        _uuid(shipment_id, "shipment_id"),
        _body(ShipmentUpdateRequest, fields),
    )


# --- Курс EUR --------------------------------------------------------------


@tool(
    "list_fx_rates",
    "Справочник курса EUR/RUB, новые периоды сверху. valid_to=null — бессрочно "
    "с valid_from. Периоды не пересекаются. Это курс по умолчанию для новых "
    "документов, уже записанные оплаты и поставки он не пересчитывает.",
    {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "1–500, по умолчанию 100"},
        },
        "required": [],
    },
)
def list_fx_rates(db: Session, _actor: McpActor, limit: int = 100):
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 500:
        raise ToolArgumentError("limit должен быть от 1 до 500")
    return _run(db, procurement.list_fx_rates, limit=limit)


@tool(
    "create_fx_rate",
    "Новый курс EUR/RUB на период. valid_to можно не передавать — тогда период "
    "бессрочный. Пересечение с уже заданным периодом отклоняется. Удалить курс нельзя.",
    {
        "type": "object",
        "properties": {
            "valid_from": _DATE,
            "valid_to": {**_DATE, "description": "Пусто — бессрочно"},
            "eur_rub": {"type": "number", "description": "Рублей за 1 евро, больше 0"},
            "comment": {"type": "string"},
        },
        "required": ["valid_from", "eur_rub"],
    },
    scope=SCOPE_WRITE,
)
def create_fx_rate(db: Session, _actor: McpActor, **fields):
    return _run(db, procurement.create_fx_rate, _body(FxRateCreateRequest, fields))


@tool(
    "update_fx_rate",
    "Изменить период или значение курса. clear_valid_to=true сделает период "
    "бессрочным. Пересечение с другими периодами отклоняется. Удаления нет. "
    "Уже сохранённые рубли в оплатах и поставках не меняются.",
    {
        "type": "object",
        "properties": {
            "rate_id": _UUID,
            "valid_from": _DATE,
            "valid_to": _DATE,
            "clear_valid_to": {"type": "boolean"},
            "eur_rub": {"type": "number"},
            "comment": {"type": "string"},
        },
        "required": ["rate_id"],
    },
    scope=SCOPE_WRITE,
)
def update_fx_rate(db: Session, _actor: McpActor, rate_id: str, **fields):
    return _run(
        db,
        procurement.update_fx_rate,
        _uuid(rate_id, "rate_id"),
        _body(FxRateUpdateRequest, fields),
    )


# --- Сводки ----------------------------------------------------------------


@tool(
    "get_procurement_refs",
    "Справочник для форм: сезоны, активные категории, бренды и курс, действующий сегодня.",
    {"type": "object", "properties": {}, "required": []},
)
def get_procurement_refs(db: Session, _actor: McpActor):
    return _run(db, procurement.get_procurement_refs)


@tool(
    "get_season_dashboard",
    "Сводка сезонов, отмеченных для PWA: заказы, оплаты, поставки, остатки, "
    "разбивка по брендам и категориям. Без season_id — все сезоны дашборда.",
    {
        "type": "object",
        "properties": {"season_id": _UUID},
        "required": [],
    },
)
def get_season_dashboard(db: Session, _actor: McpActor, season_id: str | None = None):
    return _run(
        db,
        procurement.get_season_dashboard,
        season_id=_optional_uuid(season_id, "season_id"),
    )


@tool(
    "get_prepayment_overview",
    "Предоплаты сезонов дашборда: план, факт, остаток, просрочка. "
    "due_soon_days — за сколько дней до срока считать «скоро» (1–90, по умолчанию 14).",
    {
        "type": "object",
        "properties": {
            "season_id": _UUID,
            "due_soon_days": {"type": "integer"},
        },
        "required": [],
    },
)
def get_prepayment_overview(
    db: Session,
    _actor: McpActor,
    season_id: str | None = None,
    due_soon_days: int = 14,
):
    if (
        isinstance(due_soon_days, bool)
        or not isinstance(due_soon_days, int)
        or due_soon_days < 1
        or due_soon_days > 90
    ):
        raise ToolArgumentError("due_soon_days должен быть от 1 до 90")
    return _run(
        db,
        procurement.get_prepayment_overview,
        season_id=_optional_uuid(season_id, "season_id"),
        due_soon_days=due_soon_days,
    )


@tool(
    "list_brand_stats",
    "Сводка по брендам, у которых есть заказы, оплаты или доставленные поставки. "
    "Можно сузить одним season_id.",
    {
        "type": "object",
        "properties": {"season_id": _UUID},
        "required": [],
    },
)
def list_brand_stats(db: Session, _actor: McpActor, season_id: str | None = None):
    return _run(
        db,
        procurement.list_brand_stats,
        season_id=_optional_uuid(season_id, "season_id"),
    )


@tool(
    "get_brand_procurement_stats",
    "Заказы, оплаты и поставки одного бренда: итоги, разбивка по сезонам и категориям.",
    {
        "type": "object",
        "properties": {"brand_id": _UUID},
        "required": ["brand_id"],
    },
)
def get_brand_procurement_stats(db: Session, _actor: McpActor, brand_id: str):
    return _run(
        db,
        procurement.get_brand_procurement_stats,
        _uuid(brand_id, "brand_id"),
    )
