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
