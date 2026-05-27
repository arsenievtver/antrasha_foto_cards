from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class XimilarMatchedItem(BaseModel):
    tag_id: uuid.UUID
    tag_name: str
    group_slug: str
    source: str


class XimilarObjectBucket(BaseModel):
    index: int
    summary: str
    prob: float | None = None
    area: float | None = None
    tag_ids: list[uuid.UUID]
    matched: list[XimilarMatchedItem]
    unmapped: list[dict[str, str]] = Field(default_factory=list)


class XimilarSuggestResponse(BaseModel):
    tag_ids: list[uuid.UUID]
    matched: list[XimilarMatchedItem]
    unmapped: list[dict[str, str]] = Field(default_factory=list)
    objects: list[XimilarObjectBucket] = Field(default_factory=list)
    ximilar: dict[str, Any] = Field(
        default_factory=dict,
        description="Полный JSON-ответ Ximilar (для отладки)",
    )