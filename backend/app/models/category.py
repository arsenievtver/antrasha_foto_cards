import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

CATEGORY_GENDER_MEN = "men"
CATEGORY_GENDER_WOMEN = "women"
CATEGORY_GENDER_UNISEX = "unisex"
CATEGORY_GENDERS = (CATEGORY_GENDER_MEN, CATEGORY_GENDER_WOMEN, CATEGORY_GENDER_UNISEX)


class Category(Base):
    """Закупочная категория — зеркало группы товаров МойСклад.

    Берём только ветки «Мужская коллекция», «Женская коллекция» и корневую
    «Аксессуары»; Онлайн / Товар ТО / РАДУГА и прочее в закупках не участвуют.
    """

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    moy_sklad_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    path_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order_lines = relationship("BrandOrderCategoryLine", back_populates="category")
