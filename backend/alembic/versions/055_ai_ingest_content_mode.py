"""ai_ingest_jobs.source_mode: flatlay/on_model -> single/look

Revision ID: 055_ai_ingest_content_mode
Revises: 054_gift_certificate_giver
"""

from typing import Sequence, Union

from alembic import op

revision: str = "055_ai_ingest_content_mode"
down_revision: Union[str, None] = "054_gift_certificate_giver"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE ai_ingest_jobs SET source_mode = 'single' WHERE source_mode = 'flatlay'",
    )
    op.execute(
        "UPDATE ai_ingest_jobs SET source_mode = 'look' WHERE source_mode = 'on_model'",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE ai_ingest_jobs SET source_mode = 'flatlay' WHERE source_mode = 'single'",
    )
    op.execute(
        "UPDATE ai_ingest_jobs SET source_mode = 'on_model' WHERE source_mode = 'look'",
    )
