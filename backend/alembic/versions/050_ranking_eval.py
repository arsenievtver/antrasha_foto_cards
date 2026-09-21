"""ranking eval benchmarks + users.ranking_eval_enabled

Revision ID: 050_ranking_eval
Revises: 049_taste_by_gender
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "050_ranking_eval"
down_revision: Union[str, None] = "049_taste_by_gender"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ranking_eval_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "ranking_eval_benchmarks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("gender", sa.String(length=10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ranking_eval_benchmarks_gender", "ranking_eval_benchmarks", ["gender"])
    op.create_index("ix_ranking_eval_benchmarks_is_active", "ranking_eval_benchmarks", ["is_active"])

    op.create_table(
        "ranking_eval_benchmark_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "benchmark_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ranking_eval_benchmarks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "photo_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("photos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_ranking_eval_benchmark_items_benchmark_id",
        "ranking_eval_benchmark_items",
        ["benchmark_id"],
    )
    op.create_index(
        "uq_ranking_eval_benchmark_photo",
        "ranking_eval_benchmark_items",
        ["benchmark_id", "photo_id"],
        unique=True,
    )

    op.create_table(
        "ranking_eval_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "benchmark_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ranking_eval_benchmarks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("human_order", postgresql.JSONB(), nullable=False),
        sa.Column("model_order", postgresql.JSONB(), nullable=False),
        sa.Column("settings_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("kendall_tau", sa.Float(), nullable=True),
        sa.Column("spearman_rho", sa.Float(), nullable=True),
        sa.Column("top3_overlap", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ranking_eval_submissions_benchmark_id",
        "ranking_eval_submissions",
        ["benchmark_id"],
    )
    op.create_index(
        "ix_ranking_eval_submissions_user_id",
        "ranking_eval_submissions",
        ["user_id"],
    )
    op.create_index(
        "uq_ranking_eval_submission_user_benchmark",
        "ranking_eval_submissions",
        ["benchmark_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("ranking_eval_submissions")
    op.drop_table("ranking_eval_benchmark_items")
    op.drop_table("ranking_eval_benchmarks")
    op.drop_column("users", "ranking_eval_enabled")
