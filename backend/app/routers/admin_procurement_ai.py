"""Админка: диалоговый агент закупок. Доступ — право «Товар»."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.deps import AdminPrincipal, require_permission
from app.schemas.procurement_ai import (
    ProcurementAiChatRequest,
    ProcurementAiChatResponse,
    ProcurementAiPreset,
    ProcurementAiPresetsResponse,
    ProcurementAiStatusResponse,
)
from app.services.procurement_ai import PRESETS, chat_procurement, status_for

log = logging.getLogger("app.api.procurement_ai")

router = APIRouter(prefix="/admin/procurement-ai", tags=["admin-procurement-ai"])


def _configured() -> bool:
    return bool(settings.anthropic_api_key and str(settings.anthropic_api_key).strip())


@router.get("/status", response_model=ProcurementAiStatusResponse)
def procurement_ai_status(
    principal: AdminPrincipal = Depends(require_permission("product")),
) -> ProcurementAiStatusResponse:
    key_set = _configured()
    info = status_for(principal)
    return ProcurementAiStatusResponse(
        configured=key_set,
        model=(settings.warehouse_ai_writer_model or settings.anthropic_model) if key_set else None,
        **info,
    )


@router.get("/presets", response_model=ProcurementAiPresetsResponse)
def procurement_ai_presets(
    _p: AdminPrincipal = Depends(require_permission("product")),
) -> ProcurementAiPresetsResponse:
    _ = _p
    return ProcurementAiPresetsResponse(items=[ProcurementAiPreset(**item) for item in PRESETS])


@router.post("/chat", response_model=ProcurementAiChatResponse)
def procurement_ai_chat(
    body: ProcurementAiChatRequest,
    principal: AdminPrincipal = Depends(require_permission("product")),
) -> ProcurementAiChatResponse:
    if not _configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Агент закупок не настроен. Нужен ANTHROPIC_API_KEY.",
        )
    messages = [{"role": m.role, "content": m.content.strip()} for m in body.messages]
    messages = [m for m in messages if m["content"]]
    if not messages or messages[-1]["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Последнее сообщение должно быть от пользователя",
        )
    try:
        result = chat_procurement(settings, messages=messages, principal=principal)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    log.info(
        "procurement_ai chat role=%s write=%s tools=%s",
        principal.role,
        result.get("can_write"),
        result.get("tools_used"),
    )
    return ProcurementAiChatResponse(**result)
