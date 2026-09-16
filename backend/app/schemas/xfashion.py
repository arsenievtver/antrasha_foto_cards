from pydantic import BaseModel, Field


class XfashionVisitRequest(BaseModel):
    ref: str = Field(min_length=1, max_length=64)


class XfashionVisitResponse(BaseModel):
    recorded: bool


class XfashionLeadCreateRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=32)
    name: str | None = Field(default=None, max_length=120)
    contact_channel: str = Field(min_length=1, max_length=32)
    message: str | None = Field(default=None, max_length=1000)
    ref: str | None = Field(default=None, max_length=64)


class XfashionLeadCreateResponse(BaseModel):
    request_id: str
    status: str
