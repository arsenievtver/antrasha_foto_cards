"""действующие клиенты А в недельном отчёте

Revision ID: 065_active_a_clients
Revises: 064_a_clients
Create Date: 2026-11-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "065_active_a_clients"
down_revision: Union[str, None] = "064_a_clients"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "weekly_insight_reports",
        sa.Column("active_clients", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("weekly_insight_reports", "active_clients")
