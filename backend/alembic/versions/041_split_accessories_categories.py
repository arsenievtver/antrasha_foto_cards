"""split unisex accessories into men/women procurement categories

Revision ID: 041_split_accessories
Revises: 040_modal_videos
Create Date: 2026-08-14

В МойСклад «Аксессуары» остаются одной корневой папкой. Для форм заказа
заводим две закупочные категории: муж и жен. Папку МС оставляем на мужской;
женская без moy_sklad_id (unique), подсказки по остаткам смотрят ту же папку.
Строки женских заказов переводим на новую категорию.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041_split_accessories"
down_revision: Union[str, None] = "040_modal_videos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCESSORIES_MS_ID = "82adf299-8e8b-11e9-9ff4-31500007fc47"
WOMEN_SHOES_MS_ID = "79419e87-9e44-11e9-9ff4-31500007d6fe"


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            UPDATE categories
            SET name = :name, gender = :gender, is_active = true
            WHERE moy_sklad_id = :ms_id
            """
        ),
        {"name": "Аксессуары муж", "gender": "men", "ms_id": ACCESSORIES_MS_ID},
    )

    exists = bind.execute(
        sa.text(
            """
            SELECT id FROM categories
            WHERE gender = 'women' AND name = :name
            """
        ),
        {"name": "Аксессуары жен"},
    ).scalar()

    if exists:
        bind.execute(
            sa.text(
                """
                UPDATE categories
                SET is_active = true, gender = 'women'
                WHERE id = :id
                """
            ),
            {"id": exists},
        )
        women_id = exists
    else:
        sibling_sort = bind.execute(
            sa.text("SELECT sort_order FROM categories WHERE moy_sklad_id = :ms_id"),
            {"ms_id": WOMEN_SHOES_MS_ID},
        ).scalar()
        sort_order = (sibling_sort or 0) + 1
        women_id = str(uuid.uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO categories (
                    id, name, gender, moy_sklad_id, path_name,
                    is_active, sort_order, created_at
                )
                VALUES (
                    :id, :name, :gender, NULL, :path_name,
                    true, :sort_order, now()
                )
                """
            ),
            {
                "id": women_id,
                "name": "Аксессуары жен",
                "gender": "women",
                "path_name": "Женская коллекция",
                "sort_order": sort_order,
            },
        )

    bind.execute(
        sa.text(
            """
            UPDATE brand_order_category_lines AS lines
            SET category_id = :women_id
            FROM categories AS accessories_men, brand_orders AS orders
            WHERE accessories_men.moy_sklad_id = :ms_id
              AND lines.category_id = accessories_men.id
              AND orders.id = lines.order_id
              AND orders.gender = 'women'
            """
        ),
        {"women_id": women_id, "ms_id": ACCESSORIES_MS_ID},
    )


def downgrade() -> None:
    bind = op.get_bind()

    men_id = bind.execute(
        sa.text("SELECT id FROM categories WHERE moy_sklad_id = :ms_id"),
        {"ms_id": ACCESSORIES_MS_ID},
    ).scalar()
    if men_id:
        bind.execute(
            sa.text(
                """
                UPDATE brand_order_category_lines AS lines
                SET category_id = :men_id
                FROM categories AS accessories_women
                WHERE accessories_women.gender = 'women'
                  AND accessories_women.name = :name
                  AND lines.category_id = accessories_women.id
                """
            ),
            {"men_id": men_id, "name": "Аксессуары жен"},
        )

    bind.execute(
        sa.text(
            """
            DELETE FROM categories
            WHERE gender = 'women' AND name = :name AND moy_sklad_id IS NULL
            """
        ),
        {"name": "Аксессуары жен"},
    )

    bind.execute(
        sa.text(
            """
            UPDATE categories
            SET name = :name, gender = :gender
            WHERE moy_sklad_id = :ms_id
            """
        ),
        {"name": "Аксессуары", "gender": "unisex", "ms_id": ACCESSORIES_MS_ID},
    )
