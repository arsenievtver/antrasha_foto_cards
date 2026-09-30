"""staff_feedback: спрос от продавцов из work PWA

Revision ID: 058_staff_feedback
Revises: 057_fill_missing_doc_rates
Create Date: 2026-09-30
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "058_staff_feedback"
down_revision: Union[str, None] = "057_fill_missing_doc_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_label", sa.String(length=160), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_staff_feedback_author_user_id",
        "staff_feedback",
        ["author_user_id"],
    )
    op.create_index("ix_staff_feedback_created_at", "staff_feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_staff_feedback_created_at", table_name="staff_feedback")
    op.drop_index("ix_staff_feedback_author_user_id", table_name="staff_feedback")
    op.drop_table("staff_feedback")
