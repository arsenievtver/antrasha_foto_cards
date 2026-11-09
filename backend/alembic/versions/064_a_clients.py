"""клиенты А на контроле, привязка сотрудников и нити комментариев

Revision ID: 064_a_clients
Revises: 063_fashn_job_resume
Create Date: 2026-11-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "064_a_clients"
down_revision: Union[str, None] = "063_fashn_job_resume"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "a_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("counterparty_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("last_visit", sa.Date(), nullable=True),
        sa.Column("days_since", sa.Integer(), nullable=True),
        sa.Column("median_gap", sa.Float(), nullable=True),
        sa.Column("visits", sa.Integer(), nullable=True),
        sa.Column("rev_prev12", sa.Float(), nullable=True),
        sa.Column("rev_cur12", sa.Float(), nullable=True),
        sa.Column("brands", postgresql.JSONB(), nullable=True),
        sa.Column("categories", postgresql.JSONB(), nullable=True),
        sa.Column("sizes", sa.Text(), nullable=True),
        sa.Column("avg_discount_pct", sa.Float(), nullable=True),
        sa.Column("markdown_share_pct", sa.Float(), nullable=True),
        sa.Column("picks", postgresql.JSONB(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("first_week", sa.Date(), nullable=True),
        sa.Column("last_week", sa.Date(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("counterparty_id", name="uq_a_clients_counterparty"),
    )
    op.create_table(
        "a_client_weeks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("last_visit", sa.Date(), nullable=True),
        sa.Column("days_since", sa.Integer(), nullable=True),
        sa.Column("visits", sa.Integer(), nullable=True),
        sa.Column("rev_prev12", sa.Float(), nullable=True),
        sa.Column("rev_cur12", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["a_clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["report_id"], ["weekly_insight_reports.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("client_id", "week_start", name="uq_a_client_weeks_client_week"),
    )
    op.create_index("ix_a_client_weeks_client_id", "a_client_weeks", ["client_id"])
    op.create_index("ix_a_client_weeks_week_start", "a_client_weeks", ["week_start"])
    op.create_table(
        "a_client_caretakers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_label", sa.String(length=160), nullable=False),
        sa.Column("author_key", sa.String(length=180), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="comment"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["client_id"], ["a_clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("client_id", "author_key", name="uq_a_client_caretakers_author"),
    )
    op.create_index("ix_a_client_caretakers_client_id", "a_client_caretakers", ["client_id"])
    op.add_column("staff_feedback", sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "staff_feedback",
        sa.Column("thread_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("staff_feedback", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("staff_feedback", sa.Column("client_binding", sa.String(length=16), nullable=True))
    op.create_index("ix_staff_feedback_thread_id", "staff_feedback", ["thread_id"])
    op.create_index("ix_staff_feedback_client_id", "staff_feedback", ["client_id"])
    op.create_foreign_key(
        "fk_staff_feedback_client_id",
        "staff_feedback",
        "a_clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_staff_feedback_client_id", "staff_feedback", type_="foreignkey")
    op.drop_index("ix_staff_feedback_client_id", table_name="staff_feedback")
    op.drop_index("ix_staff_feedback_thread_id", table_name="staff_feedback")
    op.drop_column("staff_feedback", "client_binding")
    op.drop_column("staff_feedback", "client_id")
    op.drop_column("staff_feedback", "thread_locked")
    op.drop_column("staff_feedback", "thread_id")
    op.drop_index("ix_a_client_caretakers_client_id", table_name="a_client_caretakers")
    op.drop_table("a_client_caretakers")
    op.drop_index("ix_a_client_weeks_week_start", table_name="a_client_weeks")
    op.drop_index("ix_a_client_weeks_client_id", table_name="a_client_weeks")
    op.drop_table("a_client_weeks")
    op.drop_table("a_clients")
