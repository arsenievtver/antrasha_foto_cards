"""Схемы: ИИ-аналитика склада (semantic / legacy MCP)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class WarehouseAiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=32_000)


class WarehouseAiChatRequest(BaseModel):
    messages: list[WarehouseAiChatMessage] = Field(..., min_length=1, max_length=40)
    preset_id: str | None = Field(default=None, max_length=64)


class WarehouseAiChatResponse(BaseModel):
    reply: str
    model: str
    tools_used: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    continues: int = 0
    mode: str = "semantic"
    cache_hits: int = 0
    plan: dict[str, Any] | None = None


class WarehouseAiPreset(BaseModel):
    id: str
    title: str
    description: str
    prompt: str


class WarehouseAiPresetsResponse(BaseModel):
    items: list[WarehouseAiPreset]


class WarehouseAiStatusResponse(BaseModel):
    configured: bool
    mode: str = "semantic"
    anthropic_key_set: bool
    moysklad_token_set: bool = False
    mcp_url_set: bool
    mcp_auth_set: bool
    model: str | None = None
    router_model: str | None = None
    writer_model: str | None = None
    operations_count: int = 0
    allowlist_count: int = 0
    denylist_count: int = 0
    allowlist_mode: str = "default"
