"""
Параметры модели весов тегов для ленты: unary по уровням группы + разреженные кросс-групповые пары.

Уровни (swipe_tier на TagGroup): base — тип изделия (слабый штраф на дизлайке + кламп),
strong / weak — вкусовые и уточняющие признаки с разными множителями.
"""

from __future__ import annotations

import math
import uuid

# Множители приращения unary-веса при свайпе по уровню группы
TIER_MULT: dict[str, dict[str, float]] = {
    "base": {"like": 0.42, "dislike": 0.14},
    "strong": {"like": 1.0, "dislike": 1.0},
    "weak": {"like": 0.52, "dislike": 0.42},
}

# После дизлайка/лайка итоговый unary-вес тегов уровня base ограничиваем (анти-«рубашки плохие»)
CLAMP_BASE_WEIGHT: tuple[float, float] = (-0.36, 1.08)

# Разрешённые пары slug групп (лексикографически упорядоченная пара)
ALLOWED_GROUP_PAIR_SLUGS: frozenset[tuple[str, str]] = frozenset(
    {
        ("details", "product_type"),
        ("fit", "print_visual"),
        ("fit", "product_type"),
        ("fit", "style"),
        ("formality", "product_type"),
        ("print_visual", "product_type"),
        ("print_visual", "style"),
        ("style", "product_type"),
    }
)

# Масштаб приращения весов пар относительно силы связей на фото (вместе с SCORE_* задаёт баланс)
PAIR_DELTA_SCALE = 0.92

# Доля unary vs пары в итоговом score карточки (пары переносят контекст «тип + визуал» и т.п.)
SCORE_UNARY_SHARE = 0.34
SCORE_PAIR_SHARE = 0.66

# Нормализация catalog recommendation_weight (сид ~50–92, якорь 75)
REC_WEIGHT_ANCHOR = 75.0
REC_WEIGHT_FACTOR_MIN = 0.38
REC_WEIGHT_FACTOR_MAX = 1.62


def catalog_importance(rec_weight: int) -> float:
    """Масштаб влияния тега из каталога (без поломки старых данных)."""
    x = float(rec_weight) / REC_WEIGHT_ANCHOR
    return max(REC_WEIGHT_FACTOR_MIN, min(REC_WEIGHT_FACTOR_MAX, x))


def tier_mult(swipe_tier: str | None, action: str) -> float:
    t = (swipe_tier or "strong").lower()
    row = TIER_MULT.get(t) or TIER_MULT["strong"]
    return float(row[action])


def combined_pair_tier_mult(tier_a: str | None, tier_b: str | None, action: str) -> float:
    """Геометрическое среднее множителей уровней — пары не перетягивают за счёт одного «жёсткого» тира."""
    return math.sqrt(tier_mult(tier_a, action) * tier_mult(tier_b, action))


def canonical_tag_pair(tag_id_a: uuid.UUID, tag_id_b: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    if tag_id_a < tag_id_b:
        return tag_id_a, tag_id_b
    return tag_id_b, tag_id_a


def iter_weighted_cross_group_pairs(
    photo_tags: list,
) -> list[tuple[object, object, tuple[str, str]]]:
    """
    Возвращает пары PhotoTag с каноническим tuple slug групп для проверки ALLOWED_GROUP_PAIR_SLUGS.
    Требует загруженных pt.tag и pt.tag.group.
    """
    items: list[tuple[object, str]] = []
    for pt in photo_tags:
        tag = getattr(pt, "tag", None)
        grp = getattr(tag, "group", None) if tag else None
        if not tag or not grp:
            continue
        items.append((pt, grp.slug))

    out: list[tuple[object, object, tuple[str, str]]] = []
    for i in range(len(items)):
        pt_i, si = items[i]
        for j in range(i + 1, len(items)):
            pt_j, sj = items[j]
            if si == sj:
                continue
            a, b = (si, sj) if si < sj else (sj, si)
            if (a, b) in ALLOWED_GROUP_PAIR_SLUGS:
                out.append((pt_i, pt_j, (a, b)))
    return out
