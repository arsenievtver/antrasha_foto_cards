import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.embedding_constants import EMBEDDING_DIM


class PhotoEmbedding(Base):
    __tablename__ = "photo_embeddings"

    photo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    photo = relationship("Photo", back_populates="photo_embedding")
