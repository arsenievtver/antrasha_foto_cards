"""HTTP-вход MCP закупок: POST /mcp, без сессии.

Клиент ходит сюда с ключом из админки (Товар → Ключ MCP), заголовок
Authorization: Bearer mcp_live_…. Снаружи, за nginx админки, это /api/mcp.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import Request
from fastapi.responses import JSONResponse, Response

from app.database import SessionLocal
from app.mcp_procurement.server import (
    INVALID_REQUEST,
    PARSE_ERROR,
    error_response,
    handle_message,
)
from app.services.mcp_keys import actor_from_key, resolve_key, touch_key

logger = logging.getLogger("app.mcp_procurement")

BEARER_PREFIX = "Bearer "


class AuthError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def extract_token(header: str | None) -> str | None:
    if not header or not header.startswith(BEARER_PREFIX):
        return None
    token = header[len(BEARER_PREFIX) :].strip()
    return token or None


def _unauthorized(message: str) -> JSONResponse:
    return JSONResponse(
        {"error": message},
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def dispatch(token: str | None, payload) -> dict | list | None:
    """Один JSON-RPC запрос или пакет. None — пакет из одних уведомлений.

    AuthError, если ключа нет или он не действует. Сессию закрывает вызывающий
    код: она живёт внутри этой функции.
    """
    if not token:
        raise AuthError("Missing API key")

    db = SessionLocal()
    try:
        key = resolve_key(db, token)
        if key is None:
            logger.warning("MCP procurement: rejected key")
            raise AuthError("Invalid API key")
        touch_key(db, key)
        actor = actor_from_key(key)

        if isinstance(payload, list):
            if not payload:
                return error_response(None, INVALID_REQUEST, "Empty batch")
            responses = []
            for message in payload:
                response = handle_message(message, db, actor)
                if response is not None:
                    responses.append(response)
            return responses or None

        return handle_message(payload, db, actor)
    finally:
        db.close()


async def mcp_post(request: Request) -> Response:
    token = extract_token(request.headers.get("authorization"))
    if token is None:
        return _unauthorized("Missing API key")

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            error_response(None, PARSE_ERROR, "Invalid JSON"),
            status_code=400,
        )

    try:
        body = await asyncio.to_thread(dispatch, token, payload)
    except AuthError as exc:
        return _unauthorized(exc.message)

    if body is None:
        return Response(status_code=202)
    return JSONResponse(body)


async def mcp_method_not_allowed(_request: Request) -> JSONResponse:
    return JSONResponse(
        {"error": "This MCP server is stateless: use POST"},
        status_code=405,
        headers={"Allow": "POST"},
    )
