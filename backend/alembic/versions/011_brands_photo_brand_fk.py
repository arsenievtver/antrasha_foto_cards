"""brands table; photos.brand_id; ai_ingest_jobs.brand_id

Revision ID: 011_brands
Revises: 010_tag_limits
Create Date: 2026-05-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011_brands"
down_revision: Union[str, None] = "010_tag_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_brands_name", "brands", ["name"], unique=True)

    op.add_column(
        "photos",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_photos_brand_id", "photos", ["brand_id"])
    op.create_foreign_key(
        "fk_photos_brand_id_brands",
        "photos",
        "brands",
        ["brand_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "ai_ingest_jobs",
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_ai_ingest_jobs_brand_id", "ai_ingest_jobs", ["brand_id"])
    op.create_foreign_key(
        "fk_ai_ingest_jobs_brand_id_brands",
        "ai_ingest_jobs",
        "brands",
        ["brand_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_ingest_jobs_brand_id_brands", "ai_ingest_jobs", type_="foreignkey")
    op.drop_index("ix_ai_ingest_jobs_brand_id", table_name="ai_ingest_jobs")
    op.drop_column("ai_ingest_jobs", "brand_id")

    op.drop_constraint("fk_photos_brand_id_brands", "photos", type_="foreignkey")
    op.drop_index("ix_photos_brand_id", table_name="photos")
    op.drop_column("photos", "brand_id")

    op.drop_index("ix_brands_name", table_name="brands")
    op.drop_table("brands")
