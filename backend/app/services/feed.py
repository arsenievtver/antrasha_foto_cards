from __future__ import annotations

import logging
import math
import random
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.recommendation_model import (
    SCORE_PAIR_SHARE,
    SCORE_UNARY_SHARE,
    canonical_tag_pair,
    catalog_importance,
    iter_weighted_cross_group_pairs,
)
from app.models import (
    PHOTO_SOURCE_YC_OBJECT_STORAGE,
    FeedReleaseBatch,
    Interaction,
    Photo,
    PhotoTag,
    Tag,
    UserTagPairWeight,
    UserTagWeight,
)
from app.services.feed_policy import (
    feed_ranking_mode,
    feed_require_tagging_review_for_feed,
    feed_swipe_chunk_size,
    feed_vector_weight,
)
from app.services.photo_embedding import load_embeddings_for_photo_ids
from app.services.taste_vector import load_taste_embedding
from app.services.taste_vector_math import cosine_similarity, min_max_normalize

log = logging.getLogger("app.feed")


def load_weights_map(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID,
) -> dict[uuid.UUID, float]:
    if user_id is not None:
        q = select(UserTagWeight).where(
            UserTagWeight.user_id == user_id,
            UserTagWeight.session_id.is_(None),
        )
    else:
        q = select(UserTagWeight).where(
            UserTagWeight.session_id == session_id,
            UserTagWeight.user_id.is_(None),
        )
    rows = db.execute(q).scalars().all()
    return {r.tag_id: float(r.weight) for r in rows}


def load_pair_weights_map(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID,
) -> dict[tuple[uuid.UUID, uuid.UUID], float]:
    if user_id is not None:
        q = select(UserTagPairWeight).where(
            UserTagPairWeight.user_id == user_id,
            UserTagPairWeight.session_id.is_(None),
        )
    else:
        q = select(UserTagPairWeight).where(
            UserTagPairWeight.session_id == session_id,
            UserTagPairWeight.user_id.is_(None),
        )
    rows = db.execute(q).scalars().all()
    return {(r.tag_id_lo, r.tag_id_hi): float(r.weight) for r in rows}


def seen_photo_ids_for_collection(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
    collection_gender_norm: str,
) -> set[uuid.UUID]:
    """Уже просмотренные фото только для этой коллекции (пол фото в БД).

    Раньше брали все interaction.photo_id по сессии без учёта пола: при смене male/female
    в одной сессии счётчик «просмотрено» смешивался с другой коллекцией по смыслу и мог
    давать неполную выдачу (часть id не из этой коллекции не вычиталась, другие эффекты — путаница).
    """
    parts = []
    if user_id is not None:
        parts.append(Interaction.user_id == user_id)
    if session_id is not None:
        parts.append(Interaction.session_id == session_id)
    if not parts:
        return set()
    q = (
        select(Interaction.photo_id)
        .join(Photo, Interaction.photo_id == Photo.id)
        .where(func.lower(Photo.gender) == collection_gender_norm)
        .where(or_(*parts))
        .distinct()
    )
    return set(db.execute(q).scalars().all())


def score_for_photo(
    photo: Photo,
    unary_weights: dict[uuid.UUID, float],
    pair_weights: dict[tuple[uuid.UUID, uuid.UUID], float],
) -> float:
    unary_total = 0.0
    for pt in photo.photo_tags:
        uw = unary_weights.get(pt.tag_id)
        if not uw:
            continue
        tag = getattr(pt, "tag", None)
        rf = catalog_importance(int(tag.recommendation_weight)) if tag else 1.0
        unary_total += float(uw) * float(pt.weight) * rf

    pair_total = 0.0
    for pt_i, pt_j, _gs in iter_weighted_cross_group_pairs(photo.photo_tags):
        ti = getattr(pt_i, "tag", None)
        tj = getattr(pt_j, "tag", None)
        if not ti or not tj:
            continue
        lo, hi = canonical_tag_pair(pt_i.tag_id, pt_j.tag_id)
        pw = pair_weights.get((lo, hi))
        if not pw:
            continue
        ri = catalog_importance(int(ti.recommendation_weight))
        rj = catalog_importance(int(tj.recommendation_weight))
        geom_r = math.sqrt(ri * rj)
        geom_pt = math.sqrt(float(pt_i.weight) * float(pt_j.weight))
        pair_total += float(pw) * geom_pt * geom_r

    return SCORE_UNARY_SHARE * unary_total + SCORE_PAIR_SHARE * pair_total


def fetch_feed_photos(
    db: Session,
    *,
    gender: str,
    limit: int,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID,
    include_seen: bool = False,
) -> tuple[list[Photo], dict[str, float]]:
    g_norm = gender.strip().lower()
    weights = load_weights_map(db, user_id=user_id, session_id=session_id)
    pair_w = load_pair_weights_map(db, user_id=user_id, session_id=session_id)
    seen = seen_photo_ids_for_collection(
        db,
        user_id=user_id,
        session_id=session_id,
        collection_gender_norm=g_norm,
    )

    cond = [
        Photo.is_active.is_(True),
        Photo.feed_visible.is_(True),
        func.lower(Photo.gender) == g_norm,
        Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
    ]
    if feed_require_tagging_review_for_feed(db):
        cond.append(Photo.tagging_review_done.is_(True))

    q = select(Photo).where(*cond).options(
        selectinload(Photo.photo_tags).selectinload(PhotoTag.tag).selectinload(Tag.group),
        selectinload(Photo.release_batch),
    )
    all_for_gender = list(db.execute(q).scalars().unique().all())
    total_active = len(all_for_gender)
    if include_seen:
        candidates = list(all_for_gender)
    else:
        candidates = [p for p in all_for_gender if p.id not in seen]
    loop_rewind = False

    if not candidates:
        if total_active == 0:
            meta = {
                "weight_keys": float(len(weights)),
                "pair_weight_keys": float(len(pair_w)),
                "total_active_for_gender": float(total_active),
                "seen_in_this_collection": float(len(seen)),
            }
            log.warning(
                "feed.empty reason=no_yc_photos gender=%s session_id=%s user_id=%s — "
                "нет активных фото из Object Storage для этого пола (синхронизация бакетов)",
                gender,
                session_id,
                user_id,
            )
            return [], meta

        # Каталог исчерпан — без автоповтора всей ленты (см. чанки / новый пакет).
        loop_rewind = False
        meta = {
            "candidates": float(0),
            "nonzero_scores": float(0),
            "weight_keys": float(len(weights)),
            "pair_weight_keys": float(len(pair_w)),
            "total_active_for_gender": float(total_active),
            "seen_in_this_collection": float(len(seen)),
            "loop_rewind": float(0),
            "catalog_exhausted": float(1),
            "has_more_unseen": float(0),
        }
        log.info(
            "feed.exhausted gender=%s session_id=%s total_active=%s seen=%s",
            gender,
            session_id,
            total_active,
            len(seen),
        )
        return [], meta

    ranking_mode = feed_ranking_mode(db)
    vector_w = feed_vector_weight(db)
    taste_emb = load_taste_embedding(db, user_id=user_id, session_id=session_id)
    emb_by_id = load_embeddings_for_photo_ids(db, [p.id for p in candidates])

    tag_scores = [score_for_photo(p, weights, pair_w) for p in candidates]
    vec_raw: list[float] = []
    for p in candidates:
        pe = emb_by_id.get(p.id)
        if taste_emb and pe:
            vec_raw.append(max(0.0, cosine_similarity(taste_emb, pe)))
        else:
            vec_raw.append(0.0)
    tag_norm = min_max_normalize(tag_scores)
    vec_norm = min_max_normalize(vec_raw)

    combined: list[float] = []
    for i, _p in enumerate(candidates):
        ts = tag_norm[i]
        vs = vec_norm[i]
        if ranking_mode == "tags":
            combined.append(ts)
        elif ranking_mode == "vectors":
            combined.append(vs if taste_emb else ts)
        else:
            if taste_emb and emb_by_id.get(candidates[i].id):
                combined.append((1.0 - vector_w) * ts + vector_w * vs)
            else:
                combined.append(ts)

    scored: list[tuple[Photo, float]] = [
        (p, combined[i]) for i, p in enumerate(candidates)
    ]
    # В ленте сначала показываем самые новые фото из бакета; score остаётся вторым приоритетом.
    def _batch_ts(photo: Photo) -> float:
        batch: FeedReleaseBatch | None = getattr(photo, "release_batch", None)
        if batch and batch.published_at:
            return batch.published_at.timestamp()
        return photo.created_at.timestamp() if photo.created_at else 0.0

    scored.sort(
        key=lambda x: (
            -_batch_ts(x[0]),
            -(x[0].created_at.timestamp() if x[0].created_at else 0.0),
            -x[1],
            random.random(),
        )
    )
    top = [p for p, _ in scored[:limit]]
    has_more_unseen = len(candidates) > len(top)
    meta = {
        "candidates": float(len(candidates)),
        "has_more_unseen": float(1 if has_more_unseen else 0),
        "include_seen": float(1 if include_seen else 0),
        "swipe_chunk_size": float(feed_swipe_chunk_size(db)),
        "nonzero_scores": float(sum(1 for _, s in scored if s != 0)),
        "weight_keys": float(len(weights)),
        "pair_weight_keys": float(len(pair_w)),
        "total_active_for_gender": float(total_active),
        "seen_in_this_collection": float(len(seen)),
        "loop_rewind": float(loop_rewind),
        "ranking_mode": float({"tags": 0, "vectors": 1, "hybrid": 2}.get(ranking_mode, 0)),
        "taste_vector_ready": float(1 if taste_emb else 0),
        "photos_with_embedding": float(len(emb_by_id)),
    }
    log.info(
        "feed.ok gender=%s session_id=%s returned=%s candidates_pool=%s total_active=%s "
        "seen_in_collection=%s loop=%s",
        gender,
        session_id,
        len(top),
        len(candidates),
        total_active,
        len(seen),
        loop_rewind,
    )
    return top, meta
