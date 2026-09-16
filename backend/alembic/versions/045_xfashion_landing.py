"""xfashion landing: campaign product + visit log

Revision ID: 045_xfashion_landing
Revises: 044_shipment_logistics
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "045_xfashion_landing"
down_revision: Union[str, None] = "044_shipment_logistics"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marketing_campaigns",
        sa.Column(
            "product",
            sa.String(length=32),
            nullable=False,
            server_default="antrasha",
        ),
    )
    op.create_index(
        "ix_marketing_campaigns_product",
        "marketing_campaigns",
        ["product"],
        unique=False,
    )

    op.create_table(
        "xfashion_landing_visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_xfashion_landing_visits_campaign_id",
        "xfashion_landing_visits",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_xfashion_landing_visits_created_at",
        "xfashion_landing_visits",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_xfashion_landing_visits_created_at", table_name="xfashion_landing_visits")
    op.drop_index("ix_xfashion_landing_visits_campaign_id", table_name="xfashion_landing_visits")
    op.drop_table("xfashion_landing_visits")
    op.drop_index("ix_marketing_campaigns_product", table_name="marketing_campaigns")
    op.drop_column("marketing_campaigns", "product")
