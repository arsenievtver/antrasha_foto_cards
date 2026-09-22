"""Реестр инструментов MCP закупок.

Обработчик синхронный: проект работает на синхронной сессии SQLAlchemy.
Схема аргументов — JSON Schema, её читает модель. Проверка нарочно неглубокая:
обязательные поля, лишние поля и типы. Тонкую валидацию делает pydantic в
существующих запросах админки.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.mcp_api_key import SCOPE_READ, SCOPE_WRITE
from app.services.mcp_keys import McpActor

logger = logging.getLogger("app.mcp_procurement")

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class ToolArgumentError(Exception):
    """Аргументы не сошлись со схемой или админка отклонила запись."""


class ToolPermissionError(Exception):
    """Ключ выпущен только на чтение, а инструмент меняет данные."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    handler: Callable[..., Any]
    scope: str = SCOPE_READ


_TOOLS: dict[str, Tool] = {}


def tool(
    name: str,
    description: str,
    input_schema: dict,
    scope: str = SCOPE_READ,
):
    def decorator(handler: Callable[..., Any]):
        _TOOLS[name] = Tool(name, description, input_schema, handler, scope)
        return handler

    return decorator


def scope_allows(key_scope: str, tool_scope: str) -> bool:
    return tool_scope == SCOPE_READ or key_scope == SCOPE_WRITE


def list_tools(key_scope: str = SCOPE_READ) -> list[dict]:
    return [
        {
            "name": item.name,
            "description": item.description,
            "inputSchema": item.input_schema,
        }
        for item in _TOOLS.values()
        if scope_allows(key_scope, item.scope)
    ]


def get_tool(name: str) -> Tool | None:
    return _TOOLS.get(name)


def check_limit(limit: int | None, maximum: int = MAX_LIMIT) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ToolArgumentError(f"limit должен быть целым от 1 до {maximum}")
    if limit < 1 or limit > maximum:
        raise ToolArgumentError(f"limit должен быть от 1 до {maximum}")
    return limit


def validate_arguments(item: Tool, arguments: dict) -> dict:
    schema = item.input_schema
    properties: dict = schema.get("properties", {})
    required: list = schema.get("required", [])

    unknown = set(arguments) - set(properties)
    if unknown:
        raise ToolArgumentError(
            f"Неизвестные аргументы: {', '.join(sorted(unknown))}. "
            f"Допустимы: {', '.join(sorted(properties)) or 'нет'}"
        )

    missing = [key for key in required if key not in arguments]
    if missing:
        raise ToolArgumentError(
            f"Не хватает обязательных аргументов: {', '.join(missing)}"
        )

    checkers = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for key, value in arguments.items():
        if value is None:
            continue
        expected = properties[key].get("type")
        checker = checkers.get(expected)
        if checker is None:
            continue
        if expected in ("integer", "number") and isinstance(value, bool):
            raise ToolArgumentError(f"Аргумент {key} должен быть типа {expected}")
        if not isinstance(value, checker):
            raise ToolArgumentError(f"Аргумент {key} должен быть типа {expected}")

    return arguments


def call_tool(item: Tool, db: Session, actor: McpActor, arguments: dict) -> Any:
    if not scope_allows(actor.scope, item.scope):
        raise ToolPermissionError(
            "Инструмент изменяет данные и требует ключ с правом записи. "
            "Текущий ключ только читает. Отзовите его в админке (Товар → Ключ MCP) "
            "и выпустите новый с галочкой «Разрешить изменять данные». "
            "Удаление через MCP недоступно в любом случае."
        )
    validate_arguments(item, arguments)
    if item.scope == SCOPE_WRITE:
        logger.info(
            "MCP procurement write %s actor=%s key=%s",
            item.name,
            actor.owner_role,
            actor.key_id,
        )
    return item.handler(db, actor, **arguments)
