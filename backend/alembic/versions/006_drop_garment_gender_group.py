"""remove garment_gender tag group (gender comes from photo row)

Revision ID: 006_drop_garment_gender
Revises: 005_tag_groups
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op

revision: str = "006_drop_garment_gender"
down_revision: Union[str, None] = "005_tag_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM photo_tags
        WHERE tag_id IN (
            SELECT t.id FROM tags t
            JOIN tag_groups g ON t.group_id = g.id
            WHERE g.slug = 'garment_gender'
        )
        """
    )
    op.execute(
        """
        DELETE FROM tags
        WHERE group_id IN (SELECT id FROM tag_groups WHERE slug = 'garment_gender')
        """
    )
    op.execute("DELETE FROM tag_groups WHERE slug = 'garment_gender'")


def downgrade() -> None:
    pass
