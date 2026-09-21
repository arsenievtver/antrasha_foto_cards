"""Клиент: оценка ранжирования для участников с ranking_eval_enabled."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import require_user
from app.models import (
    PhotoEmbedding,
    RankingEvalBenchmark,
    RankingEvalBenchmarkItem,
    RankingEvalSubmission,
    User,
)
from app.schemas.ranking_eval import (
    RankingEvalActiveOut,
    RankingEvalPhotoOut,
    RankingEvalSubmitRequest,
    RankingEvalSubmitResponse,
)
from app.services.ranking_eval import (
    benchmark_all_embedded,
    get_active_benchmark,
    kendall_tau,
    model_order_for_user,
    settings_snapshot,
    spearman_rho,
    top3_overlap,
)

router = APIRouter(prefix="/ranking-eval", tags=["ranking-eval"])


def _require_eval_user(user: User = Depends(require_user)) -> User:
    if not user.ranking_eval_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Оценка ранжирования недоступна для этого аккаунта",
        )
    return user


def _photos_out(benchmark: RankingEvalBenchmark, db: Session) -> list[RankingEvalPhotoOut]:
    ids = [it.photo_id for it in benchmark.items]
    emb = set(
        db.execute(
            select(PhotoEmbedding.photo_id).where(PhotoEmbedding.photo_id.in_(ids))
        ).scalars()
        if ids
        else []
    )
    out: list[RankingEvalPhotoOut] = []
    for it in sorted(benchmark.items, key=lambda x: x.sort_order):
        p = it.photo
        if not p:
            continue
        out.append(
            RankingEvalPhotoOut(
                photo_id=p.id,
                url=p.url,
                has_embedding=p.id in emb,
                sort_order=it.sort_order,
            )
        )
    return out


@router.get("/active", response_model=RankingEvalActiveOut)
def get_active(
    db: Session = Depends(get_db),
    user: User = Depends(_require_eval_user),
    gender: str = Query(..., pattern="^(male|female)$"),
) -> RankingEvalActiveOut:
    bench = get_active_benchmark(db, gender=gender)
    if not bench or not bench.items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Нет активного набора для оценки",
        )
    if not benchmark_all_embedded(db, bench):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Набор ещё не готов — не все фото векторизованы",
        )
    existing = db.execute(
        select(RankingEvalSubmission.id).where(
            RankingEvalSubmission.benchmark_id == bench.id,
            RankingEvalSubmission.user_id == user.id,
        )
    ).first()
    return RankingEvalActiveOut(
        benchmark_id=bench.id,
        name=bench.name,
        gender=bench.gender,
        photos=_photos_out(bench, db),
        already_submitted=existing is not None,
    )


@router.post("/submit", response_model=RankingEvalSubmitResponse)
def submit_ranking(
    body: RankingEvalSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_require_eval_user),
) -> RankingEvalSubmitResponse:
    bench = db.execute(
        select(RankingEvalBenchmark)
        .where(RankingEvalBenchmark.id == body.benchmark_id)
        .options(
            selectinload(RankingEvalBenchmark.items).selectinload(RankingEvalBenchmarkItem.photo),
        )
    ).scalar_one_or_none()
    if not bench or not bench.is_active:
        raise HTTPException(status_code=404, detail="Набор не найден или не активен")
    if not benchmark_all_embedded(db, bench):
        raise HTTPException(status_code=503, detail="Набор не готов")

    expected_ids = {it.photo_id for it in bench.items}
    human = list(body.human_order)
    if set(human) != expected_ids or len(human) != len(expected_ids):
        raise HTTPException(status_code=400, detail="human_order должен содержать все фото набора ровно один раз")

    dup = db.execute(
        select(RankingEvalSubmission).where(
            RankingEvalSubmission.benchmark_id == bench.id,
            RankingEvalSubmission.user_id == user.id,
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="Вы уже отправили оценку для этого набора")

    model = model_order_for_user(
        db,
        user_id=user.id,
        photo_ids=[it.photo_id for it in sorted(bench.items, key=lambda x: x.sort_order)],
        gender=bench.gender,
    )
    kt = kendall_tau(human, model)
    sr = spearman_rho(human, model)
    t3 = top3_overlap(human, model)
    row = RankingEvalSubmission(
        benchmark_id=bench.id,
        user_id=user.id,
        human_order=[str(x) for x in human],
        model_order=[str(x) for x in model],
        settings_snapshot=settings_snapshot(db),
        kendall_tau=kt,
        spearman_rho=sr,
        top3_overlap=t3,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return RankingEvalSubmitResponse(
        submission_id=row.id,
        kendall_tau=kt,
        spearman_rho=sr,
        top3_overlap=t3,
    )
