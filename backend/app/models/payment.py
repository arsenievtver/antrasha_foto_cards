import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

PAYMENT_KIND_PREPAYMENT = "prepayment"
PAYMENT_KIND_MAIN = "main"
PAYMENT_KINDS = (PAYMENT_KIND_PREPAYMENT, PAYMENT_KIND_MAIN)


class Payment(Base):
    """Оплата бренду: сумма в евро + курс на дату оплаты и пересчёт в рубли.

    `order_id` необязателен — оплату можно вести по паре сезон+бренд, а привязка
    к заказу уточняет, сколько ещё должны по конкретному заказу.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brand_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("seasons.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    paid_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PAYMENT_KIND_MAIN, index=True
    )
    amount_eur: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    eur_rub_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    amount_rub: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order = relationship("BrandOrder", back_populates="payments")
    season = relationship("Season", back_populates="payments")
    brand = relationship("Brand", back_populates="payments")
