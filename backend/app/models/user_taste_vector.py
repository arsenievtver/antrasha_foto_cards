import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.embedding_constants import EMBEDDING_DIM


class UserTasteVector(Base):
    __tablename__ = "user_taste_vectors"
    __table_args__ = (
        CheckConstraint(
            "(user_id IS NOT NULL AND session_id IS NULL) OR "
            "(user_id IS NULL AND session_id IS NOT NULL)",
            name="ck_user_taste_vectors_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    swipe_updates: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="taste_vector")
    session = relationship("UserSession", back_populates="taste_vector")
