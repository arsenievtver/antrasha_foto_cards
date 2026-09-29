"""one brand order per season + brand, gender lives in order lines

Revision ID: 056_single_order_per_season
Revises: 055_ai_ingest_content_mode
Create Date: 2026-09-29

Раньше на бренд в сезоне заводили два заказа (муж и жен), а оплаты и поставки
приходили на бренд целиком и вешались на одну из половин. Теперь заказ один
на пару сезон + бренд, пол и категории — в строках. Строка без категории —
сумма «без разбивки» по полу.

Данные: заказы без строк получают строку «без разбивки» по своему полу, пары
заказов сливаются в самый ранний, оплаты и поставки перепривязываются к заказу
своей пары. Точечно: две записи одной поставки Duno ОЗ26-27 сливаются в одну
(вес и логистика складываются), четыре предоплаты ОЗ26-27, записанные как
основные оплаты, получают kind=prepayment.

Downgrade возвращает схему, но не разделяет слитые заказы обратно; строки
«без разбивки» удаляются, сумма заказа остаётся.
"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "056_single_order_per_season"
down_revision: Union[str, None] = "055_ai_ingest_content_mode"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DUNO_SHIPMENT_KEEP = "0eda62a6-61fb-4ca3-a779-0d5ba39217df"
DUNO_SHIPMENT_MERGED = "eed57900-6490-4a2e-a2c2-d03563393cc4"
PREPAYMENTS_RECORDED_AS_MAIN = (
    "0ff432c9-e187-4799-ab89-0953919211b7",  # Transit 1818.80
    "c138a1a8-441b-4cc1-be7e-90cf8d9ab1b6",  # Duno 4135.80
    "44faca5f-7853-461a-85dc-7d9d9d07bd05",  # Giovanni 874.00
    "62d0c43c-36b9-47df-bfa8-dd6745e39198",  # Diktat 704.58
)


def _add_unsplit_lines(bind) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT o.id, o.gender, o.amount_eur
            FROM brand_orders o
            WHERE o.gender IN ('men', 'women')
              AND NOT EXISTS (
                  SELECT 1 FROM brand_order_category_lines l WHERE l.order_id = o.id
              )
            """
        )
    ).all()
    for order_id, gender, amount in rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO brand_order_category_lines
                    (id, order_id, category_id, gender, amount_eur, comment, created_at)
                VALUES (:id, :order_id, NULL, :gender, :amount, NULL, now())
                """
            ),
            {"id": str(uuid.uuid4()), "order_id": order_id, "gender": gender, "amount": amount},
        )


def _merge_pairs(bind) -> None:
    groups = bind.execute(
        sa.text(
            """
            SELECT season_id, brand_id
            FROM brand_orders
            GROUP BY season_id, brand_id
            HAVING count(*) > 1
            """
        )
    ).all()
    for season_id, brand_id in groups:
        orders = bind.execute(
            sa.text(
                """
                SELECT o.id, o.ordered_on, o.eur_rub_rate, o.has_prepayment,
                       o.prepayment_amount_eur, o.prepayment_due_on, o.comment,
                       EXISTS (
                           SELECT 1 FROM brand_order_category_lines l
                           WHERE l.order_id = o.id
                       ) AS has_lines
                FROM brand_orders o
                WHERE o.season_id = :season_id AND o.brand_id = :brand_id
                ORDER BY o.created_at, o.id
                """
            ),
            {"season_id": season_id, "brand_id": brand_id},
        ).mappings().all()
        without_lines = [str(o["id"]) for o in orders if not o["has_lines"]]
        if without_lines:
            raise RuntimeError(
                "Нельзя слить заказы без строк и без пола men/women: "
                + ", ".join(without_lines)
            )

        keep = orders[0]
        others = [str(o["id"]) for o in orders[1:]]
        prepay = [o for o in orders if o["has_prepayment"] and o["prepayment_amount_eur"]]
        dates = [o["ordered_on"] for o in orders if o["ordered_on"]]
        due_dates = [o["prepayment_due_on"] for o in prepay if o["prepayment_due_on"]]
        rates = [o["eur_rub_rate"] for o in orders if o["eur_rub_rate"] is not None]
        comments: list[str] = []
        for o in orders:
            text = (o["comment"] or "").strip()
            if text and text not in comments:
                comments.append(text)

        params = {"keep": keep["id"], "others": others}
        for table in ("brand_order_category_lines", "payments", "shipments"):
            bind.execute(
                sa.text(
                    f"UPDATE {table} SET order_id = :keep "
                    "WHERE order_id = ANY(CAST(:others AS uuid[]))"
                ),
                params,
            )
        bind.execute(
            sa.text(
                """
                UPDATE brand_orders SET
                    amount_eur = (
                        SELECT COALESCE(sum(amount_eur), 0)
                        FROM brand_order_category_lines WHERE order_id = :keep
                    ),
                    ordered_on = :ordered_on,
                    eur_rub_rate = :rate,
                    has_prepayment = :has_prepayment,
                    prepayment_amount_eur = :prepayment_amount,
                    prepayment_due_on = :prepayment_due_on,
                    comment = :comment,
                    updated_at = now()
                WHERE id = :keep
                """
            ),
            {
                "keep": keep["id"],
                "ordered_on": min(dates) if dates else None,
                "rate": keep["eur_rub_rate"] if keep["eur_rub_rate"] is not None else (
                    rates[0] if rates else None
                ),
                "has_prepayment": bool(prepay),
                "prepayment_amount": (
                    sum(o["prepayment_amount_eur"] for o in prepay) if prepay else None
                ),
                "prepayment_due_on": min(due_dates) if due_dates else None,
                "comment": "; ".join(comments) or None,
            },
        )
        bind.execute(
            sa.text("DELETE FROM brand_orders WHERE id = ANY(CAST(:others AS uuid[]))"),
            params,
        )


def _recompute_order_gender(bind) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE brand_orders o SET gender = CASE
                WHEN g.cnt = 1 THEN g.one_gender
                ELSE 'mixed'
            END
            FROM (
                SELECT order_id, count(DISTINCT gender) AS cnt, min(gender) AS one_gender
                FROM brand_order_category_lines
                GROUP BY order_id
            ) g
            WHERE g.order_id = o.id
            """
        )
    )


def _bind_documents(bind) -> None:
    for table in ("payments", "shipments"):
        bind.execute(
            sa.text(
                f"""
                UPDATE {table} d SET order_id = NULL
                WHERE d.order_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM brand_orders o
                    WHERE o.id = d.order_id
                      AND o.season_id = d.season_id
                      AND o.brand_id = d.brand_id
                )
                """
            )
        )
        bind.execute(
            sa.text(
                f"""
                UPDATE {table} d SET order_id = o.id
                FROM brand_orders o
                WHERE o.season_id = d.season_id
                  AND o.brand_id = d.brand_id
                  AND d.order_id IS DISTINCT FROM o.id
                """
            )
        )


def _fix_known_documents(bind) -> None:
    bind.execute(
        sa.text(
            """
            UPDATE shipments k SET
                amount_eur = k.amount_eur + m.amount_eur,
                weight_kg = COALESCE(k.weight_kg, 0) + COALESCE(m.weight_kg, 0),
                logistics_amount_rub = CASE
                    WHEN k.logistics_amount_rub IS NULL AND m.logistics_amount_rub IS NULL
                        THEN NULL
                    ELSE COALESCE(k.logistics_amount_rub, 0) + COALESCE(m.logistics_amount_rub, 0)
                END,
                amount_rub = CASE
                    WHEN k.eur_rub_rate IS NULL THEN NULL
                    ELSE round((k.amount_eur + m.amount_eur) * k.eur_rub_rate, 2)
                END
            FROM shipments m
            WHERE k.id = :keep AND m.id = :merged
            """
        ),
        {"keep": DUNO_SHIPMENT_KEEP, "merged": DUNO_SHIPMENT_MERGED},
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM shipments
            WHERE id = :merged AND EXISTS (SELECT 1 FROM shipments WHERE id = :keep)
            """
        ),
        {"keep": DUNO_SHIPMENT_KEEP, "merged": DUNO_SHIPMENT_MERGED},
    )
    bind.execute(
        sa.text(
            "UPDATE payments SET kind = 'prepayment' WHERE id = ANY(CAST(:ids AS uuid[]))"
        ),
        {"ids": list(PREPAYMENTS_RECORDED_AS_MAIN)},
    )


def upgrade() -> None:
    bind = op.get_bind()

    op.add_column(
        "brand_order_category_lines",
        sa.Column("gender", sa.String(length=16), nullable=True),
    )
    bind.execute(
        sa.text(
            """
            UPDATE brand_order_category_lines l SET gender = CASE
                WHEN c.gender IN ('men', 'women') THEN c.gender
                WHEN o.gender IN ('men', 'women') THEN o.gender
                ELSE c.gender
            END
            FROM categories c, brand_orders o
            WHERE c.id = l.category_id AND o.id = l.order_id
            """
        )
    )
    op.alter_column("brand_order_category_lines", "category_id", nullable=True)

    _add_unsplit_lines(bind)
    _merge_pairs(bind)
    _recompute_order_gender(bind)
    _bind_documents(bind)
    _fix_known_documents(bind)

    op.alter_column("brand_order_category_lines", "gender", nullable=False)
    op.create_unique_constraint(
        "uq_brand_orders_season_brand", "brand_orders", ["season_id", "brand_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_brand_orders_season_brand", "brand_orders", type_="unique")
    op.execute("DELETE FROM brand_order_category_lines WHERE category_id IS NULL")
    op.alter_column("brand_order_category_lines", "category_id", nullable=False)
    op.drop_column("brand_order_category_lines", "gender")
