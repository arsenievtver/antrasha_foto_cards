"""weekly insight reports from MoySklad

Revision ID: 061_weekly_insight_reports
Revises: 060_welcome_gift_settings
Create Date: 2026-10-27
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "061_weekly_insight_reports"
down_revision: Union[str, None] = "060_welcome_gift_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "weekly_insight_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("started_by", sa.String(length=160), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=True),
        sa.Column("watchlist", postgresql.JSONB(), nullable=True),
        sa.Column("summary_md", sa.Text(), nullable=True),
        sa.Column("summary_model", sa.String(length=80), nullable=True),
        sa.Column("ms_requests", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_weekly_insight_reports_week_start", "weekly_insight_reports", ["week_start"])


def downgrade() -> None:
    op.drop_index("ix_weekly_insight_reports_week_start", table_name="weekly_insight_reports")
    op.drop_table("weekly_insight_reports")
