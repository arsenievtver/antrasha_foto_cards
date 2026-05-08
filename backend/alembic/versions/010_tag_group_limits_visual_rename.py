"""Higher max_tags for multi-outfit photos; rename duplicate visual_perception label

Revision ID: 010_tag_limits
Revises: 009_recommendation_tag
Create Date: 2026-05-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_tag_limits"
down_revision: Union[str, None] = "009_recommendation_tag"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE tag_groups SET max_tags = CASE slug
                WHEN 'product_type' THEN 2
                WHEN 'style' THEN 6
                WHEN 'print_visual' THEN 4
                WHEN 'details' THEN 6
                WHEN 'formality' THEN 4
                WHEN 'usage_scenario' THEN 6
                WHEN 'visual_perception' THEN 4
                ELSE max_tags
            END
            WHERE slug IN (
                'product_type', 'style', 'print_visual', 'details',
                'formality', 'usage_scenario', 'visual_perception'
            )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE tags AS t SET name = 'интенсивный'
            FROM tag_groups AS g
            WHERE t.group_id = g.id
              AND g.slug = 'visual_perception'
              AND t.name = 'яркий'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE tags AS t SET name = 'яркий'
            FROM tag_groups AS g
            WHERE t.group_id = g.id
              AND g.slug = 'visual_perception'
              AND t.name = 'интенсивный'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE tag_groups SET max_tags = CASE slug
                WHEN 'product_type' THEN 1
                WHEN 'style' THEN 3
                WHEN 'print_visual' THEN 2
                WHEN 'details' THEN 3
                WHEN 'formality' THEN 2
                WHEN 'usage_scenario' THEN 2
                WHEN 'visual_perception' THEN 2
                ELSE max_tags
            END
            WHERE slug IN (
                'product_type', 'style', 'print_visual', 'details',
                'formality', 'usage_scenario', 'visual_perception'
            )
            """
        )
    )
