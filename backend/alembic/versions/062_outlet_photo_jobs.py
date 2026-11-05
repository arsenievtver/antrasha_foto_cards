"""outlet photo jobs: phone uploads, server talks to Fashn

Revision ID: 062_outlet_photo_jobs
Revises: 061_weekly_insight_reports
Create Date: 2026-11-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "062_outlet_photo_jobs"
down_revision: Union[str, None] = "061_weekly_insight_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outlet_photo_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("gender", sa.String(length=10), nullable=False),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("article", sa.String(length=120), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("path_name", sa.Text(), nullable=True),
        sa.Column("product_gender", sa.String(length=10), nullable=True),
        sa.Column("source_name", sa.String(length=80), nullable=False),
        sa.Column("result_name", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_is_superuser",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outlet_photo_jobs_status", "outlet_photo_jobs", ["status"])
    op.create_index("ix_outlet_photo_jobs_owner_user_id", "outlet_photo_jobs", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_outlet_photo_jobs_owner_user_id", table_name="outlet_photo_jobs")
    op.drop_index("ix_outlet_photo_jobs_status", table_name="outlet_photo_jobs")
    op.drop_table("outlet_photo_jobs")
