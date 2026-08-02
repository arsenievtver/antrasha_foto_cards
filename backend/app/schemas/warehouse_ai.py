"""Схемы: ИИ-аналитика склада (Anthropic + MCP МойСклад)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class WarehouseAiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=32_000)


class WarehouseAiChatRequest(BaseModel):
    """Свободный вопрос или продолжение диалога. Опционально — id пресета (для аналитики)."""

    messages: list[WarehouseAiChatMessage] = Field(..., min_length=1, max_length=40)
    preset_id: str | None = Field(default=None, max_length=64)


class WarehouseAiChatResponse(BaseModel):
    reply: str
    model: str
    tools_used: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)


class WarehouseAiPreset(BaseModel):
    id: str
    title: str
    description: str
    prompt: str


class WarehouseAiPresetsResponse(BaseModel):
    items: list[WarehouseAiPreset]


class WarehouseAiStatusResponse(BaseModel):
    configured: bool
    anthropic_key_set: bool
    mcp_url_set: bool
    mcp_auth_set: bool
    model: str | None = None
    allowlist_count: int = 0
    denylist_count: int = 0
