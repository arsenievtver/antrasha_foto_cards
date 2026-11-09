"""Спрос от продавцов через MCP закупок.

Чтение — ключ суперпользователя. Склейка сообщений и привязка к клиенту А
меняют данные: нужен ещё ключ с правом записи.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mcp_procurement.registry import (
    SCOPE_WRITE,
    ToolArgumentError,
    ToolPermissionError,
    check_limit,
    tool,
)
from app.models.mcp_api_key import OWNER_SUPERUSER
from app.services.mcp_keys import McpActor
from app.models.staff_feedback import StaffFeedback
from app.services.a_clients import merge_feedback, set_feedback_client, split_thread
from app.services.staff_feedback import feedback_dicts, feedback_stats, list_feedback

MAX_FEEDBACK_LIMIT = 500

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
            "Раздел «Спрос» доступен только по ключу суперпользователя."
        )


def _date(value: str | None, name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ToolArgumentError(f"{name} должен быть датой YYYY-MM-DD") from exc


def _uuid(value: str | None, name: str) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise ToolArgumentError(f"{name} должен быть UUID") from exc


def _feedback_thread(db: Session, thread_id: uuid.UUID) -> list[dict]:
    rows = list(
        db.scalars(
            select(StaffFeedback)
            .where(StaffFeedback.thread_id == thread_id)
            .order_by(StaffFeedback.created_at)
        ).all()
    )
    return feedback_dicts(db, rows)


@tool(
    "list_staff_feedback",
    "Сообщения продавцов из раздела «Спрос» в work PWA, только ключ суперпользователя. "
    "Свободный текст о том, что спрашивали и чего нет, каких размеров не хватает, какие бренды хотят клиенты. "
    "Если несколько сообщений — одна мысль, у них общий thread_id. "
    "client_name — клиент А, к которому сообщение привязано. "
    "unlinked=true — ещё не привязанные и явно отвязанные. "
    "Новые сначала. Только чтение. Категории, бренды и размеры извлекайте из текста сами; "
    "id брендов и категорий для сверки — list_brands и list_categories.",
    {
        "type": "object",
        "properties": {
            **_PERIOD,
            "author_user_id": {
                "type": "string",
                "format": "uuid",
                "description": "Только сообщения этого сотрудника (id из get_staff_feedback_stats)",
            },
            "client_id": {
                "type": "string",
                "format": "uuid",
                "description": "Только сообщения этого клиента А (id из list_a_clients)",
            },
            "unlinked": {
                "type": "boolean",
                "description": "Только без клиента: разбор не узнал имя или привязку сняли",
            },
            "limit": {
                "type": "integer",
                "description": f"Сколько сообщений, от 1 до {MAX_FEEDBACK_LIMIT}. По умолчанию 50.",
            },
        },
    },
)
def list_staff_feedback_tool(
    db: Session,
    actor: McpActor,
    date_from: str | None = None,
    date_to: str | None = None,
    author_user_id: str | None = None,
    client_id: str | None = None,
    unlinked: bool | None = None,
    limit: int | None = None,
) -> dict:
    _require_superuser_key(actor)
    rows, total = list_feedback(
        db,
        author_user_id=_uuid(author_user_id, "author_user_id"),
        client_id=_uuid(client_id, "client_id"),
        unlinked=bool(unlinked),
        date_from=_date(date_from, "date_from"),
        date_to=_date(date_to, "date_to"),
        limit=check_limit(limit, MAX_FEEDBACK_LIMIT),
    )
    return {"total": total, "items": feedback_dicts(db, rows)}


@tool(
    "get_staff_feedback_stats",
    "Активность продавцов в разделе «Спрос» за период, только ключ суперпользователя: "
    "число сообщений, число разных дней с сообщениями, суммарная длина текста, первое и последнее сообщение. Только чтение. "
    "Полезность сообщений эти цифры не отражают — для неё читайте тексты через "
    "list_staff_feedback.",
    {"type": "object", "properties": {**_PERIOD}},
)
def get_staff_feedback_stats_tool(
    db: Session,
    actor: McpActor,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    _require_superuser_key(actor)
    return feedback_stats(
        db,
        date_from=_date(date_from, "date_from"),
        date_to=_date(date_to, "date_to"),
    )


@tool(
    "merge_staff_feedback",
    "Склеить сообщения «Спроса» в одну мысль. Только один сотрудник и только ключ "
    "суперпользователя с правом записи. Берите id из list_staff_feedback. "
    "После склейки у всех общий thread_id, текст читается по частям в порядке времени. "
    "Авторазбор больше эту склейку не переиграет.",
    {
        "type": "object",
        "properties": {
            "feedback_ids": {
                "type": "array",
                "items": {"type": "string", "format": "uuid"},
                "description": "Два или больше id сообщений одного автора, не больше 20",
            },
        },
        "required": ["feedback_ids"],
    },
    scope=SCOPE_WRITE,
)
def merge_staff_feedback_tool(db: Session, actor: McpActor, feedback_ids: list) -> dict:
    _require_superuser_key(actor)
    if not isinstance(feedback_ids, list) or not 2 <= len(feedback_ids) <= 20:
        raise ToolArgumentError("feedback_ids — от 2 до 20 сообщений")
    ids = []
    for raw in feedback_ids:
        if not isinstance(raw, str):
            raise ToolArgumentError("feedback_ids должен быть списком UUID")
        parsed = _uuid(raw, "feedback_ids")
        if parsed is None:
            raise ToolArgumentError("feedback_ids должен быть списком UUID")
        ids.append(parsed)
    try:
        thread_id = merge_feedback(db, ids)
    except ValueError as exc:
        db.rollback()
        raise ToolArgumentError(str(exc)) from exc
    db.commit()
    return {"thread_id": str(thread_id), "items": _feedback_thread(db, thread_id)}


@tool(
    "split_staff_feedback",
    "Разделить склеенную мысль «Спроса» обратно на отдельные сообщения. "
    "thread_id из list_staff_feedback. Только ключ суперпользователя с правом записи. "
    "Эти сообщения автосклейка больше не соединит.",
    {
        "type": "object",
        "properties": {
            "thread_id": {"type": "string", "format": "uuid", "description": "thread_id склейки"},
        },
        "required": ["thread_id"],
    },
    scope=SCOPE_WRITE,
)
def split_staff_feedback_tool(db: Session, actor: McpActor, thread_id: str) -> dict:
    _require_superuser_key(actor)
    parsed = _uuid(thread_id, "thread_id")
    if parsed is None:
        raise ToolArgumentError("thread_id должен быть UUID")
    try:
        count = split_thread(db, parsed)
    except LookupError as exc:
        db.rollback()
        raise ToolArgumentError(str(exc)) from exc
    db.commit()
    return {"split": count, "thread_id": str(parsed)}


@tool(
    "set_staff_feedback_client",
    "Привязать сообщение «Спроса» к клиенту А или отвязать. "
    "Только ключ суперпользователя с правом записи. "
    "Если у сообщения есть thread_id, привязка ставится на всю склейку. "
    "client_id из list_a_clients. client_id=null отвязывает и запрещает авторазбору вернуть эту связь. "
    "Ручная привязка следующим разбором не затирается.",
    {
        "type": "object",
        "properties": {
            "feedback_id": {"type": "string", "format": "uuid", "description": "id сообщения"},
            "client_id": {
                "type": "string",
                "format": "uuid",
                "description": "id клиента А или null, чтобы отвязать",
            },
        },
        "required": ["feedback_id", "client_id"],
    },
    scope=SCOPE_WRITE,
)
def set_staff_feedback_client_tool(
    db: Session,
    actor: McpActor,
    feedback_id: str,
    client_id: str | None = None,
) -> dict:
    _require_superuser_key(actor)
    message_id = _uuid(feedback_id, "feedback_id")
    if message_id is None:
        raise ToolArgumentError("feedback_id должен быть UUID")
    try:
        row = set_feedback_client(db, message_id, _uuid(client_id, "client_id"))
    except LookupError as exc:
        db.rollback()
        raise ToolArgumentError(str(exc)) from exc
    db.commit()
    db.refresh(row)
    if row.thread_id:
        items = _feedback_thread(db, row.thread_id)
    else:
        items = feedback_dicts(db, [row])
    return {"items": items}
