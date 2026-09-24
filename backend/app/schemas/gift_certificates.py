from datetime import date, datetime

from pydantic import BaseModel, Field


class GiftTransactionOut(BaseModel):
    time: datetime | None
    amount: float
    sms_id: str | None = None
    sms_sent: bool | None = None
    sms_error: str | None = None
    status: str


class GiftCertificateOut(BaseModel):
    id: str
    code: str
    nominal: float | None
    amount: float
    description: str | None
    employee: str | None
    check_amount: float | None
    status: str
    created_at: date | None
    used_at: date | None
    indefinite: bool
    period: int | None
    name: str | None
    last_name: str | None
    phone: str


class GiftCertificatePublicOut(BaseModel):
    nominal: float | None
    amount: float
    code: str
    description: str | None
    status: str
    created_at: date | None
    used_at: date | None
    indefinite: bool
    period: int | None
    name: str | None
    last_name: str | None
    phone: str
    transactions: list[GiftTransactionOut] = Field(default_factory=list)


class GiftCertificateCreate(BaseModel):
    nominal: float
    description: str = ""
    employee: str = ""
    check_amount: float | None = None
    status: str = "ACTIVE"
    created_at: date | None = None
    indefinite: bool = True
    period: int | None = None
    name: str | None = None
    last_name: str | None = None
    phone: str


class GiftCertificateUpdate(BaseModel):
    amount: float | None = None
    description: str | None = None
    employee: str | None = None
    check_amount: float | None = None
    indefinite: bool | None = None
    period: int | None = None
    name: str | None = None
    last_name: str | None = None
    phone: str | None = None


class TelegramSendBody(BaseModel):
    chat_id: int
    image_url: str | None = None
