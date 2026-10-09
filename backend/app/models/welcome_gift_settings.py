"""Настройки акции: сертификат за регистрацию, установку PWA и push."""

from datetime import date

from sqlalchemy import Boolean, Date, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WelcomeGiftSettings(Base):
    __tablename__ = "welcome_gift_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    nominal: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
