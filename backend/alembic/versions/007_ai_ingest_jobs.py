"""ai ingest jobs queue for phone photos -> Fashn -> YC

Revision ID: 007_ai_ingest
Revises: 006_drop_garment_gender
Create Date: 2026-05-03

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007_ai_ingest"
down_revision: Union[str, None] = "006_drop_garment_gender"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_ingest_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gender", sa.String(length=10), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("temp_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_bucket", sa.Text(), nullable=True),
        sa.Column("result_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_ingest_jobs_gender", "ai_ingest_jobs", ["gender"])
    op.create_index("ix_ai_ingest_jobs_status", "ai_ingest_jobs", ["status"])
    op.create_index(
        "ix_ai_ingest_jobs_status_created",
        "ai_ingest_jobs",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_ingest_jobs_status_created", table_name="ai_ingest_jobs")
    op.drop_index("ix_ai_ingest_jobs_status", table_name="ai_ingest_jobs")
    op.drop_index("ix_ai_ingest_jobs_gender", table_name="ai_ingest_jobs")
    op.drop_table("ai_ingest_jobs")
