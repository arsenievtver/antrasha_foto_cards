"""Схемы диалога агента закупок."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProcurementAiChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=32_000)


class ProcurementAiChatRequest(BaseModel):
    messages: list[ProcurementAiChatMessage] = Field(min_length=1, max_length=40)


class ProcurementAiChatResponse(BaseModel):
    reply: str
    model: str
    tools_used: list[str] = Field(default_factory=list)
    stop_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    can_write: bool = False


class ProcurementAiPreset(BaseModel):
    id: str
    title: str
    description: str
    prompt: str


class ProcurementAiPresetsResponse(BaseModel):
    items: list[ProcurementAiPreset]


class ProcurementAiStatusResponse(BaseModel):
    configured: bool
    model: str | None = None
    key_present: bool
    key_scope: str | None = None
    can_write: bool
    tools_count: int
