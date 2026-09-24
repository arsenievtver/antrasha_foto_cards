"""Gift certificates

Revision ID: 052_gift_certificates
Revises: 051_mcp_api_keys
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052_gift_certificates"
down_revision: Union[str, None] = "051_mcp_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gift_certificates",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("nominal", sa.Float(), nullable=True),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employee", sa.String(length=128), nullable=True),
        sa.Column("check_amount", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.Date(), nullable=True),
        sa.Column("used_at", sa.Date(), nullable=True),
        sa.Column("indefinite", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("period", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("last_name", sa.String(length=256), nullable=True),
        sa.Column("phone", sa.String(length=256), nullable=False),
        sa.Column("actual_tran_id", sa.BigInteger(), nullable=True),
        sa.UniqueConstraint("code", name="uq_gift_certificates_code"),
    )
    op.create_table(
        "gift_certificate_transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("cert_id", sa.String(length=26), nullable=False),
        sa.Column(
            "time",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("sms_id", sa.String(length=64), nullable=True),
        sa.Column("sms_sent", sa.Boolean(), nullable=True),
        sa.Column("sms_error", sa.String(length=256), nullable=True),
        sa.Column("confirm_code", sa.String(length=256), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="OPENED"),
        sa.ForeignKeyConstraint(["cert_id"], ["gift_certificates.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_gift_certificate_transactions_cert_id",
        "gift_certificate_transactions",
        ["cert_id"],
    )
    op.execute(
        "CREATE SEQUENCE IF NOT EXISTS gift_certificate_code_seq START WITH 1 INCREMENT BY 1"
    )


def downgrade() -> None:
    op.execute("DROP SEQUENCE IF EXISTS gift_certificate_code_seq")
    op.drop_index(
        "ix_gift_certificate_transactions_cert_id",
        table_name="gift_certificate_transactions",
    )
    op.drop_table("gift_certificate_transactions")
    op.drop_table("gift_certificates")
