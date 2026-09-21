from __future__ import annotations

import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, get_admin_principal, require_superuser
from app.models import (
    PHOTO_SOURCE_YC_OBJECT_STORAGE,
    Photo,
    PhotoEmbedding,
    RankingEvalBenchmark,
    RankingEvalBenchmarkItem,
    RankingEvalSubmission,
    User,
)
from app.schemas.ranking_eval import (
    RankingEvalBenchmarkCreate,
    RankingEvalBenchmarkDetailOut,
    RankingEvalBenchmarkOut,
    RankingEvalBenchmarkPatch,
    RankingEvalEmbedBatchOut,
    RankingEvalPhotoOut,
    RankingEvalSubmissionDetailOut,
    RankingEvalSubmissionOut,
)
from app.services.photo_embedding import embed_photo_url, upsert_photo_embedding
from app.services.ranking_eval import benchmark_all_embedded
from app.services.yc_storage import public_object_url, put_image_object

log = logging.getLogger("app.admin.ranking_eval")

router = APIRouter(prefix="/admin/ranking-eval", tags=["admin-ranking-eval"])

MAX_PHOTOS_PER_BENCHMARK = 10


def _counts(db: Session, benchmark_id: uuid.UUID) -> tuple[int, int]:
    items = db.execute(
        select(RankingEvalBenchmarkItem.photo_id).where(
            RankingEvalBenchmarkItem.benchmark_id == benchmark_id
        )
    ).scalars().all()
    if not items:
        return 0, 0
    emb = db.scalar(
        select(func.count())
        .select_from(PhotoEmbedding)
        .where(PhotoEmbedding.photo_id.in_(items))
    )
    return len(items), int(emb or 0)


def _benchmark_out(db: Session, row: RankingEvalBenchmark) -> RankingEvalBenchmarkOut:
    pc, ec = _counts(db, row.id)
    return RankingEvalBenchmarkOut(
        id=row.id,
        name=row.name,
        gender=row.gender,
        is_active=row.is_active,
        created_at=row.created_at,
        photo_count=pc,
        embedded_count=ec,
    )


def _detail_out(db: Session, row: RankingEvalBenchmark) -> RankingEvalBenchmarkDetailOut:
    base = _benchmark_out(db, row)
    ids = [it.photo_id for it in row.items]
    emb = set(
        db.execute(
            select(PhotoEmbedding.photo_id).where(PhotoEmbedding.photo_id.in_(ids))
        ).scalars()
        if ids
        else []
    )
    photos: list[RankingEvalPhotoOut] = []
    for it in sorted(row.items, key=lambda x: x.sort_order):
        p = it.photo
        if not p:
            continue
        photos.append(
            RankingEvalPhotoOut(
                photo_id=p.id,
                url=p.url,
                has_embedding=p.id in emb,
                sort_order=it.sort_order,
            )
        )
    return RankingEvalBenchmarkDetailOut(**base.model_dump(), photos=photos)


@router.get("/benchmarks", response_model=list[RankingEvalBenchmarkOut])
def list_benchmarks(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> list[RankingEvalBenchmarkOut]:
    _ = _p
    rows = db.execute(
        select(RankingEvalBenchmark).order_by(RankingEvalBenchmark.created_at.desc())
    ).scalars().all()
    return [_benchmark_out(db, r) for r in rows]


@router.post("/benchmarks", response_model=RankingEvalBenchmarkDetailOut)
def create_benchmark(
    body: RankingEvalBenchmarkCreate,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> RankingEvalBenchmarkDetailOut:
    _ = _su
    row = RankingEvalBenchmark(
        name=body.name.strip(),
        gender=body.gender.strip().lower(),
        is_active=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _detail_out(db, row)


@router.get("/benchmarks/{benchmark_id}", response_model=RankingEvalBenchmarkDetailOut)
def get_benchmark(
    benchmark_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> RankingEvalBenchmarkDetailOut:
    _ = _p
    row = db.execute(
        select(RankingEvalBenchmark)
        .where(RankingEvalBenchmark.id == benchmark_id)
        .options(
            selectinload(RankingEvalBenchmark.items).selectinload(RankingEvalBenchmarkItem.photo),
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Набор не найден")
    return _detail_out(db, row)


@router.patch("/benchmarks/{benchmark_id}", response_model=RankingEvalBenchmarkDetailOut)
def patch_benchmark(
    benchmark_id: uuid.UUID,
    body: RankingEvalBenchmarkPatch,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> RankingEvalBenchmarkDetailOut:
    _ = _su
    row = db.execute(
        select(RankingEvalBenchmark)
        .where(RankingEvalBenchmark.id == benchmark_id)
        .options(selectinload(RankingEvalBenchmark.items))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Набор не найден")
    if body.name is not None:
        row.name = body.name.strip() or row.name
    if body.is_active is not None:
        if body.is_active:
            if not row.items:
                raise HTTPException(status_code=400, detail="Добавьте фото в набор")
            if not benchmark_all_embedded(db, row):
                raise HTTPException(
                    status_code=400,
                    detail="Сначала векторизуйте все фото набора",
                )
            others = db.execute(
                select(RankingEvalBenchmark).where(
                    RankingEvalBenchmark.id != row.id,
                    func.lower(RankingEvalBenchmark.gender) == row.gender.lower(),
                    RankingEvalBenchmark.is_active.is_(True),
                )
            ).scalars().all()
            for o in others:
                o.is_active = False
        row.is_active = bool(body.is_active)
    db.commit()
    db.refresh(row)
    row = db.execute(
        select(RankingEvalBenchmark)
        .where(RankingEvalBenchmark.id == row.id)
        .options(
            selectinload(RankingEvalBenchmark.items).selectinload(RankingEvalBenchmarkItem.photo),
        )
    ).scalar_one()
    return _detail_out(db, row)


@router.post("/benchmarks/{benchmark_id}/photos", response_model=RankingEvalBenchmarkDetailOut)
async def upload_benchmark_photos(
    benchmark_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    files: list[UploadFile] = File(...),
) -> RankingEvalBenchmarkDetailOut:
    _ = _su
    if not settings.yc_s3_configured:
        raise HTTPException(status_code=503, detail="Object Storage не настроен")
    row = db.execute(
        select(RankingEvalBenchmark)
        .where(RankingEvalBenchmark.id == benchmark_id)
        .options(selectinload(RankingEvalBenchmark.items))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Набор не найден")
    current = len(row.items)
    if current + len(files) > MAX_PHOTOS_PER_BENCHMARK:
        raise HTTPException(
            status_code=400,
            detail=f"Не больше {MAX_PHOTOS_PER_BENCHMARK} фото в наборе",
        )
    bucket = (
        settings.yc_bucket_women
        if row.gender.lower() == "female"
        else settings.yc_bucket_men
    )
    next_order = max((it.sort_order for it in row.items), default=-1) + 1
    for uf in files:
        data = await uf.read()
        if not data:
            continue
        ext = ".jpg"
        ct = uf.content_type or "image/jpeg"
        if uf.filename and "." in uf.filename:
            ext = "." + uf.filename.rsplit(".", 1)[-1].lower()[:5]
        if "png" in ct or ext == ".png":
            ct = "image/png"
            ext = ".png"
        elif "webp" in ct or ext == ".webp":
            ct = "image/webp"
            ext = ".webp"
        key = f"eval-benchmark/{benchmark_id}/{uuid.uuid4()}{ext}"
        put_image_object(bucket, key, data, content_type=ct)
        url = public_object_url(bucket, key)
        photo = Photo(
            url=url,
            gender=row.gender.lower(),
            source_type=PHOTO_SOURCE_YC_OBJECT_STORAGE,
            is_active=True,
            feed_visible=False,
            brand="-",
        )
        db.add(photo)
        db.flush()
        db.add(
            RankingEvalBenchmarkItem(
                benchmark_id=row.id,
                photo_id=photo.id,
                sort_order=next_order,
            )
        )
        next_order += 1
    db.commit()
    row = db.execute(
        select(RankingEvalBenchmark)
        .where(RankingEvalBenchmark.id == benchmark_id)
        .options(
            selectinload(RankingEvalBenchmark.items).selectinload(RankingEvalBenchmarkItem.photo),
        )
    ).scalar_one()
    return _detail_out(db, row)


@router.delete("/benchmarks/{benchmark_id}/photos/{photo_id}", status_code=204)
def delete_benchmark_photo(
    benchmark_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> None:
    _ = _su
    item = db.execute(
        select(RankingEvalBenchmarkItem).where(
            RankingEvalBenchmarkItem.benchmark_id == benchmark_id,
            RankingEvalBenchmarkItem.photo_id == photo_id,
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Фото не в наборе")
    db.delete(item)
    db.commit()


@router.post("/benchmarks/{benchmark_id}/embed", response_model=RankingEvalEmbedBatchOut)
def embed_benchmark_photos(
    benchmark_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    limit: int = Query(4, ge=1, le=10),
) -> RankingEvalEmbedBatchOut:
    _ = _su
    row = db.execute(
        select(RankingEvalBenchmark)
        .where(RankingEvalBenchmark.id == benchmark_id)
        .options(selectinload(RankingEvalBenchmark.items).selectinload(RankingEvalBenchmarkItem.photo))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Набор не найден")
    succeeded = 0
    failed: list[dict] = []
    processed = 0
    for it in row.items:
        if processed >= limit:
            break
        p = it.photo
        if not p or db.get(PhotoEmbedding, p.id):
            continue
        processed += 1
        try:
            vec = embed_photo_url(p.url)
            upsert_photo_embedding(db, photo_id=p.id, embedding=vec)
            p.vector_embed_error = None
            succeeded += 1
        except Exception as e:
            p.vector_embed_error = str(e)[:500]
            failed.append({"photo_id": str(p.id), "error": str(e)})
    db.commit()
    return RankingEvalEmbedBatchOut(processed=processed, succeeded=succeeded, failed=failed)


@router.get("/submissions", response_model=list[RankingEvalSubmissionOut])
def list_submissions(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
    benchmark_id: uuid.UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
) -> list[RankingEvalSubmissionOut]:
    _ = _p
    q = (
        select(RankingEvalSubmission, RankingEvalBenchmark, User)
        .join(RankingEvalBenchmark, RankingEvalSubmission.benchmark_id == RankingEvalBenchmark.id)
        .join(User, RankingEvalSubmission.user_id == User.id)
        .order_by(RankingEvalSubmission.created_at.desc())
        .limit(limit)
    )
    if benchmark_id:
        q = q.where(RankingEvalSubmission.benchmark_id == benchmark_id)
    rows = db.execute(q).all()
    out: list[RankingEvalSubmissionOut] = []
    for sub, bench, user in rows:
        label = user.display_name.strip() if user.display_name and user.display_name.strip() else user.phone
        out.append(
            RankingEvalSubmissionOut(
                id=sub.id,
                created_at=sub.created_at,
                benchmark_id=bench.id,
                benchmark_name=bench.name,
                gender=bench.gender,
                user_id=user.id,
                user_label=label,
                human_order=[uuid.UUID(x) for x in sub.human_order],
                model_order=[uuid.UUID(x) for x in sub.model_order],
                kendall_tau=sub.kendall_tau,
                spearman_rho=sub.spearman_rho,
                top3_overlap=sub.top3_overlap,
                settings_snapshot=sub.settings_snapshot or {},
            )
        )
    return out


@router.get("/submissions/{submission_id}", response_model=RankingEvalSubmissionDetailOut)
def get_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> RankingEvalSubmissionDetailOut:
    _ = _p
    row = db.execute(
        select(RankingEvalSubmission, RankingEvalBenchmark, User)
        .join(RankingEvalBenchmark, RankingEvalSubmission.benchmark_id == RankingEvalBenchmark.id)
        .join(User, RankingEvalSubmission.user_id == User.id)
        .where(RankingEvalSubmission.id == submission_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Не найдено")
    sub, bench, user = row
    label = user.display_name.strip() if user.display_name and user.display_name.strip() else user.phone
    photos: list[RankingEvalPhotoOut] = []
    ids = [uuid.UUID(x) for x in sub.human_order]
    photo_rows = db.execute(select(Photo).where(Photo.id.in_(ids))).scalars().all()
    by_id = {p.id: p for p in photo_rows}
    emb = set(
        db.execute(
            select(PhotoEmbedding.photo_id).where(PhotoEmbedding.photo_id.in_(ids))
        ).scalars()
    )
    for i, pid in enumerate(ids):
        p = by_id.get(pid)
        if not p:
            continue
        photos.append(
            RankingEvalPhotoOut(
                photo_id=p.id,
                url=p.url,
                has_embedding=pid in emb,
                sort_order=i,
            )
        )
    return RankingEvalSubmissionDetailOut(
        id=sub.id,
        created_at=sub.created_at,
        benchmark_id=bench.id,
        benchmark_name=bench.name,
        gender=bench.gender,
        user_id=user.id,
        user_label=label,
        human_order=[uuid.UUID(x) for x in sub.human_order],
        model_order=[uuid.UUID(x) for x in sub.model_order],
        kendall_tau=sub.kendall_tau,
        spearman_rho=sub.spearman_rho,
        top3_overlap=sub.top3_overlap,
        settings_snapshot=sub.settings_snapshot or {},
        photos=photos,
    )
