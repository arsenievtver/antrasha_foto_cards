"""Сводка отправки оценки ранжирования для разбора, без сырых векторов."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Interaction,
    Photo,
    RankingEvalBenchmark,
    RankingEvalSubmission,
    User,
    UserTasteVector,
)
from app.services.photo_embedding import load_embeddings_for_photo_ids
from app.services.ranking_eval import settings_snapshot
from app.services.taste_vector import load_taste_embedding
from app.services.taste_vector_math import cosine_similarity


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _user_label(user: User) -> str:
    name = (user.display_name or "").strip()
    return name or user.phone


def _parse_ids(raw: list) -> list[uuid.UUID]:
    return [uuid.UUID(str(item)) for item in raw]


def _rank_map(order: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    return {photo_id: index + 1 for index, photo_id in enumerate(order)}


def embedding_spread(vectors: list[list[float]]) -> dict[str, Any]:
    """Попарный косинус. Близко к 1 — кадры для модели почти неразличимы."""
    pairs: list[float] = []
    for i, left in enumerate(vectors):
        for right in vectors[i + 1 :]:
            pairs.append(cosine_similarity(left, right))
    if not pairs:
        return {"pairs": 0, "min": None, "max": None, "mean": None}
    return {
        "pairs": len(pairs),
        "min": _round(min(pairs)),
        "max": _round(max(pairs)),
        "mean": _round(sum(pairs) / len(pairs)),
    }


def _cosine_stats(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0, "min": None, "max": None, "mean": None, "spread": None}
    low = min(values)
    high = max(values)
    return {
        "n": len(values),
        "min": _round(low),
        "max": _round(high),
        "mean": _round(sum(values) / len(values)),
        "spread": _round(high - low),
    }


def _signals(
    *,
    settings: dict,
    taste_present: bool,
    photo_spread: dict[str, Any],
    taste_stats: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    if settings.get("feed_ranking_mode") == "tags":
        flags.append("ranking_mode_was_tags")
    if not taste_present:
        flags.append("no_taste_vector_for_gender")
    photo_min = photo_spread.get("min")
    if photo_min is not None and photo_min >= 0.9:
        flags.append("benchmark_embeddings_very_close")
    taste_spread = taste_stats.get("spread")
    if taste_stats.get("n") and taste_spread is not None and taste_spread < 0.02:
        flags.append("taste_scores_almost_flat")
    return flags


def list_ranking_eval_submissions(
    db: Session,
    *,
    gender: str | None = None,
    benchmark_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = (
        select(RankingEvalSubmission, RankingEvalBenchmark, User)
        .join(RankingEvalBenchmark, RankingEvalSubmission.benchmark_id == RankingEvalBenchmark.id)
        .join(User, RankingEvalSubmission.user_id == User.id)
        .order_by(RankingEvalSubmission.created_at.desc())
        .limit(limit)
    )
    if gender:
        q = q.where(func.lower(RankingEvalBenchmark.gender) == gender.strip().lower())
    if benchmark_id is not None:
        q = q.where(RankingEvalSubmission.benchmark_id == benchmark_id)
    rows = db.execute(q).all()
    out: list[dict[str, Any]] = []
    for sub, bench, user in rows:
        out.append(
            {
                "id": str(sub.id),
                "created_at": _iso(sub.created_at),
                "user_id": str(user.id),
                "user_label": _user_label(user),
                "benchmark_id": str(bench.id),
                "benchmark_name": bench.name,
                "gender": bench.gender,
                "kendall_tau": _round(sub.kendall_tau),
                "spearman_rho": _round(sub.spearman_rho),
                "top3_overlap": sub.top3_overlap,
                "settings_at_submit": sub.settings_snapshot or {},
            }
        )
    return out


def get_ranking_eval_submission(db: Session, submission_id: uuid.UUID) -> dict[str, Any] | None:
    row = db.execute(
        select(RankingEvalSubmission, RankingEvalBenchmark, User)
        .join(RankingEvalBenchmark, RankingEvalSubmission.benchmark_id == RankingEvalBenchmark.id)
        .join(User, RankingEvalSubmission.user_id == User.id)
        .where(RankingEvalSubmission.id == submission_id)
    ).first()
    if not row:
        return None
    sub, bench, user = row
    human = _parse_ids(sub.human_order or [])
    model = _parse_ids(sub.model_order or [])
    human_rank = _rank_map(human)
    model_rank = _rank_map(model)
    photo_ids = list(dict.fromkeys([*human, *model]))
    photos = db.execute(select(Photo).where(Photo.id.in_(photo_ids))).scalars().all() if photo_ids else []
    by_photo = {photo.id: photo for photo in photos}
    embeddings = load_embeddings_for_photo_ids(db, photo_ids)
    taste = load_taste_embedding(
        db,
        user_id=user.id,
        session_id=uuid.uuid4(),
        collection_gender=bench.gender,
    )
    taste_cosines: list[float] = []
    items: list[dict[str, Any]] = []
    for photo_id in human:
        photo = by_photo.get(photo_id)
        emb = embeddings.get(photo_id)
        cosine = cosine_similarity(taste, emb) if taste and emb else None
        if cosine is not None:
            taste_cosines.append(cosine)
        items.append(
            {
                "photo_id": str(photo_id),
                "url": photo.url if photo else None,
                "human_rank": human_rank.get(photo_id),
                "model_rank": model_rank.get(photo_id),
                "taste_cosine": _round(cosine),
            }
        )
    photo_spread = embedding_spread([embeddings[pid] for pid in photo_ids if pid in embeddings])
    photo_spread["n_photos"] = len(photo_ids)
    photo_spread["n_embedded"] = len(embeddings)
    taste_stats = _cosine_stats(taste_cosines)
    settings = sub.settings_snapshot or {}
    return {
        "id": str(sub.id),
        "created_at": _iso(sub.created_at),
        "user": {"id": str(user.id), "label": _user_label(user)},
        "benchmark": {
            "id": str(bench.id),
            "name": bench.name,
            "gender": bench.gender,
            "is_active": bool(bench.is_active),
        },
        "metrics": {
            "kendall_tau": _round(sub.kendall_tau),
            "spearman_rho": _round(sub.spearman_rho),
            "top3_overlap": sub.top3_overlap,
        },
        "settings_at_submit": settings,
        "settings_now": settings_snapshot(db),
        "items": items,
        "photo_embedding_spread": photo_spread,
        "taste_cosine_to_benchmark": taste_stats,
        "taste_profiles": _taste_profiles(db, user.id),
        "swipes_by_gender": _swipes_by_gender(db, user.id),
        "signals": _signals(
            settings=settings,
            taste_present=taste is not None,
            photo_spread=photo_spread,
            taste_stats=taste_stats,
        ),
    }


def _taste_profiles(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(UserTasteVector)
        .where(UserTasteVector.user_id == user_id)
        .order_by(UserTasteVector.collection_gender.asc().nullsfirst())
    ).scalars()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "collection_gender": row.collection_gender,
                "model_version": row.model_version,
                "has_embedding": row.embedding is not None,
                "swipe_updates": int(row.swipe_updates or 0),
                "updated_at": _iso(row.updated_at),
            }
        )
    return out


def _swipes_by_gender(db: Session, user_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        select(Photo.gender, Interaction.action, func.count())
        .join(Photo, Photo.id == Interaction.photo_id)
        .where(
            Interaction.user_id == user_id,
            Interaction.action.in_(("like", "dislike")),
        )
        .group_by(Photo.gender, Interaction.action)
        .order_by(Photo.gender, Interaction.action)
    ).all()
    return [
        {"gender": gender, "action": action, "count": int(count)}
        for gender, action, count in rows
    ]
