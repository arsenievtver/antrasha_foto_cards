"""ai_ingest_jobs.photo_id — связь с каталогом до выпуска пакета

Revision ID: 048_ai_ingest_photo
Revises: 047_feed_release
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "048_ai_ingest_photo"
down_revision: Union[str, None] = "047_feed_release"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_ingest_jobs",
        sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_ingest_jobs_photo_id",
        "ai_ingest_jobs",
        "photos",
        ["photo_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_ai_ingest_jobs_photo_id", "ai_ingest_jobs", ["photo_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_ingest_jobs_photo_id", table_name="ai_ingest_jobs")
    op.drop_constraint("fk_ai_ingest_jobs_photo_id", "ai_ingest_jobs", type_="foreignkey")
    op.drop_column("ai_ingest_jobs", "photo_id")
