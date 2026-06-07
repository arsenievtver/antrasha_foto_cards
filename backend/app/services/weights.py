from __future__ import annotations

import math
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.recommendation_model import (
    CLAMP_BASE_WEIGHT,
    PAIR_DELTA_SCALE,
    canonical_tag_pair,
    catalog_importance,
    combined_pair_tier_mult,
    iter_weighted_cross_group_pairs,
    tier_mult,
)
from app.models import Interaction, Photo, User, UserSession, UserTagPairWeight, UserTagWeight


def _maybe_clamp(weight: float, clamp: tuple[float, float] | None) -> float:
    if clamp is None:
        return weight
    lo, hi = clamp
    return max(lo, min(hi, weight))


def upsert_tag_weight(
    db: Session,
    *,
    tag_id: uuid.UUID,
    delta: float,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
    clamp: tuple[float, float] | None = None,
) -> None:
    q = select(UserTagWeight).where(UserTagWeight.tag_id == tag_id)
    if user_id is not None:
        q = q.where(UserTagWeight.user_id == user_id, UserTagWeight.session_id.is_(None))
    else:
        q = q.where(
            UserTagWeight.session_id == session_id,
            UserTagWeight.user_id.is_(None),
        )
    row = db.execute(q).scalar_one_or_none()
    if row:
        row.weight = _maybe_clamp(float(row.weight) + delta, clamp)
    else:
        db.add(
            UserTagWeight(
                user_id=user_id,
                session_id=session_id,
                tag_id=tag_id,
                weight=_maybe_clamp(delta, clamp),
            )
        )


def upsert_pair_weight(
    db: Session,
    *,
    tag_id_lo: uuid.UUID,
    tag_id_hi: uuid.UUID,
    delta: float,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
) -> None:
    if tag_id_lo >= tag_id_hi:
        tag_id_lo, tag_id_hi = canonical_tag_pair(tag_id_lo, tag_id_hi)

    q = select(UserTagPairWeight).where(
        UserTagPairWeight.tag_id_lo == tag_id_lo,
        UserTagPairWeight.tag_id_hi == tag_id_hi,
    )
    if user_id is not None:
        q = q.where(UserTagPairWeight.user_id == user_id, UserTagPairWeight.session_id.is_(None))
    else:
        q = q.where(
            UserTagPairWeight.session_id == session_id,
            UserTagPairWeight.user_id.is_(None),
        )
    row = db.execute(q).scalar_one_or_none()
    if row:
        row.weight = float(row.weight) + delta
    else:
        db.add(
            UserTagPairWeight(
                user_id=user_id,
                session_id=session_id,
                tag_id_lo=tag_id_lo,
                tag_id_hi=tag_id_hi,
                weight=delta,
            )
        )


def apply_swipe_to_weights(
    db: Session,
    photo: Photo,
    *,
    action: str,
    k: float,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
) -> None:
    if action not in ("like", "dislike"):
        return
    sign = 1.0 if action == "like" else -1.0
    owner_session = session_id if user_id is None else None

    for pt in photo.photo_tags:
        tag = getattr(pt, "tag", None)
        grp = getattr(tag, "group", None) if tag else None
        rec_f = catalog_importance(int(tag.recommendation_weight)) if tag else 1.0

        if tag and grp:
            tier = (grp.swipe_tier or "strong").lower()
            mult = tier_mult(grp.swipe_tier, action)
            is_base = tier == "base"
            delta = sign * float(pt.weight) * k * mult * rec_f
            upsert_tag_weight(
                db,
                tag_id=pt.tag_id,
                delta=delta,
                user_id=user_id,
                session_id=owner_session,
                clamp=CLAMP_BASE_WEIGHT if is_base else None,
            )
        else:
            delta = sign * float(pt.weight) * k * rec_f
            upsert_tag_weight(
                db,
                tag_id=pt.tag_id,
                delta=delta,
                user_id=user_id,
                session_id=owner_session,
                clamp=None,
            )

    for pt_i, pt_j, _gs in iter_weighted_cross_group_pairs(photo.photo_tags):
        tag_i = getattr(pt_i, "tag", None)
        tag_j = getattr(pt_j, "tag", None)
        if not tag_i or not tag_j:
            continue
        lo, hi = canonical_tag_pair(pt_i.tag_id, pt_j.tag_id)
        g_i = getattr(tag_i, "group", None)
        g_j = getattr(tag_j, "group", None)
        tier_a = g_i.swipe_tier if g_i else "strong"
        tier_b = g_j.swipe_tier if g_j else "strong"
        geom_w = math.sqrt(float(pt_i.weight) * float(pt_j.weight))
        rec_pair = catalog_importance(
            int((tag_i.recommendation_weight + tag_j.recommendation_weight) / 2)
        )
        tier_mul = combined_pair_tier_mult(tier_a, tier_b, action)
        delta_p = sign * k * PAIR_DELTA_SCALE * geom_w * rec_pair * tier_mul
        upsert_pair_weight(
            db,
            tag_id_lo=lo,
            tag_id_hi=hi,
            delta=delta_p,
            user_id=user_id,
            session_id=owner_session,
        )


def touch_session(db: Session, session_id: uuid.UUID) -> None:
    from datetime import datetime, timezone

    sess = db.get(UserSession, session_id)
    if sess:
        sess.last_activity_at = datetime.now(timezone.utc)


def merge_session_into_user(
    db: Session,
    *,
    session_id: uuid.UUID,
    user: User,
) -> None:
    """Перенос interactions и слияние весов тегов и пар session → user."""
    db.execute(
        update(Interaction)
        .where(
            Interaction.session_id == session_id,
            Interaction.user_id.is_(None),
        )
        .values(user_id=user.id, session_id=None)
    )

    session_weights = db.execute(
        select(UserTagWeight).where(
            UserTagWeight.session_id == session_id,
            UserTagWeight.user_id.is_(None),
        )
    ).scalars().all()

    for sw in session_weights:
        existing = db.execute(
            select(UserTagWeight).where(
                UserTagWeight.user_id == user.id,
                UserTagWeight.tag_id == sw.tag_id,
                UserTagWeight.session_id.is_(None),
            )
        ).scalar_one_or_none()
        if existing:
            existing.weight = float(existing.weight) + float(sw.weight)
        else:
            db.add(
                UserTagWeight(
                    user_id=user.id,
                    session_id=None,
                    tag_id=sw.tag_id,
                    weight=float(sw.weight),
                )
            )
        db.delete(sw)

    session_pairs = db.execute(
        select(UserTagPairWeight).where(
            UserTagPairWeight.session_id == session_id,
            UserTagPairWeight.user_id.is_(None),
        )
    ).scalars().all()

    for sp in session_pairs:
        existing = db.execute(
            select(UserTagPairWeight).where(
                UserTagPairWeight.user_id == user.id,
                UserTagPairWeight.tag_id_lo == sp.tag_id_lo,
                UserTagPairWeight.tag_id_hi == sp.tag_id_hi,
                UserTagPairWeight.session_id.is_(None),
            )
        ).scalar_one_or_none()
        if existing:
            existing.weight = float(existing.weight) + float(sp.weight)
        else:
            db.add(
                UserTagPairWeight(
                    user_id=user.id,
                    session_id=None,
                    tag_id_lo=sp.tag_id_lo,
                    tag_id_hi=sp.tag_id_hi,
                    weight=float(sp.weight),
                )
            )
        db.delete(sp)

    from app.services.web_push import merge_session_push_subscriptions

    merge_session_push_subscriptions(db, session_id=session_id, user_id=user.id)

    # Сессию не удаляем: клиент продолжает слать X-Session-Id после регистрации.
