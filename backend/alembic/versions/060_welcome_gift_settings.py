"""welcome gift promo settings and one certificate per user

Revision ID: 060_welcome_gift_settings
Revises: 059_season_visibility
Create Date: 2026-10-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "060_welcome_gift_settings"
down_revision: Union[str, None] = "059_season_visibility"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "welcome_gift_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("nominal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("period_days", sa.Integer(), nullable=False, server_default="30"),
    )
    op.execute(
        "INSERT INTO welcome_gift_settings (id, enabled, nominal, period_days) "
        "VALUES (1, false, 0, 30)"
    )
    op.add_column(
        "users",
        sa.Column("welcome_gift_cert_id", sa.String(length=26), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_welcome_gift_cert_id",
        "users",
        "gift_certificates",
        ["welcome_gift_cert_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_users_welcome_gift_cert_id", "users", ["welcome_gift_cert_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_users_welcome_gift_cert_id", "users", type_="unique")
    op.drop_constraint("fk_users_welcome_gift_cert_id", "users", type_="foreignkey")
    op.drop_column("users", "welcome_gift_cert_id")
    op.drop_table("welcome_gift_settings")
