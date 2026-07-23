"""ai_ingest_jobs.source_mode for flatlay vs on-model prompts

Revision ID: 029_ai_ingest_source_mode
Revises: 028_promo_banner_ctas
Create Date: 2026-07-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_ai_ingest_source_mode"
down_revision: Union[str, None] = "028_promo_banner_ctas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_ingest_jobs",
        sa.Column(
            "source_mode",
            sa.String(length=20),
            nullable=False,
            server_default="flatlay",
        ),
    )
    op.alter_column("ai_ingest_jobs", "source_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("ai_ingest_jobs", "source_mode")
