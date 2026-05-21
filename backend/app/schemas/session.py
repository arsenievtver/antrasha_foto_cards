import uuid

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    ref: str | None = Field(default=None, max_length=64)


class SessionCreateResponse(BaseModel):
    session_id: uuid.UUID


class SessionAttributionPatch(BaseModel):
    ref: str = Field(min_length=1, max_length=64)


class SessionAttributionResponse(BaseModel):
    session_id: uuid.UUID
    campaign_id: uuid.UUID | None
    campaign_slug: str | None
    bound: bool
