"""Giver name and phone on gift certificates

Revision ID: 054_gift_certificate_giver
Revises: 053_gift_certificate_slug
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054_gift_certificate_giver"
down_revision: Union[str, None] = "053_gift_certificate_slug"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gift_certificates", sa.Column("giver_name", sa.String(length=256), nullable=True))
    op.add_column("gift_certificates", sa.Column("giver_phone", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("gift_certificates", "giver_phone")
    op.drop_column("gift_certificates", "giver_name")
