"""ai_ingest_jobs.show_badge for Sale badge on ingest

Revision ID: 027_ai_ingest_show_badge
Revises: 026_card_badge_central
Create Date: 2026-07-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027_ai_ingest_show_badge"
down_revision: Union[str, None] = "026_card_badge_central"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_ingest_jobs",
        sa.Column("show_badge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("ai_ingest_jobs", "show_badge", server_default=None)


def downgrade() -> None:
    op.drop_column("ai_ingest_jobs", "show_badge")
