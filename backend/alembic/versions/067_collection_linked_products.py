"""linked_products на ai_ingest_jobs — комплект до 3 штрихкодов

Revision ID: 067_collection_linked_products
Revises: 066_collection_inbox
Create Date: 2026-11-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "067_collection_linked_products"
down_revision: Union[str, None] = "066_collection_inbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_ingest_jobs",
        sa.Column("linked_products", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_ingest_jobs", "linked_products")
