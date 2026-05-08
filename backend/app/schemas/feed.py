import uuid
from typing import Any

from pydantic import BaseModel, Field


class TagOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    weight: float = Field(description="How strongly this tag applies to the photo")


class FeedPhoto(BaseModel):
    id: uuid.UUID
    url: str
    gender: str
    source_type: str
    tags: list[TagOut]


class FeedResponse(BaseModel):
    photos: list[FeedPhoto]
    meta: dict[str, Any] = Field(default_factory=dict)
