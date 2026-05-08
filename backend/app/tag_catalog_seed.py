"""
Каталог групп и тегов для разметки (идемпотентный seed).

PYTHONPATH=. python -c "from app.database import SessionLocal; from app.tag_catalog_seed import seed_tag_catalog; s=SessionLocal(); seed_tag_catalog(s); s.close()"
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tag, TagGroup

LEGACY_GROUP_SLUG = "legacy"


GROUP_DEFS: list[dict] = [
    # --- basic ---
    dict(
        slug="product_type",
        title="Тип изделия",
        section="basic",
        section_sort=0,
        group_sort=0,
        min_tags=1,
        max_tags=2,
        swipe_tier="base",
    ),
    dict(
        slug="fit",
        title="Посадка",
        section="basic",
        section_sort=0,
        group_sort=1,
        min_tags=1,
        max_tags=1,
        swipe_tier="strong",
    ),
    dict(
        slug="color",
        title="Цвет",
        section="basic",
        section_sort=0,
        group_sort=2,
        min_tags=1,
        max_tags=2,
        swipe_tier="weak",
    ),
    dict(
        slug="material",
        title="Материал",
        section="basic",
        section_sort=0,
        group_sort=3,
        min_tags=1,
        max_tags=2,
        swipe_tier="weak",
    ),
    dict(
        slug="season",
        title="Сезон",
        section="basic",
        section_sort=0,
        group_sort=4,
        min_tags=1,
        max_tags=1,
        swipe_tier="weak",
    ),
    # --- style ---
    dict(
        slug="style",
        title="Стиль",
        section="style_visual",
        section_sort=1,
        group_sort=0,
        min_tags=0,
        max_tags=6,
        swipe_tier="strong",
    ),
    dict(
        slug="print_visual",
        title="Принт / визуал",
        section="style_visual",
        section_sort=1,
        group_sort=1,
        min_tags=0,
        max_tags=4,
        swipe_tier="strong",
    ),
    dict(
        slug="details",
        title="Детали",
        section="style_visual",
        section_sort=1,
        group_sort=2,
        min_tags=0,
        max_tags=6,
        swipe_tier="weak",
    ),
    # --- formality ---
    dict(
        slug="formality",
        title="Формальность",
        section="formality",
        section_sort=2,
        group_sort=0,
        min_tags=1,
        max_tags=4,
        swipe_tier="strong",
    ),
    # --- behavioral ---
    dict(
        slug="visual_perception",
        title="Визуальное восприятие",
        section="behavioral",
        section_sort=3,
        group_sort=0,
        min_tags=0,
        max_tags=4,
        swipe_tier="strong",
    ),
    dict(
        slug="age_feel",
        title="Возрастное ощущение",
        section="behavioral",
        section_sort=3,
        group_sort=1,
        min_tags=0,
        max_tags=1,
        swipe_tier="weak",
    ),
    dict(
        slug="usage_scenario",
        title="Сценарий использования",
        section="behavioral",
        section_sort=3,
        group_sort=2,
        min_tags=0,
        max_tags=6,
        swipe_tier="weak",
    ),
    dict(
        slug="perceived_luxury",
        title="Визуальная «дороговизна»",
        section="behavioral",
        section_sort=3,
        group_sort=3,
        min_tags=0,
        max_tags=1,
        swipe_tier="strong",
    ),
    dict(
        slug="visibility_level",
        title="Уровень заметности",
        section="behavioral",
        section_sort=3,
        group_sort=4,
        min_tags=0,
        max_tags=1,
        swipe_tier="strong",
    ),
]

# (group_slug, [(name, subgroup_key?, sort_order, weight)])
TAG_ROWS: list[tuple[str, list[tuple]]] = [
    (
        "product_type",
        [
            ("футболка", None, 0, 75),
            ("поло", None, 1, 75),
            ("рубашка", None, 2, 75),
            ("блузка", None, 3, 75),
            ("худи", None, 4, 75),
            ("свитшот", None, 5, 75),
            ("свитер", None, 6, 75),
            ("кардиган", None, 7, 75),
            ("пиджак", None, 8, 75),
            ("жакет", None, 9, 75),
            ("пальто", None, 10, 75),
            ("тренч", None, 11, 75),
            ("куртка", None, 12, 75),
            ("пуховик", None, 13, 75),
            ("жилет", None, 14, 75),
            ("джинсы", None, 15, 75),
            ("брюки", None, 16, 75),
            ("чиносы", None, 17, 75),
            ("шорты", None, 18, 75),
            ("юбка", None, 19, 75),
            ("платье", None, 20, 75),
            ("костюм", None, 21, 75),
        ],
    ),
    (
        "fit",
        [
            ("slim", None, 0, 72),
            ("regular", None, 1, 72),
            ("relaxed", None, 2, 72),
            ("oversized", None, 3, 72),
            ("прямой крой", None, 4, 72),
            ("приталенный", None, 5, 72),
            ("свободный", None, 6, 72),
            ("укороченный", None, 7, 72),
            ("удлинённый", None, 8, 72),
        ],
    ),
    (
        "color",
        [
            ("чёрный", "palette", 0, 65),
            ("белый", "palette", 1, 65),
            ("серый", "palette", 2, 65),
            ("бежевый", "palette", 3, 65),
            ("коричневый", "palette", 4, 65),
            ("синий", "palette", 5, 65),
            ("голубой", "palette", 6, 65),
            ("зелёный", "palette", 7, 65),
            ("красный", "palette", 8, 65),
            ("бордовый", "palette", 9, 65),
            ("тёмный", "tone", 10, 60),
            ("светлый", "tone", 11, 60),
            ("яркий", "tone", 12, 60),
            ("пастельный", "tone", 13, 60),
        ],
    ),
    (
        "material",
        [
            ("хлопок", None, 0, 65),
            ("шерсть", None, 1, 65),
            ("кашемир", None, 2, 65),
            ("лён", None, 3, 65),
            ("шёлк", None, 4, 65),
            ("кожа", None, 5, 65),
            ("замша", None, 6, 65),
            ("деним", None, 7, 65),
            ("трикотаж", None, 8, 65),
            ("смесовая", None, 9, 65),
        ],
    ),
    (
        "season",
        [
            ("лето", None, 0, 68),
            ("демисезон", None, 1, 68),
            ("зима", None, 2, 68),
            ("всесезон", None, 3, 68),
        ],
    ),
    (
        "style",
        [
            ("классика", None, 0, 78),
            ("casual", None, 1, 78),
            ("smart casual", None, 2, 78),
            ("business", None, 3, 78),
            ("sport", None, 4, 78),
            ("streetwear", None, 5, 78),
            ("минимализм", None, 6, 78),
            ("базовый", None, 7, 78),
            ("fashion (тренд)", None, 8, 78),
            ("вечерний", None, 9, 78),
            ("милитари", None, 10, 78),
            ("ретро", None, 11, 78),
            ("сафари", None, 12, 78),
        ],
    ),
    (
        "print_visual",
        [
            ("однотонный", None, 0, 62),
            ("логотип", None, 1, 62),
            ("принт", None, 2, 62),
            ("полоска", None, 3, 62),
            ("клетка", None, 4, 62),
            ("графика", None, 5, 62),
            ("надпись", None, 6, 62),
            ("камуфляж", None, 7, 62),
            ("текстура", None, 8, 62),
            ("меланж", None, 9, 62),
        ],
    ),
    (
        "details",
        [
            ("с капюшоном", None, 0, 58),
            ("на молнии", None, 1, 58),
            ("на пуговицах", None, 2, 58),
            ("без воротника", None, 3, 58),
            ("с воротником", None, 4, 58),
            ("высокий ворот", None, 5, 58),
            ("укороченный рукав", None, 6, 58),
            ("длинный рукав", None, 7, 58),
            ("высокая посадка", None, 8, 58),
            ("низкая посадка", None, 9, 58),
        ],
    ),
    (
        "formality",
        [
            ("повседневное", None, 0, 74),
            ("офис", None, 1, 74),
            ("деловое", None, 2, 74),
            ("вечер", None, 3, 74),
            ("спорт", None, 4, 74),
        ],
    ),
    (
        "visual_perception",
        [
            ("спокойный", None, 0, 92),
            ("выразительный", None, 1, 92),
            ("интенсивный", None, 2, 92),
            ("сдержанный", None, 3, 92),
            ("агрессивный", None, 4, 92),
            ("мягкий", None, 5, 92),
        ],
    ),
    (
        "age_feel",
        [
            ("молодёжное", None, 0, 88),
            ("универсальное", None, 1, 88),
            ("взрослое", None, 2, 88),
        ],
    ),
    (
        "usage_scenario",
        [
            ("на каждый день", None, 0, 90),
            ("в офис", None, 1, 90),
            ("на выход", None, 2, 90),
            ("в отпуск", None, 3, 90),
            ("на тренировку", None, 4, 90),
            ("на свидание", None, 5, 90),
            ("в поездку", None, 6, 90),
        ],
    ),
    (
        "perceived_luxury",
        [
            ("выглядит дорого", None, 0, 91),
            ("нейтрально", None, 1, 91),
            ("выглядит просто", None, 2, 91),
        ],
    ),
    (
        "visibility_level",
        [
            ("базовая вещь", None, 0, 89),
            ("акцентная вещь", None, 1, 89),
        ],
    ),
]


def seed_tag_catalog(db: Session) -> dict[str, int]:
    groups_n = 0
    tags_n = 0
    group_ids: dict[str, uuid.UUID] = {}

    for gd in GROUP_DEFS:
        row = db.execute(select(TagGroup).where(TagGroup.slug == gd["slug"])).scalar_one_or_none()
        if row:
            gid = row.id
            for k, v in gd.items():
                setattr(row, k, v)
        else:
            row = TagGroup(**gd)
            db.add(row)
            db.flush()
            gid = row.id
            groups_n += 1
        group_ids[gd["slug"]] = gid

    for slug, rows in TAG_ROWS:
        gid = group_ids[slug]
        for name, subgroup, sort_order, weight in rows:
            exists = db.execute(
                select(Tag.id).where(Tag.group_id == gid, Tag.name == name),
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(
                Tag(
                    id=uuid.uuid4(),
                    name=name,
                    type=slug,
                    group_id=gid,
                    subgroup_key=subgroup,
                    sort_order=sort_order,
                    recommendation_weight=weight,
                    created_by_user_id=None,
                ),
            )
            tags_n += 1

    db.commit()
    return {"groups_added_or_updated": groups_n, "tags_added": tags_n}


def seed_tag_catalog_if_needed(db: Session) -> dict[str, int] | None:
    """Добавляет каталог, если ещё нет группы product_type."""
    has = db.execute(select(TagGroup.id).where(TagGroup.slug == "product_type")).scalar_one_or_none()
    if has:
        return None
    return seed_tag_catalog(db)


if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.database import SessionLocal

    s = SessionLocal()
    try:
        print(seed_tag_catalog(s))
    finally:
        s.close()
