"""swipe_tier on tag groups + user_tag_pair_weights

Revision ID: 009_recommendation_tag
Revises: 008_user_display_name
Create Date: 2026-05-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_recommendation_tag"
down_revision: Union[str, None] = "008_user_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tag_groups",
        sa.Column(
            "swipe_tier",
            sa.String(length=16),
            nullable=False,
            server_default="strong",
        ),
    )
    op.create_index("ix_tag_groups_swipe_tier", "tag_groups", ["swipe_tier"], unique=False)

    op.execute(
        sa.text("UPDATE tag_groups SET swipe_tier = 'base' WHERE slug = 'product_type'")
    )
    op.execute(
        sa.text(
            "UPDATE tag_groups SET swipe_tier = 'weak' WHERE slug IN ("
            "'color', 'material', 'season', 'details', 'age_feel', 'usage_scenario'"
            ")"
        )
    )
    op.execute(
        sa.text(
            "UPDATE tag_groups SET swipe_tier = 'strong' WHERE slug IN ("
            "'fit', 'style', 'print_visual', 'formality', 'visual_perception', "
            "'perceived_luxury', 'visibility_level'"
            ")"
        )
    )

    op.create_table(
        "user_tag_pair_weights",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tag_id_lo", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id_hi", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND session_id IS NULL) OR "
            "(user_id IS NULL AND session_id IS NOT NULL)",
            name="ck_user_tag_pair_weights_owner",
        ),
        sa.CheckConstraint("tag_id_lo < tag_id_hi", name="ck_user_tag_pair_weights_order"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id_lo"], ["tags.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id_hi"], ["tags.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_tag_pair_weights_user_id", "user_tag_pair_weights", ["user_id"])
    op.create_index(
        "ix_user_tag_pair_weights_session_id", "user_tag_pair_weights", ["session_id"]
    )
    op.create_index("ix_user_tag_pair_weights_tag_lo", "user_tag_pair_weights", ["tag_id_lo"])
    op.create_index("ix_user_tag_pair_weights_tag_hi", "user_tag_pair_weights", ["tag_id_hi"])

    op.create_index(
        "uq_user_tag_pair_weights_user_pair",
        "user_tag_pair_weights",
        ["user_id", "tag_id_lo", "tag_id_hi"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_user_tag_pair_weights_session_pair",
        "user_tag_pair_weights",
        ["session_id", "tag_id_lo", "tag_id_hi"],
        unique=True,
        postgresql_where=sa.text("session_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_user_tag_pair_weights_session_pair", table_name="user_tag_pair_weights")
    op.drop_index("uq_user_tag_pair_weights_user_pair", table_name="user_tag_pair_weights")
    op.drop_table("user_tag_pair_weights")

    op.drop_index("ix_tag_groups_swipe_tier", table_name="tag_groups")
    op.drop_column("tag_groups", "swipe_tier")
