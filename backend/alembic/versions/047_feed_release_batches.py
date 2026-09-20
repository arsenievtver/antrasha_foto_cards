"""feed_release_batches, photos.feed_visible, ingest batch link

Revision ID: 047_feed_release
Revises: 046_vector_taste
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "047_feed_release"
down_revision: Union[str, None] = "046_vector_taste"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feed_release_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("gender", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_embed_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_feed_release_batches_gender", "feed_release_batches", ["gender"])
    op.create_index("ix_feed_release_batches_status", "feed_release_batches", ["status"])

    op.add_column(
        "photos",
        sa.Column("feed_visible", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "photos",
        sa.Column("release_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "photos",
        sa.Column("vector_embed_error", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_photos_release_batch_id",
        "photos",
        "feed_release_batches",
        ["release_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_photos_feed_visible", "photos", ["feed_visible"])
    op.create_index("ix_photos_release_batch_id", "photos", ["release_batch_id"])

    op.add_column(
        "ai_ingest_jobs",
        sa.Column("release_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_ingest_jobs_release_batch_id",
        "ai_ingest_jobs",
        "feed_release_batches",
        ["release_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "feed_settings",
        sa.Column("swipe_chunk_size", sa.Integer(), nullable=False, server_default="10"),
    )


def downgrade() -> None:
    op.drop_column("feed_settings", "swipe_chunk_size")
    op.drop_constraint("fk_ai_ingest_jobs_release_batch_id", "ai_ingest_jobs", type_="foreignkey")
    op.drop_column("ai_ingest_jobs", "release_batch_id")
    op.drop_constraint("fk_photos_release_batch_id", "photos", type_="foreignkey")
    op.drop_index("ix_photos_release_batch_id", table_name="photos")
    op.drop_index("ix_photos_feed_visible", table_name="photos")
    op.drop_column("photos", "vector_embed_error")
    op.drop_column("photos", "release_batch_id")
    op.drop_column("photos", "feed_visible")
    op.drop_table("feed_release_batches")
