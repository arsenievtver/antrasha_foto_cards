import uuid

from pydantic import BaseModel


class SessionCreateResponse(BaseModel):
    session_id: uuid.UUID
