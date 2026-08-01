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


AdminPushAudience = Literal["all", "male", "female", "both"]


class AdminPushStatsResponse(BaseModel):
    configured: bool
    active_total: int = 0
    active_male: int = 0
    active_female: int = 0
    active_both: int = 0


class AdminPushBroadcastRequest(BaseModel):
    title: str = Field(default="ANTRASHA", max_length=80)
    body: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=500)
    audience: AdminPushAudience = "all"
    respect_cooldown: bool = False


class AdminPushBroadcastResponse(BaseModel):
    eligible: int
    sent: int
    failed: int
    skipped: int
