import uuid

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=5, max_length=20)
    pin: str = Field(min_length=4, max_length=12)
    session_id: uuid.UUID = Field(description="Anonymous session to merge into the new user")


class LoginRequest(BaseModel):
    phone: str
    pin: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID | None = None
    role: str = "user"


class MeOut(BaseModel):
    id: uuid.UUID
    phone: str
    display_name: str | None = None
    role: str


class AdminSuperuserLoginRequest(BaseModel):
    username: str
    password: str


class FittingRequestCreateRequest(BaseModel):
    likes: int = Field(ge=0, default=0)
    total: int = Field(ge=0, default=0)
    photo_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    note: str | None = Field(default=None, max_length=1000)


class FittingRequestCreateResponse(BaseModel):
    request_id: uuid.UUID
    status: str
