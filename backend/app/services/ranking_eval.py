from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Photo, PhotoEmbedding, RankingEvalBenchmark
from app.models.feed_settings import FeedSettings
from app.services.feed import load_pair_weights_map, load_weights_map, score_for_photo
from app.services.feed_policy import (
    feed_ranking_mode,
    feed_vector_weight,
    taste_vectors_separate_by_gender,
)
from app.services.photo_embedding import load_embeddings_for_photo_ids
from app.services.taste_vector import load_taste_embedding
from app.services.taste_vector_math import cosine_similarity, min_max_normalize


def _rank_list(ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    return {pid: i for i, pid in enumerate(ids)}


def kendall_tau(order_human: list[uuid.UUID], order_model: list[uuid.UUID]) -> float | None:
    if len(order_human) < 2 or set(order_human) != set(order_model):
        return None
    n = len(order_human)
    rm = _rank_list(order_model)
    concordant = 0
    discordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = order_human[i], order_human[j]
            ra, rb = rm[a], rm[b]
            if ra < rb:
                concordant += 1
            elif ra > rb:
                discordant += 1
    denom = n * (n - 1) / 2
    if denom <= 0:
        return None
    return (concordant - discordant) / denom


def spearman_rho(order_human: list[uuid.UUID], order_model: list[uuid.UUID]) -> float | None:
    if len(order_human) < 2 or set(order_human) != set(order_model):
        return None
    rm = _rank_list(order_model)
    rh = _rank_list(order_human)
    ids = order_human
    n = len(ids)
    mean_h = sum(rh[i] for i in ids) / n
    mean_m = sum(rm[i] for i in ids) / n
    num = 0.0
    dh = 0.0
    dm = 0.0
    for pid in ids:
        dh_i = rh[pid] - mean_h
        dm_i = rm[pid] - mean_m
        num += dh_i * dm_i
        dh += dh_i * dh_i
        dm += dm_i * dm_i
    if dh <= 1e-12 or dm <= 1e-12:
        return None
    return num / (dh**0.5 * dm**0.5)


def top3_overlap(order_human: list[uuid.UUID], order_model: list[uuid.UUID]) -> int:
    h3 = set(order_human[:3])
    m3 = set(order_model[:3])
    return len(h3 & m3)


def settings_snapshot(db: Session) -> dict[str, Any]:
    row = db.get(FeedSettings, 1)
    return {
        "feed_ranking_mode": feed_ranking_mode(db),
        "feed_vector_weight": feed_vector_weight(db),
        "taste_vectors_separate_by_gender": taste_vectors_separate_by_gender(db),
        "card_badge_label": row.card_badge_label if row else None,
    }


def interest_scores_for_photos(
    db: Session,
    photos: list[Photo],
    *,
    user_id: uuid.UUID,
    gender: str,
) -> list[tuple[Photo, float]]:
    """Score как в /feed, но без сортировки по новизне батча."""
    g_norm = gender.strip().lower()
    session_id = uuid.uuid4()  # unused when user_id set
    weights = load_weights_map(db, user_id=user_id, session_id=session_id)
    pair_w = load_pair_weights_map(db, user_id=user_id, session_id=session_id)
    ranking_mode = feed_ranking_mode(db)
    vector_w = feed_vector_weight(db)
    taste_emb = load_taste_embedding(
        db,
        user_id=user_id,
        session_id=session_id,
        collection_gender=g_norm,
    )
    emb_by_id = load_embeddings_for_photo_ids(db, [p.id for p in photos])

    tag_scores = [score_for_photo(p, weights, pair_w) for p in photos]
    vec_raw: list[float] = []
    for p in photos:
        pe = emb_by_id.get(p.id)
        if taste_emb and pe:
            vec_raw.append(max(0.0, cosine_similarity(taste_emb, pe)))
        else:
            vec_raw.append(0.0)
    tag_norm = min_max_normalize(tag_scores)
    vec_norm = min_max_normalize(vec_raw)

    combined: list[float] = []
    for i, _p in enumerate(photos):
        ts = tag_norm[i]
        vs = vec_norm[i]
        if ranking_mode == "tags":
            combined.append(ts)
        elif ranking_mode == "vectors":
            combined.append(vs if taste_emb else ts)
        else:
            if taste_emb and emb_by_id.get(photos[i].id):
                combined.append((1.0 - vector_w) * ts + vector_w * vs)
            else:
                combined.append(ts)

    scored = [(photos[i], combined[i]) for i in range(len(photos))]
    scored.sort(key=lambda x: (-x[1], str(x[0].id)))
    return scored


def model_order_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    photo_ids: list[uuid.UUID],
    gender: str,
) -> list[uuid.UUID]:
    photos = list(
        db.execute(select(Photo).where(Photo.id.in_(photo_ids))).scalars().all()
    )
    by_id = {p.id: p for p in photos}
    ordered_photos = [by_id[pid] for pid in photo_ids if pid in by_id]
    scored = interest_scores_for_photos(db, ordered_photos, user_id=user_id, gender=gender)
    return [p.id for p, _ in scored]


def get_active_benchmark(db: Session, *, gender: str) -> RankingEvalBenchmark | None:
    g = gender.strip().lower()
    return db.execute(
        select(RankingEvalBenchmark)
        .where(
            RankingEvalBenchmark.is_active.is_(True),
            func.lower(RankingEvalBenchmark.gender) == g,
        )
        .options(
            selectinload(RankingEvalBenchmark.items).selectinload(RankingEvalBenchmarkItem.photo),
        )
    ).scalar_one_or_none()


def benchmark_all_embedded(db: Session, benchmark: RankingEvalBenchmark) -> bool:
    if not benchmark.items:
        return False
    ids = [it.photo_id for it in benchmark.items]
    n = db.scalar(
        select(func.count())
        .select_from(PhotoEmbedding)
        .where(PhotoEmbedding.photo_id.in_(ids))
    )
    return int(n or 0) >= len(ids)
