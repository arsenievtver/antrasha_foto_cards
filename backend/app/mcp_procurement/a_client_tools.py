"""Клиенты А на контроле через MCP закупок.

Чтение — ключ суперпользователя. Сбор списка и сотрудники меняют данные:
нужен ещё ключ с правом записи. Склейка комментариев — merge_staff_feedback.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.mcp_procurement.registry import (
    SCOPE_WRITE,
    ToolArgumentError,
    ToolPermissionError,
    check_limit,
    tool,
)
from app.models.mcp_api_key import OWNER_SUPERUSER
from app.services.a_client_active import load_active_board
from app.services.a_clients import (
    add_caretaker,
    dismiss_caretaker,
    get_client,
    list_clients,
    refresh_from_reports,
)
from app.services.mcp_keys import McpActor

MAX_CLIENTS = 200


def _require_superuser_key(actor: McpActor) -> None:
    if actor.owner_role != OWNER_SUPERUSER:
        raise ToolPermissionError("Клиенты А доступны только по ключу суперпользователя.")


def _uuid(value: str | None, name: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ToolArgumentError(f"{name} должен быть UUID") from exc


@tool(
    "list_a_clients",
    "Клиенты категории А на контроле, только ключ суперпользователя. "
    "Снимок из недель: статус, выручка за 12 месяцев, сколько недель в списке, "
    "кто из сотрудников ведёт (их может быть несколько) и короткий последний комментарий из «Спроса». "
    "active=false — в последней неделе клиента уже нет, это и есть прогресс. "
    "without_caretaker=true — о клиенте ещё никто не написал. Только чтение. "
    "Подробности, история недель и тексты — get_a_client.",
    {
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "Часть имени или телефон"},
            "status": {
                "type": "string",
                "description": "просрочил визит, покупает меньше или ушёл (>12 мес)",
            },
            "active": {"type": "boolean", "description": "Только те, кто ещё в последнем списке"},
            "caretaker": {
                "type": "string",
                "description": "Имя сотрудника или его id из get_staff_feedback_stats",
            },
            "without_caretaker": {
                "type": "boolean",
                "description": "Только клиенты без привязанного сотрудника",
            },
            "limit": {"type": "integer", "description": f"Сколько строк, от 1 до {MAX_CLIENTS}. По умолчанию 50."},
        },
    },
)
def list_a_clients_tool(
    db: Session,
    actor: McpActor,
    q: str | None = None,
    status: str | None = None,
    active: bool | None = None,
    caretaker: str | None = None,
    without_caretaker: bool | None = None,
    limit: int | None = None,
) -> dict:
    _require_superuser_key(actor)
    items = list_clients(
        db,
        q=q,
        status=status,
        active=active,
        caretaker=caretaker,
        without_caretaker=bool(without_caretaker),
    )
    cap = check_limit(limit, MAX_CLIENTS)
    return {"total": len(items), "items": items[:cap]}


@tool(
    "get_a_client",
    "Карточка клиента А, только ключ суперпользователя. "
    "История по неделям (статус, дни без визита, выручка 12 мес), сотрудники и комментарии «Спроса». "
    "Комментарии одной мысли лежат в одной группе parts. id — из list_a_clients. Только чтение.",
    {
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "format": "uuid", "description": "id из list_a_clients"},
        },
        "required": ["client_id"],
    },
)
def get_a_client_tool(db: Session, actor: McpActor, client_id: str) -> dict:
    _require_superuser_key(actor)
    parsed = _uuid(client_id, "client_id")
    if parsed is None:
        raise ToolArgumentError("client_id должен быть UUID")
    row = get_client(db, parsed)
    if row is None:
        raise ToolArgumentError("Клиент не найден")
    return row


@tool(
    "sync_a_clients",
    "Собрать клиентов А из готовых недель и заново разобрать комментарии «Спроса». "
    "Только ключ суперпользователя с правом записи. "
    "Повторный запуск ничего не дублирует. Ручные привязки и снятые сотрудники не затираются. "
    "Обрывки одной мысли короче трёх минут склеиваются сами, если во втором сообщении нет нового имени. "
    "Возвращает, сколько недель взято, сколько клиентов на контроле, сколько сообщений привязано и склеено.",
    {"type": "object", "properties": {}},
    scope=SCOPE_WRITE,
)
def sync_a_clients_tool(db: Session, actor: McpActor) -> dict:
    _require_superuser_key(actor)
    stats = refresh_from_reports(db)
    db.commit()
    return stats


@tool(
    "add_a_client_caretaker",
    "Назначить сотруднику клиента А вручную. Только ключ суперпользователя с правом записи. "
    "client_id из list_a_clients. author_user_id и author_label — из get_staff_feedback_stats. "
    "У клиента может быть несколько сотрудников. Повторный вызов для того же человека включает его снова, "
    "даже если раньше сняли.",
    {
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "format": "uuid"},
            "author_user_id": {
                "type": "string",
                "format": "uuid",
                "description": "id сотрудника, если учётка есть",
            },
            "author_label": {"type": "string", "description": "Как сотрудник подписан в «Спросе»"},
        },
        "required": ["client_id", "author_label"],
    },
    scope=SCOPE_WRITE,
)
def add_a_client_caretaker_tool(
    db: Session,
    actor: McpActor,
    client_id: str,
    author_label: str,
    author_user_id: str | None = None,
) -> dict:
    _require_superuser_key(actor)
    parsed = _uuid(client_id, "client_id")
    if parsed is None:
        raise ToolArgumentError("client_id должен быть UUID")
    label = (author_label or "").strip()
    if not label:
        raise ToolArgumentError("Нужно имя сотрудника")
    try:
        row = add_caretaker(
            db,
            parsed,
            author_user_id=_uuid(author_user_id, "author_user_id"),
            author_label=label,
        )
    except LookupError as exc:
        db.rollback()
        raise ToolArgumentError(str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise ToolArgumentError(str(exc)) from exc
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "client_id": str(row.client_id),
        "author_user_id": str(row.author_user_id) if row.author_user_id else None,
        "author_label": row.author_label,
        "source": row.source,
        "active": row.active,
    }


@tool(
    "dismiss_a_client_caretaker",
    "Снять сотрудника с клиента А. Только ключ суперпользователя с правом записи. "
    "caretaker_id — id из списка caretakers в get_a_client. Комментарии остаются. "
    "Следующий разбор комментариев этого человека сам не вернёт: чтобы вернуть, вызовите add_a_client_caretaker.",
    {
        "type": "object",
        "properties": {
            "client_id": {"type": "string", "format": "uuid"},
            "caretaker_id": {"type": "string", "format": "uuid", "description": "id из caretakers"},
        },
        "required": ["client_id", "caretaker_id"],
    },
    scope=SCOPE_WRITE,
)
def dismiss_a_client_caretaker_tool(
    db: Session,
    actor: McpActor,
    client_id: str,
    caretaker_id: str,
) -> dict:
    _require_superuser_key(actor)
    client = _uuid(client_id, "client_id")
    caretaker = _uuid(caretaker_id, "caretaker_id")
    if client is None or caretaker is None:
        raise ToolArgumentError("client_id и caretaker_id должны быть UUID")
    try:
        dismiss_caretaker(db, client, caretaker)
    except LookupError as exc:
        db.rollback()
        raise ToolArgumentError(str(exc)) from exc
    db.commit()
    return {"dismissed": True, "client_id": str(client), "caretaker_id": str(caretaker)}


@tool(
    "list_active_a_clients",
    "Действующие клиенты категории А: не на контроле, статус «в ритме» или «одна покупка». "
    "Только ключ суперпользователя. Срез пишется в понедельник вместе с неделей. "
    "summary: сколько всего, новых к прошлой неделе, оставшихся, выбывших, кто растёт и падает, "
    "суммы за 12 месяцев, средний чек и средний интервал визитов. "
    "items: карточки с размерами, брендами, категориями, trend_pct (последние 12 к предыдущим 12) "
    "и week_pct (к прошлому понедельнику). left: кто выбыл и куда (статус контроля или выход из А). "
    "Пока колонка пустая, ready=false — срез появится со следующего прогона. Только чтение.",
    {"type": "object", "properties": {}},
)
def list_active_a_clients_tool(db: Session, actor: McpActor) -> dict:
    _require_superuser_key(actor)
    return load_active_board(db)
