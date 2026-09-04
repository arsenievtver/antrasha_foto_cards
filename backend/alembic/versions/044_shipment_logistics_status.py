"""shipment logistics and delivery status

Revision ID: 044_shipment_logistics
Revises: 043_season_order_plan
Create Date: 2026-09-04

Логистика хранится на поставке, не в payments. is_delivered=False — в пути.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "044_shipment_logistics"
down_revision: Union[str, None] = "043_season_order_plan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shipments",
        sa.Column("logistics_amount_rub", sa.Numeric(16, 2), nullable=True),
    )
    op.add_column(
        "shipments",
        sa.Column("logistics_paid_on", sa.Date(), nullable=True),
    )
    op.add_column(
        "shipments",
        sa.Column(
            "is_delivered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("shipments", "is_delivered", server_default=None)


def downgrade() -> None:
    op.drop_column("shipments", "is_delivered")
    op.drop_column("shipments", "logistics_paid_on")
    op.drop_column("shipments", "logistics_amount_rub")
