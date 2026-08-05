"""Админка: AI-аналитика ANTRASHA (semantic layer + optional legacy MCP)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.deps import AdminPrincipal, require_permission
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
    resolved_allowed_tools,
    warehouse_ai_configured as mcp_configured,
)
from app.services.warehouse_analytics import chat_semantic, semantic_configured
from app.services.warehouse_analytics.catalog import OPERATION_CATALOG

log = logging.getLogger("app.api.admin_warehouse_ai")

router = APIRouter(prefix="/admin/warehouse-ai", tags=["admin-warehouse-ai"])


def _mode() -> str:
    return (settings.warehouse_ai_mode or "semantic").strip().lower()


def _is_configured() -> bool:
    if _mode() == "legacy_mcp":
        return mcp_configured(settings)
    return semantic_configured(settings)


@router.get("/status", response_model=WarehouseAiStatusResponse)
def warehouse_ai_status(
    _p: AdminPrincipal = Depends(require_permission("ai_assistant")),
) -> WarehouseAiStatusResponse:
    _ = _p
    key_set = bool(settings.anthropic_api_key and str(settings.anthropic_api_key).strip())
    token_set = bool(settings.moysklad_token and str(settings.moysklad_token).strip())
    url_set = bool(settings.moysklad_mcp_url and str(settings.moysklad_mcp_url).strip())
    auth_set = bool(settings.moysklad_mcp_auth_token and str(settings.moysklad_mcp_auth_token).strip())
    mode = _mode()
    allowed = resolved_allowed_tools(settings)
    raw_allowed = (settings.moysklad_mcp_allowed_tools or "").strip().lower()
    if raw_allowed in ("all", "*", "any"):
        allow_mode = "all"
    elif raw_allowed:
        allow_mode = "env"
    else:
        allow_mode = "default"
    return WarehouseAiStatusResponse(
        configured=_is_configured(),
        mode=mode,
        anthropic_key_set=key_set,
        moysklad_token_set=token_set,
        mcp_url_set=url_set,
        mcp_auth_set=auth_set,
        model=(settings.anthropic_model or None) if key_set else None,
        router_model=settings.warehouse_ai_router_model if key_set else None,
        writer_model=settings.warehouse_ai_writer_model if key_set else None,
        operations_count=len(OPERATION_CATALOG),
        allowlist_count=0 if allowed is None else len(allowed),
        denylist_count=len(parse_tools_csv(settings.moysklad_mcp_denied_tools)),
        allowlist_mode=allow_mode,
    )


@router.get("/presets", response_model=WarehouseAiPresetsResponse)
def warehouse_ai_presets(
    _p: AdminPrincipal = Depends(require_permission("ai_assistant")),
) -> WarehouseAiPresetsResponse:
    _ = _p
    return WarehouseAiPresetsResponse(
        items=[WarehouseAiPreset(**p) for p in WAREHOUSE_AI_PRESETS],
    )


@router.post("/chat", response_model=WarehouseAiChatResponse)
def warehouse_ai_chat(
    body: WarehouseAiChatRequest,
    _p: AdminPrincipal = Depends(require_permission("ai_assistant")),
) -> WarehouseAiChatResponse:
    if not _is_configured():
        mode = _mode()
        if mode == "legacy_mcp":
            detail = "ИИ склада (MCP) не настроен. Нужны ANTHROPIC_API_KEY и MOYSKLAD_MCP_URL."
        else:
            detail = (
                "ИИ склада (semantic) не настроен. Нужны ANTHROPIC_API_KEY и MOYSKLAD_TOKEN "
                "в deploy/env/.env.backend.prod."
            )
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)

    messages = [{"role": m.role, "content": m.content.strip()} for m in body.messages]
    messages = [m for m in messages if m["content"]]
    if not messages:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Пустой диалог")
    if messages[-1]["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Последнее сообщение должно быть от пользователя",
        )

    preset_id = body.preset_id
    if preset_id:
        preset = next((p for p in WAREHOUSE_AI_PRESETS if p["id"] == preset_id), None)
        if preset is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неизвестный preset_id: {preset_id}",
            )

    try:
        if _mode() == "legacy_mcp":
            # legacy: expand short preset label to long prompt
            if preset_id:
                preset = next(p for p in WAREHOUSE_AI_PRESETS if p["id"] == preset_id)
                last = messages[-1]["content"]
                if last == preset["id"] or last == preset["title"] or len(last) < 40:
                    messages[-1] = {"role": "user", "content": preset["prompt"]}
            result = chat_with_warehouse_mcp(settings, messages=messages)
            result.setdefault("mode", "legacy_mcp")
            result.setdefault("operations", result.get("tools_used") or [])
            result.setdefault("cache_hits", 0)
        else:
            result = chat_semantic(
                settings,
                messages=messages,
                preset_id=preset_id,
            )
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    log.info(
        "warehouse_ai chat mode=%s role=%s user=%s ops=%s usage=%s",
        result.get("mode"),
        _p.role,
        _p.user.id if _p.user else "superuser",
        result.get("operations") or result.get("tools_used"),
        result.get("usage"),
    )
    return WarehouseAiChatResponse(**{k: v for k, v in result.items() if k in WarehouseAiChatResponse.model_fields})
