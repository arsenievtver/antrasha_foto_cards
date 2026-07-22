"""promo_banners gender CTAs + image_fit

Revision ID: 028_promo_banner_ctas
Revises: 027_ai_ingest_show_badge
Create Date: 2026-07-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_promo_banner_ctas"
down_revision: Union[str, None] = "027_ai_ingest_show_badge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "promo_banners",
        sa.Column("show_gender_ctas", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "promo_banners",
        sa.Column("cta_male_label", sa.String(80), nullable=True),
    )
    op.add_column(
        "promo_banners",
        sa.Column("cta_female_label", sa.String(80), nullable=True),
    )
    # fit = вписать без обрезки; cover = заполнить блок (маркетинговый full-bleed)
    op.add_column(
        "promo_banners",
        sa.Column("image_fit", sa.String(16), nullable=False, server_default="fit"),
    )
    op.alter_column("promo_banners", "show_gender_ctas", server_default=None)
    op.alter_column("promo_banners", "image_fit", server_default=None)


def downgrade() -> None:
    op.drop_column("promo_banners", "image_fit")
    op.drop_column("promo_banners", "cta_female_label")
    op.drop_column("promo_banners", "cta_male_label")
    op.drop_column("promo_banners", "show_gender_ctas")
