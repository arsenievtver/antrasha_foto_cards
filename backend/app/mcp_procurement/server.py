"""JSON-RPC диспетчер MCP закупок.

Отдельный сервер от MCP МойСклад: тот ходит во внешний товароучёт, этот
читает и меняет закупки самого проекта. Удаления в реестре нет.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.mcp_procurement.registry import (
    ToolArgumentError,
    ToolPermissionError,
    call_tool,
    get_tool,
    list_tools,
)
from app.services.mcp_keys import McpActor

import app.mcp_procurement.ranking_eval_tools  # noqa: F401,E402
import app.mcp_procurement.tools  # noqa: F401,E402

logger = logging.getLogger("app.mcp_procurement")

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
PREFERRED_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]

SERVER_INFO = {"name": "antrasha-procurement", "version": "1.0.0"}

SERVER_INSTRUCTIONS = (
    "Закупки магазина Антраша: сезоны, бренды, заказы брендам, оплаты, поставки "
    "и курс EUR/RUB. Это данные самого проекта, не МойСклад. "
    "Суммы заказов, оплат и поставок — в евро. Курс на оплате и поставке "
    "фиксируется на дату документа; если его не передать, подставится курс из "
    "справочника на эту дату. "
    "Идентификаторы берите из list_seasons, list_brands и list_categories — "
    "по названиям фильтровать нельзя. "
    "Заказ можно создать общей суммой или строками по категориям (тогда сумма "
    "заказа равна сумме строк). Оплата и поставка требуют season_id и brand_id; "
    "order_id необязателен, но если указан, сезон и бренд должны совпасть с заказом. "
    "kind оплаты: prepayment (предоплата) или main (основная). "
    "Поставка с is_delivered=false ещё в пути и не уменьшает «осталось поставить». "
    "Периоды курса EUR не пересекаются; пустой valid_to значит «бессрочно». "
    "Сезон с is_order_plan=true — единственный сезон раздела «Для заказа». "
    "is_primary показывает сезон на дашборде PWA, таких сезонов может быть несколько. "
    "Удаления нет: сезон, бренд, заказ, оплату, поставку и курс можно только "
    "создать или изменить. Удаление — вручную в админке. "
    "Инструменты изменения видны, только если ключ выпущен с правом записи. "
    "Оценка ранжирования — только чтение: list_ranking_eval_submissions и "
    "get_ranking_eval_submission. Это сравнение порядка человека с порядком модели "
    "на эталонном наборе. В деталях — оба ранга, url фото, снимок настроек ленты, "
    "разброс эмбеддингов набора и вектор вкуса (swipe_updates и like/dislike по полу). "
    "Сырые векторы не отдаются."
)

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


def _result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _text_content(payload: Any, is_error: bool = False) -> dict:
    text = (
        payload
        if isinstance(payload, str)
        else json.dumps(payload, ensure_ascii=False, default=str, indent=2)
    )
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _negotiate_version(requested: Any) -> str:
    if isinstance(requested, str) and requested in SUPPORTED_PROTOCOL_VERSIONS:
        return requested
    return PREFERRED_PROTOCOL_VERSION


def handle_message(
    message: Any,
    db: Session,
    actor: McpActor,
) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return error_response(None, INVALID_REQUEST, "Expected a JSON-RPC 2.0 message")

    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}
    is_notification = "id" not in message

    if not isinstance(method, str):
        return None if is_notification else error_response(
            request_id, INVALID_REQUEST, "Missing method"
        )

    if method.startswith("notifications/"):
        return None

    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": _negotiate_version(params.get("protocolVersion")),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": SERVER_INSTRUCTIONS,
            },
        )

    if method == "ping":
        return _result(request_id, {})

    if method == "tools/list":
        return _result(request_id, {"tools": list_tools(actor.scope)})

    if method == "tools/call":
        return _handle_tool_call(request_id, params, db, actor)

    return error_response(request_id, METHOD_NOT_FOUND, f"Unknown method: {method}")


def _handle_tool_call(
    request_id: Any,
    params: dict,
    db: Session,
    actor: McpActor,
) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}

    if not isinstance(name, str):
        return error_response(request_id, INVALID_PARAMS, "Missing tool name")
    if not isinstance(arguments, dict):
        return error_response(request_id, INVALID_PARAMS, "arguments must be an object")

    item = get_tool(name)
    if item is None:
        return error_response(request_id, INVALID_PARAMS, f"Unknown tool: {name}")

    try:
        payload = call_tool(item, db, actor, arguments)
    except (ToolArgumentError, ToolPermissionError) as exc:
        db.rollback()
        return _result(request_id, _text_content(str(exc), is_error=True))
    except Exception:
        db.rollback()
        logger.exception("MCP procurement: tool %s failed", name)
        return _result(
            request_id,
            _text_content(
                f"Инструмент {name} завершился с ошибкой. Подробности в логах сервера.",
                is_error=True,
            ),
        )

    return _result(request_id, _text_content(payload))
