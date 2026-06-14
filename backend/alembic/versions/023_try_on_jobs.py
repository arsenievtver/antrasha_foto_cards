"""try_on_jobs queue for VTON 1.5 inference

Revision ID: 023_try_on_jobs
Revises: 022_push_gender_scope
Create Date: 2026-06-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "023_try_on_jobs"
down_revision: Union[str, None] = "022_push_gender_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "try_on_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_image_key", sa.Text(), nullable=False),
        sa.Column("garment_photo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("photos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("garment_url", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result_url", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_try_on_jobs_status", "try_on_jobs", ["status"])
    op.create_index("ix_try_on_jobs_session_id", "try_on_jobs", ["session_id"])
    op.create_index("ix_try_on_jobs_status_created", "try_on_jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_try_on_jobs_status_created", table_name="try_on_jobs")
    op.drop_index("ix_try_on_jobs_session_id", table_name="try_on_jobs")
    op.drop_index("ix_try_on_jobs_status", table_name="try_on_jobs")
    op.drop_table("try_on_jobs")