"""outlet_photo_uploads journal for MoySklad photo queue

Revision ID: 038_outlet_photo_uploads
Revises: 037_home_v2_settings
Create Date: 2026-08-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "038_outlet_photo_uploads"
down_revision: Union[str, None] = "037_home_v2_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outlet_photo_uploads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("product_id", sa.String(length=64), nullable=False),
        sa.Column(
            "product_name",
            sa.String(length=500),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("article", sa.String(length=120), nullable=True),
        sa.Column("code", sa.String(length=120), nullable=True),
        sa.Column("barcode", sa.String(length=64), nullable=True),
        sa.Column("path_name", sa.Text(), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("uploaded_by_label", sa.String(length=160), nullable=False),
        sa.Column(
            "transferred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("transferred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_outlet_photo_uploads_product_id", "outlet_photo_uploads", ["product_id"])
    op.create_index("ix_outlet_photo_uploads_article", "outlet_photo_uploads", ["article"])
    op.create_index(
        "ix_outlet_photo_uploads_uploaded_by_user_id",
        "outlet_photo_uploads",
        ["uploaded_by_user_id"],
    )
    op.create_index(
        "ix_outlet_photo_uploads_transferred",
        "outlet_photo_uploads",
        ["transferred"],
    )
    op.create_index("ix_outlet_photo_uploads_created_at", "outlet_photo_uploads", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_outlet_photo_uploads_created_at", table_name="outlet_photo_uploads")
    op.drop_index("ix_outlet_photo_uploads_transferred", table_name="outlet_photo_uploads")
    op.drop_index(
        "ix_outlet_photo_uploads_uploaded_by_user_id",
        table_name="outlet_photo_uploads",
    )
    op.drop_index("ix_outlet_photo_uploads_article", table_name="outlet_photo_uploads")
    op.drop_index("ix_outlet_photo_uploads_product_id", table_name="outlet_photo_uploads")
    op.drop_table("outlet_photo_uploads")
