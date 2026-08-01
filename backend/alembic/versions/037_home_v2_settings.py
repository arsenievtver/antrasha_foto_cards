"""home_v2_settings for MEN/WOMEN card images

Revision ID: 037_home_v2_settings
Revises: 036_hero_banners
Create Date: 2026-08-01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037_home_v2_settings"
down_revision: Union[str, None] = "036_hero_banners"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "home_v2_settings",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("image_url_male", sa.String(length=500), nullable=True),
        sa.Column("image_url_female", sa.String(length=500), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute("INSERT INTO home_v2_settings (id) VALUES (1)")


def downgrade() -> None:
    op.drop_table("home_v2_settings")
