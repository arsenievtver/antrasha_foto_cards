"""Спрос от продавцов через тот же MCP, что и закупки. Только чтение."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.mcp_procurement.registry import (
    ToolArgumentError,
    ToolPermissionError,
    check_limit,
    tool,
)
from app.models.mcp_api_key import OWNER_SUPERUSER
from app.services.mcp_keys import McpActor
from app.services.staff_feedback import feedback_dict, feedback_stats, list_feedback

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


@tool(
    "list_staff_feedback",
    "Сообщения продавцов из раздела «Спрос» в work PWA, только ключ суперпользователя. "
    "Свободный текст о том, что спрашивали и чего нет, каких размеров не хватает, какие бренды хотят клиенты. "
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
    limit: int | None = None,
) -> dict:
    _require_superuser_key(actor)
    author = None
    if author_user_id:
        try:
            author = uuid.UUID(author_user_id)
        except ValueError as exc:
            raise ToolArgumentError("author_user_id должен быть UUID") from exc
    rows, total = list_feedback(
        db,
        author_user_id=author,
        date_from=_date(date_from, "date_from"),
        date_to=_date(date_to, "date_to"),
        limit=check_limit(limit, MAX_FEEDBACK_LIMIT),
    )
    return {"total": total, "items": [feedback_dict(r) for r in rows]}


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
