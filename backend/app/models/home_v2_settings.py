"""Singleton-настройки главной /v2 (фото MEN/WOMEN)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class HomeV2Settings(Base):
    __tablename__ = "home_v2_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    image_url_male: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url_female: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )
