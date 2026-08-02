"""Админка: ИИ-аналитика МойСклад через Anthropic MCP connector."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.deps import AdminPrincipal, require_superuser
from app.schemas.warehouse_ai import (
    WarehouseAiChatRequest,
    WarehouseAiChatResponse,
    WarehouseAiPreset,
    WarehouseAiPresetsResponse,
    WarehouseAiStatusResponse,
)
from app.services.warehouse_ai import (
    WAREHOUSE_AI_PRESETS,
    chat_with_warehouse_mcp,
    parse_tools_csv,
    warehouse_ai_configured,
)

log = logging.getLogger("app.api.admin_warehouse_ai")

router = APIRouter(prefix="/admin/warehouse-ai", tags=["admin-warehouse-ai"])


@router.get("/status", response_model=WarehouseAiStatusResponse)
def warehouse_ai_status(
    _su: AdminPrincipal = Depends(require_superuser),
) -> WarehouseAiStatusResponse:
    _ = _su
    key_set = bool(settings.anthropic_api_key and str(settings.anthropic_api_key).strip())
    url_set = bool(settings.moysklad_mcp_url and str(settings.moysklad_mcp_url).strip())
    auth_set = bool(settings.moysklad_mcp_auth_token and str(settings.moysklad_mcp_auth_token).strip())
    return WarehouseAiStatusResponse(
        configured=warehouse_ai_configured(settings),
        anthropic_key_set=key_set,
        mcp_url_set=url_set,
        mcp_auth_set=auth_set,
        model=(settings.anthropic_model or None) if key_set else None,
        allowlist_count=len(parse_tools_csv(settings.moysklad_mcp_allowed_tools)),
        denylist_count=len(parse_tools_csv(settings.moysklad_mcp_denied_tools)),
    )


@router.get("/presets", response_model=WarehouseAiPresetsResponse)
def warehouse_ai_presets(
    _su: AdminPrincipal = Depends(require_superuser),
) -> WarehouseAiPresetsResponse:
    _ = _su
    return WarehouseAiPresetsResponse(
        items=[WarehouseAiPreset(**p) for p in WAREHOUSE_AI_PRESETS],
    )


@router.post("/chat", response_model=WarehouseAiChatResponse)
def warehouse_ai_chat(
    body: WarehouseAiChatRequest,
    _su: AdminPrincipal = Depends(require_superuser),
) -> WarehouseAiChatResponse:
    if not warehouse_ai_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "ИИ склада не настроен. Задайте ANTHROPIC_API_KEY и MOYSKLAD_MCP_URL в .env"
            ),
        )

    messages = [{"role": m.role, "content": m.content.strip()} for m in body.messages]
    messages = [m for m in messages if m["content"]]
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пустой диалог",
        )
    if messages[-1]["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Последнее сообщение должно быть от пользователя",
        )

    if body.preset_id:
        preset = next((p for p in WAREHOUSE_AI_PRESETS if p["id"] == body.preset_id), None)
        if preset is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неизвестный preset_id: {body.preset_id}",
            )
        # Если клиент прислал короткий ярлык — подменяем на полный промпт пресета.
        last = messages[-1]["content"]
        if last == preset["id"] or last == preset["title"] or len(last) < 40:
            messages[-1] = {"role": "user", "content": preset["prompt"]}

    try:
        result = chat_with_warehouse_mcp(settings, messages=messages)
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e

    log.info(
        "warehouse_ai chat role=%s user=%s tools=%s",
        _su.role,
        _su.user.id if _su.user else "superuser",
        result.get("tools_used"),
    )
    return WarehouseAiChatResponse(**result)
