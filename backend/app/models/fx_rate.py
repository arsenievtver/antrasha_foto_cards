import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FxRate(Base):
    """Курс EUR/RUB на период — задаётся вручную, подставляется в формы по умолчанию.

    `valid_to` = NULL означает «действует бессрочно с valid_from».
    Документы (заказ / оплата / поставка) хранят свой курс, чтобы суммы в рублях
    не менялись при правке справочника.
    """

    __tablename__ = "fx_rates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    eur_rub: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
