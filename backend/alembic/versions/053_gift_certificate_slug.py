"""Short public slug for gift certificate links

Revision ID: 053_gift_certificate_slug
Revises: 052_gift_certificates
"""

from typing import Sequence, Union

import secrets

import sqlalchemy as sa
from alembic import op

revision: str = "053_gift_certificate_slug"
down_revision: Union[str, None] = "052_gift_certificates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_LENGTH = 7


def _slug(used: set[str]) -> str:
    while True:
        value = "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
        if value not in used:
            used.add(value)
            return value


def upgrade() -> None:
    op.add_column("gift_certificates", sa.Column("public_slug", sa.String(length=16), nullable=True))
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM gift_certificates")).fetchall()
    used: set[str] = set()
    for (cert_id,) in rows:
        conn.execute(
            sa.text("UPDATE gift_certificates SET public_slug = :slug WHERE id = :id"),
            {"slug": _slug(used), "id": cert_id},
        )
    op.alter_column("gift_certificates", "public_slug", nullable=False)
    op.create_unique_constraint("uq_gift_certificates_public_slug", "gift_certificates", ["public_slug"])


def downgrade() -> None:
    op.drop_constraint("uq_gift_certificates_public_slug", "gift_certificates", type_="unique")
    op.drop_column("gift_certificates", "public_slug")
