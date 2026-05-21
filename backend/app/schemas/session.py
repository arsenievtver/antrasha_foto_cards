import uuid

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    ref: str | None = Field(default=None, max_length=64)


class SessionCreateResponse(BaseModel):
    session_id: uuid.UUID
