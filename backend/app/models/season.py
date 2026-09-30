import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Season(Base):
    """Сезон закупки, например «Весна-Лето 2027» с кодом ВЛ2027."""

    __tablename__ = "seasons"
    __table_args__ = (
        CheckConstraint(
            "visibility IS NULL OR visibility IN ('previous', 'current', 'next')",
            name="ck_seasons_visibility",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Устарело: дашборд больше не читает этот флаг. Видимость — колонка visibility.
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Сезон раздела «Для заказа» и планов категорий (не больше одного).
    is_order_plan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # previous / current / next. Не больше одного сезона на роль.
    visibility: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    orders = relationship("BrandOrder", back_populates="season")
    payments = relationship("Payment", back_populates="season")
    shipments = relationship("Shipment", back_populates="season")
