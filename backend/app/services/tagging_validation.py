"""Проверка min/max тегов по группам каталога."""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Tag, TagGroup

_CATALOG_SKIP_SLUGS = frozenset({"legacy", "garment_gender"})


def validate_catalog_tag_selection(
    db: Session,
    tag_ids: list[uuid.UUID],
) -> list[str]:
    """
    Для каждой группы каталога (кроме legacy и garment_gender):
    - min_tags > 0: число выбранных тегов в [min, max]
    - min_tags == 0 (дополнительные): достаточно не превысить max (0 тегов допустимо)
    """
    errors: list[str] = []
    groups = db.scalars(select(TagGroup)).all()
    catalog_groups = [g for g in groups if g.slug not in _CATALOG_SKIP_SLUGS]

    if not tag_ids:
        for g in catalog_groups:
            if g.min_tags > 0:
                errors.append(f"«{g.title}»: минимум {g.min_tags} тег(ов)")
        return errors

    tags = db.scalars(
        select(Tag).where(Tag.id.in_(tag_ids)).options(selectinload(Tag.group)),
    ).all()
    if len(tags) != len(set(tag_ids)):
        return ["Неизвестный или дублирующийся тег"]

    by_group: dict[uuid.UUID, list[Tag]] = defaultdict(list)
    for t in tags:
        by_group[t.group_id].append(t)

    for g in catalog_groups:
        n = len(by_group.get(g.id, []))
        if n > g.max_tags:
            errors.append(f"«{g.title}»: не больше {g.max_tags} тег(ов)")
            continue
        if g.min_tags > 0 and n < g.min_tags:
            errors.append(f"«{g.title}»: минимум {g.min_tags} тег(ов)")
    return errors
