import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased, selectinload
from starlette.responses import Response

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, get_admin_principal, require_superuser
from app.models import (
    PHOTO_SOURCE_YC_OBJECT_STORAGE,
    Brand,
    FeedSettings,
    FittingRequest,
    Interaction,
    Photo,
    PhotoTag,
    Tag,
    TagGroup,
    User,
    UserRole,
    UserTagPairWeight,
    UserTagWeight,
)
from app.schemas.admin import (
    AdminCatalogGroupOut,
    AdminCatalogSectionOut,
    AdminCatalogSubgroupOut,
    AdminCatalogTagOut,
    AdminPhotoBulkDeleteItem,
    AdminPhotoListResponse,
    AdminPhotoOut,
    AdminPhotosBulkDeleteBody,
    AdminPhotosBulkDeleteResponse,
    AdminPhotoTagOut,
    AdminPhotoTagsPutBody,
    AdminBrandCreateRequest,
    FeedSettingsOut,
    FeedSettingsPatch,
    AdminFittingRequestListResponse,
    AdminFittingRequestOut,
    AdminBrandListResponse,
    AdminBrandOut,
    AdminStatsOut,
    AdminTagCatalogResponse,
    AdminTagCreateRequest,
    AdminTagListResponse,
    AdminTagOut,
    AdminTagUpdateRequest,
    AdminUserCreateRequest,
    AdminUserDetailOut,
    AdminUserListResponse,
    AdminUserOut,
    AdminUserTagPairWeightStat,
    AdminUserTagWeightStat,
    AdminUserUpdateRequest,
    AdminWorkerTagCreateBody,
    assert_pin_for_role,
)
from app.security import hash_pin
from app.experimental.ximilar.router import router as _ximilar_experimental_router
from app.services.tagging_validation import validate_catalog_tag_selection
from app.services.yc_photo_sync import run_sync_job_commit
from app.services.yc_storage import delete_photo_file_from_object_storage

TAGGING_CLAIM_TTL = timedelta(minutes=5)

SUBGROUP_LABELS = {
    "palette": "Основная палитра",
    "tone": "Доп. оттенок",
}

log = logging.getLogger("app.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


def _pin_validation_http(role: str, pin: str) -> None:
    try:
        assert_pin_for_role(role, pin)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


def _photo_out(p: Photo, *, viewer_user_id: uuid.UUID | None = None) -> AdminPhotoOut:
    tags = []
    for pt in p.photo_tags:
        gslug = None
        if pt.tag.group:
            gslug = pt.tag.group.slug
        tags.append(
            AdminPhotoTagOut(
                tag_id=pt.tag_id,
                name=pt.tag.name,
                type=pt.tag.type,
                weight=float(pt.weight),
                group_slug=gslug,
            ),
        )
    now = datetime.now(timezone.utc)
    claim_expires_at = None
    claim_is_mine = False
    if (
        p.tagging_claimed_until is not None
        and p.tagging_claimed_until > now
        and p.tagging_claimed_by_id is not None
    ):
        claim_expires_at = p.tagging_claimed_until
        if viewer_user_id is not None and p.tagging_claimed_by_id == viewer_user_id:
            claim_is_mine = True
    return AdminPhotoOut(
        id=p.id,
        url=p.url,
        gender=p.gender,
        is_active=p.is_active,
        created_at=p.created_at,
        tags=tags,
        tagging_uncertain=p.tagging_uncertain,
        tagging_review_done=p.tagging_review_done,
        worker_signal_love=p.worker_signal_love,
        worker_signal_hit=p.worker_signal_hit,
        worker_signal_hard=p.worker_signal_hard,
        brand_id=p.brand_id,
        brand=p.brand,
        price_segment=p.price_segment,
        moy_sklad_id=p.moy_sklad_id,
        tags_version=p.tags_version,
        claim_expires_at=claim_expires_at,
        claim_is_mine=claim_is_mine,
    )


def _expire_stale_tagging_claims(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        update(Photo)
        .where(
            Photo.tagging_claimed_until.is_not(None),
            Photo.tagging_claimed_until < now,
        )
        .values(tagging_claimed_by_id=None, tagging_claimed_until=None),
    )


def _tagging_queue_pending_clause():
    """Очередь: фото ещё не прошли полную разметку (tagging_review_done)."""
    return Photo.tagging_review_done.is_(False)


def _tag_catalog_selectinloads():
    return (
        selectinload(Photo.photo_tags)
        .selectinload(PhotoTag.tag)
        .selectinload(Tag.group)
    )


def build_tag_catalog(db: Session) -> AdminTagCatalogResponse:
    groups = db.scalars(
        select(TagGroup)
        .where(TagGroup.slug.not_in(("legacy", "garment_gender")))
        .order_by(TagGroup.section_sort, TagGroup.group_sort),
    ).all()
    if not groups:
        return AdminTagCatalogResponse(sections=[])
    gids = [g.id for g in groups]
    tag_rows = db.scalars(
        select(Tag).where(Tag.group_id.in_(gids)).order_by(Tag.sort_order, Tag.name),
    ).all()
    by_gid: dict[uuid.UUID, list[Tag]] = {}
    for t in tag_rows:
        by_gid.setdefault(t.group_id, []).append(t)

    sections_map: dict[str, dict] = {}

    def subgroup_sort_key(sk: str | None) -> tuple:
        order = {None: 0, "palette": 1, "tone": 2}
        return (order.get(sk, 50), sk or "")

    for g in groups:
        sec_key = g.section
        if sec_key not in sections_map:
            sections_map[sec_key] = {"sort": g.section_sort, "groups": []}
        tglist = by_gid.get(g.id, [])
        sub_map: dict[str | None, list[Tag]] = {}
        for t in tglist:
            sub_map.setdefault(t.subgroup_key, []).append(t)
        subgroups_out: list[AdminCatalogSubgroupOut] = []
        for sk in sorted(sub_map.keys(), key=subgroup_sort_key):
            if sk is None:
                label = "Теги"
            else:
                label = SUBGROUP_LABELS.get(sk, sk)
            subgroups_out.append(
                AdminCatalogSubgroupOut(
                    key=sk,
                    label=label,
                    tags=[
                        AdminCatalogTagOut(
                            id=t.id,
                            name=t.name,
                            subgroup_key=t.subgroup_key,
                            sort_order=t.sort_order,
                            recommendation_weight=t.recommendation_weight,
                        )
                        for t in sub_map[sk]
                    ],
                ),
            )
        sections_map[sec_key]["groups"].append(
            AdminCatalogGroupOut(
                id=g.id,
                slug=g.slug,
                title=g.title,
                min_tags=g.min_tags,
                max_tags=g.max_tags,
                swipe_tier=g.swipe_tier,
                subgroups=subgroups_out,
            ),
        )

    ordered_sections = sorted(sections_map.items(), key=lambda x: x[1]["sort"])
    sections = [
        AdminCatalogSectionOut(key=k, sort=v["sort"], groups=v["groups"]) for k, v in ordered_sections
    ]
    return AdminTagCatalogResponse(sections=sections)


def _viewer_id(principal: AdminPrincipal) -> uuid.UUID | None:
    return principal.user.id if principal.user else None


@router.get("/stats", response_model=AdminStatsOut)
def admin_stats(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminStatsOut:
    users = db.scalar(select(func.count()).select_from(User)) or 0
    workers = (
        db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.worker.value),
        )
        or 0
    )
    yc = Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE
    photos = db.scalar(select(func.count()).select_from(Photo).where(yc)) or 0
    active_photos = (
        db.scalar(
            select(func.count()).select_from(Photo).where(yc, Photo.is_active.is_(True)),
        )
        or 0
    )
    tags = db.scalar(select(func.count()).select_from(Tag)) or 0
    interactions = db.scalar(select(func.count()).select_from(Interaction)) or 0
    photos_male = (
        db.scalar(
            select(func.count())
            .select_from(Photo)
            .where(yc, func.lower(Photo.gender) == "male"),
        )
        or 0
    )
    photos_female = (
        db.scalar(
            select(func.count())
            .select_from(Photo)
            .where(yc, func.lower(Photo.gender) == "female"),
        )
        or 0
    )
    return AdminStatsOut(
        users=users,
        workers=workers,
        photos=photos,
        active_photos=active_photos,
        tags=tags,
        interactions=interactions,
        photos_male=photos_male,
        photos_female=photos_female,
    )


@router.get("/feed-settings", response_model=FeedSettingsOut)
def get_feed_settings(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> FeedSettingsOut:
    row = db.get(FeedSettings, 1)
    if row is None:
        return FeedSettingsOut(require_tagging_review_for_feed=False)
    return FeedSettingsOut(require_tagging_review_for_feed=row.require_tagging_review_for_feed)


@router.patch("/feed-settings", response_model=FeedSettingsOut)
def patch_feed_settings(
    body: FeedSettingsPatch,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> FeedSettingsOut:
    _ = _su
    row = db.get(FeedSettings, 1)
    if row is None:
        row = FeedSettings(
            id=1,
            require_tagging_review_for_feed=body.require_tagging_review_for_feed,
        )
        db.add(row)
    else:
        row.require_tagging_review_for_feed = body.require_tagging_review_for_feed
    db.commit()
    db.refresh(row)
    return FeedSettingsOut(require_tagging_review_for_feed=row.require_tagging_review_for_feed)


@router.get("/photos", response_model=AdminPhotoListResponse)
def list_photos(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    gender: str | None = Query(None, description="male | female"),
    active_only: bool = Query(False),
    tagging_done_only: bool = Query(False, description="только завершённая разметка"),
    brand_id: uuid.UUID | None = Query(None, description="фильтр по бренду"),
) -> AdminPhotoListResponse:
    _expire_stale_tagging_claims(db)
    db.flush()
    cond = [Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE]
    if gender:
        cond.append(func.lower(Photo.gender) == gender.strip().lower())
    if active_only:
        cond.append(Photo.is_active.is_(True))
    if tagging_done_only:
        cond.append(Photo.tagging_review_done.is_(True))
    if brand_id is not None:
        cond.append(Photo.brand_id == brand_id)
    count_q = select(func.count()).select_from(Photo)
    if cond:
        count_q = count_q.where(*cond)
    total = db.scalar(count_q) or 0
    q = select(Photo)
    if cond:
        q = q.where(*cond)
    q = (
        q.order_by(Photo.created_at.desc())
        .offset(skip)
        .limit(limit)
        .options(_tag_catalog_selectinloads())
    )
    rows = db.scalars(q).unique().all()
    vid = _viewer_id(principal)
    return AdminPhotoListResponse(
        items=[_photo_out(p, viewer_user_id=vid) for p in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/photos/{photo_id}", response_model=AdminPhotoOut)
def get_admin_photo(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    """Одно фото — для обновления карточки после конфликта версии и т.п."""
    _expire_stale_tagging_claims(db)
    db.flush()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id, Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return _photo_out(photo, viewer_user_id=_viewer_id(principal))


@router.post("/photos/sync-object-storage")
def sync_photos_from_object_storage(
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> dict:
    _ = _principal
    if not settings.yc_s3_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yandex S3 ключи не настроены",
        )
    return run_sync_job_commit(settings, deactivate_not_in_bucket=True)


@router.get("/tagging-queue", response_model=AdminPhotoListResponse)
def list_tagging_queue(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
) -> AdminPhotoListResponse:
    """Фото с неполной разметкой (число тегов ≤ лимита). У сотрудников скрыты чужие брони."""
    _expire_stale_tagging_claims(db)
    db.flush()
    now = datetime.now(timezone.utc)
    cond = [
        Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
        Photo.is_active.is_(True),
        _tagging_queue_pending_clause(),
    ]
    if principal.role == "worker":
        assert principal.user is not None
        wid = principal.user.id
        cond.append(
            or_(
                Photo.tagging_claimed_until.is_(None),
                Photo.tagging_claimed_until < now,
                Photo.tagging_claimed_by_id == wid,
            ),
        )
    count_q = select(func.count()).select_from(Photo).where(*cond)
    total = db.scalar(count_q) or 0
    q = (
        select(Photo)
        .where(*cond)
        .order_by(Photo.created_at.asc())
        .offset(skip)
        .limit(limit)
        .options(_tag_catalog_selectinloads())
    )
    rows = db.scalars(q).unique().all()
    vid = _viewer_id(principal)
    return AdminPhotoListResponse(
        items=[_photo_out(p, viewer_user_id=vid) for p in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/tagging-queue/acquire-next", response_model=AdminPhotoOut)
def acquire_next_tagging_photo(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    """Атомарно выдаёт следующее фото без тегов и ставит бронь (только сотрудник)."""
    _expire_stale_tagging_claims(db)
    db.flush()
    now = datetime.now(timezone.utc)

    if principal.role == "superuser":
        photo = db.execute(
            select(Photo)
            .where(
                Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
                Photo.is_active.is_(True),
                _tagging_queue_pending_clause(),
            )
            .order_by(Photo.created_at.asc())
            .limit(1)
            .options(_tag_catalog_selectinloads()),
        ).scalar_one_or_none()
        if not photo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Нет фото в очереди разметки",
            )
        return _photo_out(photo)

    if principal.role != "worker" or principal.user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только для сотрудников",
        )
    wid = principal.user.id
    claim_ok = or_(
        Photo.tagging_claimed_until.is_(None),
        Photo.tagging_claimed_until < now,
        Photo.tagging_claimed_by_id == wid,
    )
    photo = db.execute(
        select(Photo)
        .where(
            Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
            Photo.is_active.is_(True),
            _tagging_queue_pending_clause(),
            claim_ok,
        )
        .order_by(Photo.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one_or_none()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Нет доступных фото в очереди (попробуйте позже)",
        )
    photo.tagging_claimed_by_id = wid
    photo.tagging_claimed_until = now + TAGGING_CLAIM_TTL
    db.commit()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo.id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one()
    return _photo_out(photo, viewer_user_id=wid)


@router.post("/tagging-queue/{photo_id}/claim", response_model=AdminPhotoOut)
def claim_tagging_photo(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    """Забронировать конкретное фото из списка (сотрудник)."""
    if principal.role != "worker" or principal.user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Бронирование доступно только сотрудникам",
        )
    _expire_stale_tagging_claims(db)
    db.flush()
    now = datetime.now(timezone.utc)
    wid = principal.user.id

    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one_or_none()
    if not photo or photo.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.tagging_review_done:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разметка этого фото уже завершена",
        )
    if not photo.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Фото неактивно — не из очереди разметки",
        )

    active_claim = (
        photo.tagging_claimed_until is not None
        and photo.tagging_claimed_until > now
        and photo.tagging_claimed_by_id is not None
        and photo.tagging_claimed_by_id != wid
    )
    if active_claim:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Фото занято другим сотрудником",
        )

    photo.tagging_claimed_by_id = wid
    photo.tagging_claimed_until = now + TAGGING_CLAIM_TTL
    db.commit()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one()
    return _photo_out(photo, viewer_user_id=wid)


@router.post("/tagging-queue/{photo_id}/release", status_code=status.HTTP_204_NO_CONTENT)
def release_tagging_photo(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> None:
    """Снять свою бронь без сохранения тегов."""
    if principal.role != "worker" or principal.user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для сотрудников")
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.tagging_claimed_by_id != principal.user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша бронь")
    photo.tagging_claimed_by_id = None
    photo.tagging_claimed_until = None
    db.commit()


@router.post("/photos/bulk-delete", response_model=AdminPhotosBulkDeleteResponse)
def bulk_delete_photos(
    body: AdminPhotosBulkDeleteBody,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotosBulkDeleteResponse:
    results: list[AdminPhotoBulkDeleteItem] = []
    for pid in body.photo_ids:
        photo = db.get(Photo, pid)
        if not photo:
            results.append(AdminPhotoBulkDeleteItem(id=pid, ok=False, detail="not_found"))
            continue
        storage_err = delete_photo_file_from_object_storage(settings, photo.url)
        if storage_err:
            log.warning("bulk_delete photo_id=%s storage failed: %s", pid, storage_err)
            results.append(
                AdminPhotoBulkDeleteItem(
                    id=pid,
                    ok=False,
                    detail=f"object_storage: {storage_err}",
                ),
            )
            continue
        try:
            db.delete(photo)
            db.commit()
            results.append(AdminPhotoBulkDeleteItem(id=pid, ok=True, detail=None))
        except Exception as e:
            db.rollback()
            log.exception("bulk_delete photo_id=%s db failed", pid)
            results.append(AdminPhotoBulkDeleteItem(id=pid, ok=False, detail=str(e)))
    return AdminPhotosBulkDeleteResponse(results=results)


@router.put("/photos/{photo_id}/tags", response_model=AdminPhotoOut)
def put_photo_tags(
    photo_id: uuid.UUID,
    body: AdminPhotoTagsPutBody,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    _expire_stale_tagging_claims(db)
    db.flush()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads())
        .with_for_update(),
    ).scalar_one_or_none()
    if not photo or photo.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    if body.expected_tags_version is not None and photo.tags_version != body.expected_tags_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Фото уже изменено (теги или разметка). Обновите данные и попробуйте сохранить снова.",
        )

    tag_ids = [a.tag_id for a in body.tags]
    if len(tag_ids) != len(set(tag_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate tag_id in list",
        )
    if tag_ids:
        found = db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all()
        if len(found) != len(set(tag_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown tag_id in list",
            )

    verrors = validate_catalog_tag_selection(db, tag_ids)
    if verrors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=" ".join(verrors),
        )

    photo.tagging_uncertain = False
    photo.worker_signal_love = body.worker_signal_love
    photo.worker_signal_hit = body.worker_signal_hit
    photo.worker_signal_hard = body.worker_signal_hard
    photo.tagging_review_done = True

    if body.apply_brand:
        if body.brand_id is not None:
            br = db.get(Brand, body.brand_id)
            if not br:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="brand_id: бренд не найден",
                )
            photo.brand_id = body.brand_id
            photo.brand = br.name
        else:
            photo.brand_id = None
            photo.brand = None

    _body_patch = body.model_dump(exclude_unset=True)
    if "moy_sklad_id" in _body_patch:
        raw = _body_patch.get("moy_sklad_id")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            photo.moy_sklad_id = None
        else:
            s = raw.strip() if isinstance(raw, str) else str(raw)
            photo.moy_sklad_id = s[:128] if s else None

    for pt in list(photo.photo_tags):
        db.delete(pt)
    db.flush()
    for assign in body.tags:
        db.add(
            PhotoTag(photo_id=photo.id, tag_id=assign.tag_id, weight=assign.weight),
        )
    if principal.role == "worker" and principal.user:
        if photo.tagging_claimed_by_id == principal.user.id:
            photo.tagging_claimed_by_id = None
            photo.tagging_claimed_until = None
    photo.tags_version = photo.tags_version + 1
    db.commit()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one()
    return _photo_out(photo, viewer_user_id=_viewer_id(principal))


@router.get("/tag/catalog", response_model=AdminTagCatalogResponse)
def get_tag_catalog(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagCatalogResponse:
    return build_tag_catalog(db)


@router.post("/tag-groups/{group_id}/tags", response_model=AdminCatalogTagOut)
def create_tag_in_group(
    group_id: uuid.UUID,
    body: AdminWorkerTagCreateBody,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminCatalogTagOut:
    """Добавить тег в группу (виден всем сотрудникам)."""
    g = db.get(TagGroup, group_id)
    if not g or g.slug == "legacy":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    name = body.name.strip()
    exists = db.scalar(select(Tag.id).where(Tag.group_id == g.id, Tag.name == name))
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такой тег уже есть в группе",
        )
    mx = db.scalar(select(func.coalesce(func.max(Tag.sort_order), -1)).where(Tag.group_id == g.id))
    sort_order = int(mx) + 1 if mx is not None else 0
    uid = principal.user.id if principal.user else None
    t = Tag(
        name=name,
        type=g.slug,
        group_id=g.id,
        subgroup_key=None,
        sort_order=sort_order,
        recommendation_weight=55,
        created_by_user_id=uid,
    )
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось сохранить тег",
        ) from None
    db.refresh(t)
    return AdminCatalogTagOut(
        id=t.id,
        name=t.name,
        subgroup_key=t.subgroup_key,
        sort_order=t.sort_order,
        recommendation_weight=t.recommendation_weight,
    )


@router.get("/tags", response_model=AdminTagListResponse)
def list_tags(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagListResponse:
    rows = db.scalars(select(Tag).options(selectinload(Tag.group)).order_by(Tag.type, Tag.name)).all()
    items = []
    for t in rows:
        gsl = t.group.slug if t.group else None
        items.append(
            AdminTagOut(
                id=t.id,
                name=t.name,
                type=t.type,
                group_id=t.group_id,
                group_slug=gsl,
            ),
        )
    return AdminTagListResponse(items=items)


@router.post("/tags", response_model=AdminTagOut)
def create_tag(
    body: AdminTagCreateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagOut:
    name = body.name.strip()
    g: TagGroup | None = None
    if body.group_id:
        g = db.get(TagGroup, body.group_id)
    if g is None:
        g = db.scalar(select(TagGroup).where(TagGroup.slug == body.type.strip()))
    if g is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неизвестная группа: задайте group_id или type = slug группы (например product_type)",
        )
    mx = db.scalar(select(func.coalesce(func.max(Tag.sort_order), -1)).where(Tag.group_id == g.id))
    sort_order = int(mx) + 1 if mx is not None else 0
    t = Tag(
        name=name,
        type=g.slug,
        group_id=g.id,
        subgroup_key=None,
        sort_order=sort_order,
        recommendation_weight=55,
        created_by_user_id=None,
    )
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Тег с таким именем уже есть в этой группе",
        ) from None
    db.refresh(t)
    return AdminTagOut(
        id=t.id,
        name=t.name,
        type=t.type,
        group_id=t.group_id,
        group_slug=g.slug,
    )


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> None:
    t = db.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    db.delete(t)
    db.commit()


@router.patch("/tags/{tag_id}", response_model=AdminTagOut)
def update_tag(
    tag_id: uuid.UUID,
    body: AdminTagUpdateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagOut:
    t = db.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    new_name = body.name.strip()
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Название тега не может быть пустым",
        )
    clash = db.scalar(
        select(Tag.id).where(
            Tag.group_id == t.group_id,
            Tag.name == new_name,
            Tag.id != t.id,
        ),
    )
    if clash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Тег с таким именем уже есть в этой группе",
        )
    t.name = new_name
    db.commit()
    db.refresh(t)
    gsl = t.group.slug if t.group else None
    return AdminTagOut(
        id=t.id,
        name=t.name,
        type=t.type,
        group_id=t.group_id,
        group_slug=gsl,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> AdminUserListResponse:
    _ = _su
    total = db.scalar(select(func.count()).select_from(User)) or 0
    rows = db.scalars(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit),
    ).all()
    return AdminUserListResponse(
        items=[
            AdminUserOut(
                id=u.id,
                phone=u.phone,
                display_name=u.display_name,
                role=u.role,
                created_at=u.created_at,
                last_login_at=u.last_login_at,
            )
            for u in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/users", response_model=AdminUserOut)
def create_user(
    body: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminUserOut:
    _ = _su
    phone = body.phone.strip()
    existing = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already registered",
        )
    dn = None
    if body.display_name is not None:
        s = body.display_name.strip()
        dn = s if s else None
    u = User(
        phone=phone,
        display_name=dn,
        pin_hash=hash_pin(body.pin.strip()),
        role=body.role,
    )
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already registered",
        )
    db.refresh(u)
    return AdminUserOut(
        id=u.id,
        phone=u.phone,
        display_name=u.display_name,
        role=u.role,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )


@router.get("/users/{user_id}/detail", response_model=AdminUserDetailOut)
def get_user_detail(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminUserDetailOut:
    _ = _su
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    uid = user_id
    interactions_total = (
        db.scalar(
            select(func.count()).select_from(Interaction).where(Interaction.user_id == uid),
        )
        or 0
    )
    likes = (
        db.scalar(
            select(func.count()).select_from(Interaction).where(
                Interaction.user_id == uid,
                Interaction.action == "like",
            ),
        )
        or 0
    )
    dislikes = (
        db.scalar(
            select(func.count()).select_from(Interaction).where(
                Interaction.user_id == uid,
                Interaction.action == "dislike",
            ),
        )
        or 0
    )

    interactions_male = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(Interaction.user_id == uid, Photo.gender == "male"),
        )
        or 0
    )
    interactions_female = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(Interaction.user_id == uid, Photo.gender == "female"),
        )
        or 0
    )

    likes_male = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(
                Interaction.user_id == uid,
                Interaction.action == "like",
                Photo.gender == "male",
            ),
        )
        or 0
    )
    likes_female = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(
                Interaction.user_id == uid,
                Interaction.action == "like",
                Photo.gender == "female",
            ),
        )
        or 0
    )

    avg_raw = db.scalar(
        select(func.avg(Interaction.view_time_ms)).where(
            Interaction.user_id == uid,
            Interaction.view_time_ms.isnot(None),
        ),
    )
    avg_view_time_ms = float(avg_raw) if avg_raw is not None else None

    tw_rows = db.execute(
        select(Tag.id, Tag.name, Tag.type, UserTagWeight.weight)
        .join(UserTagWeight, UserTagWeight.tag_id == Tag.id)
        .where(
            UserTagWeight.user_id == uid,
            UserTagWeight.session_id.is_(None),
        ),
    ).all()
    tw_sorted = sorted(tw_rows, key=lambda r: -abs(float(r[3])))

    tag_weights = [
        AdminUserTagWeightStat(
            tag_id=row[0],
            tag_name=row[1],
            tag_type=row[2],
            weight=float(row[3]),
        )
        for row in tw_sorted
    ]

    Tlo = aliased(Tag)
    Thi = aliased(Tag)
    tp_rows = db.execute(
        select(
            UserTagPairWeight.tag_id_lo,
            UserTagPairWeight.tag_id_hi,
            Tlo.name,
            Thi.name,
            UserTagPairWeight.weight,
        )
        .join(Tlo, Tlo.id == UserTagPairWeight.tag_id_lo)
        .join(Thi, Thi.id == UserTagPairWeight.tag_id_hi)
        .where(
            UserTagPairWeight.user_id == uid,
            UserTagPairWeight.session_id.is_(None),
        ),
    ).all()
    tp_sorted = sorted(tp_rows, key=lambda r: -abs(float(r[4])))

    tag_pair_weights = [
        AdminUserTagPairWeightStat(
            tag_a_id=row[0],
            tag_b_id=row[1],
            tag_a_name=row[2],
            tag_b_name=row[3],
            weight=float(row[4]),
        )
        for row in tp_sorted
    ]

    user_out = AdminUserOut(
        id=u.id,
        phone=u.phone,
        display_name=u.display_name,
        role=u.role,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )
    return AdminUserDetailOut(
        user=user_out,
        interactions_total=interactions_total,
        likes=likes,
        dislikes=dislikes,
        interactions_male=interactions_male,
        interactions_female=interactions_female,
        likes_male=likes_male,
        likes_female=likes_female,
        avg_view_time_ms=avg_view_time_ms,
        tag_weights=tag_weights,
        tag_pair_weights=tag_pair_weights,
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminUserOut:
    _ = _su
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.phone is not None:
        new_phone = body.phone.strip()
        if new_phone != u.phone:
            clash = db.execute(select(User).where(User.phone == new_phone)).scalar_one_or_none()
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone already in use",
                )
            u.phone = new_phone

    if (
        body.role == UserRole.worker.value
        and u.role != UserRole.worker.value
        and body.pin is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="При назначении роли сотрудника задайте новый PIN (6 цифр)",
        )

    role_for_pin = body.role if body.role is not None else u.role
    if body.pin is not None:
        _pin_validation_http(role_for_pin, body.pin)
        u.pin_hash = hash_pin(body.pin.strip())

    if body.role is not None:
        u.role = body.role

    if body.display_name is not None:
        s = body.display_name.strip()
        u.display_name = s if s else None

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already in use",
        )
    db.refresh(u)
    return AdminUserOut(
        id=u.id,
        phone=u.phone,
        display_name=u.display_name,
        role=u.role,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> Response:
    """Удаление через SQL DELETE: ORM session.delete(user) иногда даёт 500 при каскадах/expire."""
    _ = _su
    try:
        result = db.execute(delete(User).where(User.id == user_id))
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        log.warning("delete_user integrity_error user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить пользователя: в БД остались связанные записи.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        log.exception("delete_user failed user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка базы при удалении пользователя.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/brands", response_model=AdminBrandListResponse)
def list_brands(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminBrandListResponse:
    _ = _principal
    rows = db.scalars(select(Brand).order_by(Brand.name.asc())).all()
    return AdminBrandListResponse(
        items=[
            AdminBrandOut(id=b.id, name=b.name, created_at=b.created_at) for b in rows
        ],
    )


@router.post("/brands", response_model=AdminBrandOut)
def create_brand(
    body: AdminBrandCreateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminBrandOut:
    _ = _principal
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите название бренда",
        )
    b = Brand(name=name)
    db.add(b)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Бренд с таким названием уже есть",
        ) from None
    db.refresh(b)
    return AdminBrandOut(id=b.id, name=b.name, created_at=b.created_at)


@router.get("/fitting-requests", response_model=AdminFittingRequestListResponse)
def list_fitting_requests(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> AdminFittingRequestListResponse:
    _ = _su
    total = db.scalar(select(func.count()).select_from(FittingRequest)) or 0
    rows = db.scalars(
        select(FittingRequest)
        .order_by(FittingRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .options(selectinload(FittingRequest.liked_photos)),
    ).all()
    return AdminFittingRequestListResponse(
        items=[
            AdminFittingRequestOut(
                id=row.id,
                user_id=row.user_id,
                display_name=row.display_name,
                phone=row.phone,
                likes=row.likes,
                total=row.total,
                match_rate=float(row.match_rate or 0),
                note=row.note,
                status=row.status,
                created_at=row.created_at,
                liked_photos=[x.photo_url for x in row.liked_photos],
            )
            for row in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


router.include_router(_ximilar_experimental_router)
