"""fitting requests from thank-you page

Revision ID: 013_fitting_requests
Revises: 012_moy_sklad
Create Date: 2026-05-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_fitting_requests"
down_revision: Union[str, None] = "012_moy_sklad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fitting_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("match_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_fitting_requests_user_id", "fitting_requests", ["user_id"], unique=False)
    op.create_index("ix_fitting_requests_status", "fitting_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fitting_requests_status", table_name="fitting_requests")
    op.drop_index("ix_fitting_requests_user_id", table_name="fitting_requests")
    op.drop_table("fitting_requests")
