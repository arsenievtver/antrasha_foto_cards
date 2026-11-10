"""бренд.moysklad_id и поля товара на очереди ИИ

Revision ID: 066_collection_inbox
Revises: 065_active_a_clients
Create Date: 2026-11-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "066_collection_inbox"
down_revision: Union[str, None] = "065_active_a_clients"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("brands", sa.Column("moysklad_id", sa.String(length=64), nullable=True))
    op.create_index("ix_brands_moysklad_id", "brands", ["moysklad_id"], unique=True)
    op.add_column("ai_ingest_jobs", sa.Column("moysklad_product_id", sa.String(length=64), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("moysklad_supplier_id", sa.String(length=64), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("supplier_name", sa.String(length=200), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("product_name", sa.String(length=500), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("article", sa.String(length=120), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("barcode", sa.String(length=64), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("path_name", sa.Text(), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("moysklad_upload_status", sa.String(length=20), nullable=True))
    op.add_column("ai_ingest_jobs", sa.Column("moysklad_upload_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_ingest_jobs", "moysklad_upload_error")
    op.drop_column("ai_ingest_jobs", "moysklad_upload_status")
    op.drop_column("ai_ingest_jobs", "path_name")
    op.drop_column("ai_ingest_jobs", "barcode")
    op.drop_column("ai_ingest_jobs", "article")
    op.drop_column("ai_ingest_jobs", "product_name")
    op.drop_column("ai_ingest_jobs", "supplier_name")
    op.drop_column("ai_ingest_jobs", "moysklad_supplier_id")
    op.drop_column("ai_ingest_jobs", "moysklad_product_id")
    op.drop_index("ix_brands_moysklad_id", table_name="brands")
    op.drop_column("brands", "moysklad_id")
