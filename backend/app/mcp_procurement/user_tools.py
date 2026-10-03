"""Пользователи приложения через MCP закупок. Только чтение, ключ суперпользователя."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.mcp_procurement.registry import ToolArgumentError, ToolPermissionError, check_limit, tool
from app.models.mcp_api_key import OWNER_SUPERUSER
from app.services.app_user_intel import (
    AppUserNotFoundError,
    list_app_users,
    list_fitting_requests_filtered,
    lookup_users_by_phones,
    resolve_user,
    user_detail_enriched,
)
from app.services.mcp_keys import McpActor

_MAX_PHONES = 150
_MAX_LIST = 200

_PERIOD = {
    "date_from": {
        "type": "string",
        "format": "date",
        "description": "С даты включительно, YYYY-MM-DD (Europe/Moscow)",
    },
    "date_to": {
        "type": "string",
        "format": "date",
        "description": "По дату включительно, YYYY-MM-DD (Europe/Moscow)",
    },
}


def _require_superuser_key(actor: McpActor) -> None:
    if actor.owner_role != OWNER_SUPERUSER:
        raise ToolPermissionError(
            "Раздел «Пользователи приложения» доступен только по ключу суперпользователя."
        )


def _date(value: str | None, name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolArgumentError(f"{name} должен быть датой YYYY-MM-DD") from exc


def _uuid(value: str, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError) as exc:
        raise ToolArgumentError(f"{name} должен быть UUID") from exc


@tool(
    "list_app_users",
    "Список зарегистрированных в приложении (таблица users). Только ключ суперпользователя. "
    "Фильтры: role (user|worker), inactive_for_days — не заходили столько дней или ни разу, "
    "never_logged_in, phone, display_name_contains, registered_from/to. "
    "Для полного профиля (свайпы, вкус, push, ближайшие фото коллекции) — get_app_user.",
    {
        "type": "object",
        "properties": {
            "skip": {"type": "integer", "description": "Пропустить N записей, по умолчанию 0"},
            "limit": {
                "type": "integer",
                "description": f"Сколько вернуть, 1–{_MAX_LIST}. По умолчанию 50.",
            },
            "role": {
                "type": "string",
                "enum": ["user", "worker"],
                "description": "Только клиенты или сотрудники",
            },
            "inactive_for_days": {
                "type": "integer",
                "description": "last_login_at старше N дней или null (неактивные / «потеряшки» в приложении)",
            },
            "never_logged_in": {
                "type": "boolean",
                "description": "true — только с last_login_at=null",
            },
            "phone": {"type": "string", "description": "Точный поиск по нормализованному телефону"},
            "display_name_contains": {
                "type": "string",
                "description": "Подстрока в display_name (без учёта регистра)",
            },
            "registered_from": {**_PERIOD["date_from"], "description": "created_at с даты"},
            "registered_to": {**_PERIOD["date_to"], "description": "created_at по дату"},
        },
    },
)
def list_app_users_tool(
    db: Session,
    actor: McpActor,
    skip: int | None = None,
    limit: int | None = None,
    role: str | None = None,
    inactive_for_days: int | None = None,
    never_logged_in: bool | None = None,
    phone: str | None = None,
    display_name_contains: str | None = None,
    registered_from: str | None = None,
    registered_to: str | None = None,
) -> dict:
    _require_superuser_key(actor)
    if role is not None and role not in ("user", "worker"):
        raise ToolArgumentError("role должен быть user или worker")
    if inactive_for_days is not None and inactive_for_days < 0:
        raise ToolArgumentError("inactive_for_days не может быть отрицательным")
    return list_app_users(
        db,
        skip=max(0, skip or 0),
        limit=check_limit(limit, _MAX_LIST),
        role=role,
        inactive_for_days=inactive_for_days,
        never_logged_in=bool(never_logged_in) if never_logged_in else None,
        phone=phone,
        display_name_contains=display_name_contains,
        registered_from=_date(registered_from, "registered_from"),
        registered_to=_date(registered_to, "registered_to"),
    )


@tool(
    "get_app_user",
    "Полный профиль пользователя приложения: свайпы, теги, вектор вкуса и ближайшие фото по полу, "
    "push-подписка, кампания регистрации, заявки на примерку, активные подарочные сертификаты. "
    "Только ключ суперпользователя. Укажите user_id или phone.",
    {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "format": "uuid"},
            "phone": {"type": "string"},
        },
    },
)
def get_app_user_tool(
    db: Session,
    actor: McpActor,
    user_id: str | None = None,
    phone: str | None = None,
) -> dict:
    _require_superuser_key(actor)
    if not user_id and not phone:
        raise ToolArgumentError("Укажите user_id или phone")
    uid = _uuid(user_id, "user_id") if user_id else None
    try:
        u = resolve_user(db, user_id=uid, phone=phone)
    except AppUserNotFoundError as exc:
        raise ToolArgumentError(str(exc)) from exc
    return user_detail_enriched(db, u)


@tool(
    "lookup_app_users_by_phones",
    "Пакетная проверка: зарегистрирован ли номер в приложении. Только ключ суперпользователя. "
    "До 150 номеров. Для полного профиля — get_app_user.",
    {
        "type": "object",
        "properties": {
            "phones": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["phones"],
    },
)
def lookup_app_users_by_phones_tool(
    db: Session,
    actor: McpActor,
    phones: list,
) -> dict:
    _require_superuser_key(actor)
    if not isinstance(phones, list) or not phones:
        raise ToolArgumentError("phones — непустой массив")
    if len(phones) > _MAX_PHONES:
        raise ToolArgumentError(f"Не больше {_MAX_PHONES} номеров за один вызов")
    return lookup_users_by_phones(db, [str(p) for p in phones])


@tool(
    "list_fitting_requests",
    "Заявки на примерку из приложения (подбор понравившихся образов). Только ключ суперпользователя. "
    "Фильтры: user_id, phone, status (new и др.), date_from/date_to по created_at. "
    "user_id=null в строке — заявка гостя без регистрации.",
    {
        "type": "object",
        "properties": {
            "skip": {"type": "integer"},
            "limit": {"type": "integer"},
            "user_id": {"type": "string", "format": "uuid"},
            "phone": {"type": "string"},
            "status": {"type": "string", "description": "Статус заявки, например new"},
            "date_from": _PERIOD["date_from"],
            "date_to": _PERIOD["date_to"],
        },
    },
)
def list_fitting_requests_tool(
    db: Session,
    actor: McpActor,
    skip: int | None = None,
    limit: int | None = None,
    user_id: str | None = None,
    phone: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    _require_superuser_key(actor)
    uid = _uuid(user_id, "user_id") if user_id else None
    return list_fitting_requests_filtered(
        db,
        skip=max(0, skip or 0),
        limit=check_limit(limit, _MAX_LIST),
        user_id=uid,
        phone=phone,
        status=status,
        created_from=_date(date_from, "date_from"),
        created_to=_date(date_to, "date_to"),
    )
