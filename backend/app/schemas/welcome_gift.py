from datetime import date

from pydantic import BaseModel, Field


class WelcomeGiftSettingsOut(BaseModel):
    enabled: bool
    valid_from: date | None = None
    valid_to: date | None = None
    nominal: float
    period_days: int


class WelcomeGiftSettingsPut(BaseModel):
    enabled: bool
    valid_from: date | None = None
    valid_to: date | None = None
    nominal: float = Field(ge=0)
    period_days: int = Field(ge=1, le=3650)


class WelcomeGiftIssuedOut(BaseModel):
    code: str
    amount: float
    url: str


class WelcomeGiftClaimRequest(BaseModel):
    pwa_standalone: bool = False


class WelcomeGiftClaimResponse(BaseModel):
    welcome_gift: WelcomeGiftIssuedOut | None = None
