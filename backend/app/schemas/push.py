from typing import Literal

from pydantic import BaseModel, Field

PushGenderScope = Literal["male", "female", "both"]


class PushKeysIn(BaseModel):
    p256dh: str = Field(min_length=1)
    auth: str = Field(min_length=1)


class PushSubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)
    keys: PushKeysIn
    gender_scope: PushGenderScope = "both"


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(min_length=1)


class PushVapidPublicKeyResponse(BaseModel):
    public_key: str


class PushSubscribeResponse(BaseModel):
    ok: bool = True
