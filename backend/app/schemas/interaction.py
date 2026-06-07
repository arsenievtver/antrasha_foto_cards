import uuid
from typing import Literal

from pydantic import BaseModel, Field


class InteractionCreate(BaseModel):
    photo_id: uuid.UUID
    action: Literal["view", "like", "dislike", "skip", "favorite"]
    view_time_ms: int | None = Field(
        default=None, description="Time spent on card; used for K multiplier"
    )


class InteractionResponse(BaseModel):
    id: uuid.UUID
    ok: bool = True
