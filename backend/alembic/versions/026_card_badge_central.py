"""Central card badge text + per-photo show_badge flag

Revision ID: 026_card_badge_central
Revises: 025_photo_badge_label
Create Date: 2026-07-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026_card_badge_central"
down_revision: Union[str, None] = "025_photo_badge_label"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "feed_settings",
        sa.Column("card_badge_label", sa.String(40), nullable=True),
    )
    op.add_column(
        "photos",
        sa.Column("show_badge", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Перенос: если уже ставили произвольный badge_label — включаем флаг.
    op.execute(
        """
        UPDATE photos
        SET show_badge = true
        WHERE badge_label IS NOT NULL AND btrim(badge_label) <> ''
        """
    )
    # Текст бейджа — из самого частого значения (или Sale, если пусто).
    op.execute(
        """
        UPDATE feed_settings
        SET card_badge_label = COALESCE(
            (
                SELECT badge_label
                FROM photos
                WHERE badge_label IS NOT NULL AND btrim(badge_label) <> ''
                GROUP BY badge_label
                ORDER BY COUNT(*) DESC
                LIMIT 1
            ),
            'Sale'
        )
        WHERE id = 1 AND (card_badge_label IS NULL OR btrim(card_badge_label) = '')
        """
    )
    op.drop_column("photos", "badge_label")
    op.alter_column("photos", "show_badge", server_default=None)


def downgrade() -> None:
    op.add_column(
        "photos",
        sa.Column("badge_label", sa.String(40), nullable=True),
    )
    op.execute(
        """
        UPDATE photos p
        SET badge_label = (
            SELECT fs.card_badge_label FROM feed_settings fs WHERE fs.id = 1
        )
        WHERE p.show_badge = true
        """
    )
    op.drop_column("photos", "show_badge")
    op.drop_column("feed_settings", "card_badge_label")
