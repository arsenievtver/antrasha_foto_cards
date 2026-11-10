"""Админка (суперпользователь и сотрудник): загрузка сырья → очередь → Fashn → Object Storage."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import DOTENV_CANDIDATE_PATHS, DOTENV_LOADED_PATHS, settings
from app.database import SessionLocal, get_db
from app.deps import AdminPrincipal, get_admin_principal
from app.models import AiIngestJob, Brand, Photo
from app.schemas.ai_ingest import (
    AiIngestDiagnosticsOut,
    AiIngestEnqueueIn,
    AiIngestEnqueueOut,
    AiIngestJobListResponse,
    AiIngestJobOut,
    AiIngestLimitsOut,
    AiIngestPublishOut,
    AiIngestQueueStatsOut,
    AiIngestReleaseDraftOut,
    AiIngestUploadResponse,
)
from app.externals.http.fashn import VALID_CONTENT_MODES, normalize_content_mode
from app.services.ai_ingest_worker import count_pending_jobs, is_processing_stale
from app.services.brand_match import apply_supplier_link, match_supplier
from app.services.image_prepare import image_bytes_to_png
from app.services.moysklad_image import upload_catalog_png
from app.services.yc_storage import public_object_url, read_object_bytes
from app.services.feed_release_batch import (
    count_failed_fashn_for_draft,
    count_moysklad_pending_for_draft,
    count_pending_fashn_for_draft,
    draft_batch_summary,
    get_or_create_draft_batch,
    publish_draft_batch,
)

log = logging.getLogger("app.api.admin_ai_ingest")

router = APIRouter(prefix="/admin/ai-ingest", tags=["admin-ai-ingest"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _limits() -> AiIngestLimitsOut:
    key = settings.fashn_api_key
    tail: str | None = None
    if key and str(key).strip():
        s = str(key).strip()
        tail = s[-4:] if len(s) >= 4 else "****"
    aid = settings.yc_s3_access_key_id
    yc_tail: str | None = None
    if aid and str(aid).strip():
        a = str(aid).strip()
        yc_tail = a[-4:] if len(a) >= 4 else "****"
    pipeline = settings.fashn_configured and settings.yc_s3_configured
    return AiIngestLimitsOut(
        max_files_per_upload=settings.ai_ingest_max_files_per_upload,
        max_file_bytes=settings.ai_ingest_max_file_bytes,
        max_pending_jobs=settings.ai_ingest_max_pending_jobs,
        worker_concurrency=settings.ai_ingest_worker_concurrency,
        fashn_configured=settings.fashn_configured,
        yc_s3_configured=settings.yc_s3_configured,
        pipeline_ready=pipeline,
        fashn_calls_from="server_only",
        env_dotenv_candidates=[str(p) for p in DOTENV_CANDIDATE_PATHS],
        env_dotenv_loaded=[str(p) for p in DOTENV_LOADED_PATHS],
        fashn_key_last4=tail,
        yc_access_key_id_last4=yc_tail,
    )


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "").strip() or "photo"
    if ".." in base or base.startswith("/"):
        return "photo"
    return base[:240]


def _job_out(j: AiIngestJob, brands: list | None = None) -> AiIngestJobOut:
    url = None
    if j.result_bucket and j.result_key:
        url = public_object_url(j.result_bucket, j.result_key)
    brand_name = None
    if j.brand_id and j.brand is not None:
        brand_name = j.brand.name
    match = None
    if brands is not None and (j.status == "inbox" or j.moysklad_supplier_id or j.supplier_name):
        match = match_supplier(brands, j.moysklad_supplier_id, j.supplier_name)
    return AiIngestJobOut(
        id=j.id,
        gender=j.gender,
        source_mode=j.source_mode or "single",
        brand_id=j.brand_id,
        brand_name=brand_name,
        show_badge=bool(j.show_badge),
        original_filename=j.original_filename,
        status=j.status,
        stage=j.stage if j.status == "processing" else None,
        stage_at=j.stage_at if j.status == "processing" else None,
        fashn_ordered=bool(j.fashn_job_id) and j.status != "completed",
        stale=j.status == "processing" and is_processing_stale(j),
        error_message=j.error_message,
        result_url=url,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
        product_name=j.product_name,
        article=j.article,
        barcode=j.barcode,
        supplier_name=j.supplier_name,
        moysklad_product_id=j.moysklad_product_id,
        moysklad_upload_status=j.moysklad_upload_status,
        moysklad_upload_error=j.moysklad_upload_error,
        brand_match=match.confidence if match else None,
        brand_warning=match.warning if match else None,
        suggested_brand_id=match.brand_id if match else None,
        suggested_brand_name=match.brand_name if match else None,
    )


def _count_status(db: Session, st: str) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(AiIngestJob).where(AiIngestJob.status == st),
        )
        or 0,
    )


@router.get("/limits", response_model=AiIngestLimitsOut)
def get_limits(
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestLimitsOut:
    _ = _p
    return _limits()


@router.get("/diagnostics", response_model=AiIngestDiagnosticsOut)
def ingest_network_diagnostics(
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestDiagnosticsOut:
    """TCP до api.fashn.ai:443 с машины, где крутится бэкенд (Docker/VPS — не ваш ноутбук)."""
    _ = _p
    import socket

    ok = False
    err: str | None = None
    try:
        socket.create_connection(("api.fashn.ai", 443), timeout=8)
        ok = True
    except OSError as e:
        err = str(e)
    return AiIngestDiagnosticsOut(api_fashn_tcp_443_ok=ok, api_fashn_tcp_error=err)


@router.get("/stats", response_model=AiIngestQueueStatsOut)
def queue_stats(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestQueueStatsOut:
    _ = _p
    return AiIngestQueueStatsOut(
        pending=_count_status(db, "pending"),
        processing=_count_status(db, "processing"),
        failed=_count_status(db, "failed"),
        inbox=_count_status(db, "inbox"),
    )


@router.get("/release-draft", response_model=AiIngestReleaseDraftOut)
def get_release_draft(
    gender: str = Query(..., min_length=1, max_length=10),
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestReleaseDraftOut:
    _ = _p
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise HTTPException(status_code=400, detail="gender: male или female")
    summary = draft_batch_summary(db, gender=g)
    batch_id = summary.get("batch_id")
    fashn_pending = 0
    fashn_failed = 0
    moysklad_pending = 0
    if batch_id:
        fashn_pending = count_pending_fashn_for_draft(db, batch_id)
        fashn_failed = count_failed_fashn_for_draft(db, batch_id)
        moysklad_pending = count_moysklad_pending_for_draft(db, batch_id)
    photo_count = int(summary["photo_count"])
    embedded_count = int(summary["embedded_count"])
    embed_pending = max(0, photo_count - embedded_count)
    can_publish = (
        photo_count > 0
        and fashn_pending == 0
        and fashn_failed == 0
        and embed_pending == 0
        and moysklad_pending == 0
    )
    return AiIngestReleaseDraftOut(
        gender=g,
        batch_id=batch_id,
        photo_count=photo_count,
        embedded_count=embedded_count,
        embed_pending=embed_pending,
        embed_error_count=int(summary["embed_error_count"]),
        last_embed_error=summary.get("last_embed_error"),
        fashn_pending=fashn_pending,
        fashn_failed=fashn_failed,
        moysklad_pending=moysklad_pending,
        can_publish=can_publish,
    )


@router.post("/release/publish", response_model=AiIngestPublishOut)
def publish_release_draft(
    gender: str = Query(..., min_length=1, max_length=10),
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestPublishOut:
    _ = _p
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise HTTPException(status_code=400, detail="gender: male или female")
    draft = draft_batch_summary(db, gender=g)
    batch_id = draft.get("batch_id")
    if batch_id and count_pending_fashn_for_draft(db, batch_id) > 0:
        raise HTTPException(
            status_code=409,
            detail="Fashn ещё обрабатывает файлы — дождитесь окончания очереди",
        )
    if batch_id and count_failed_fashn_for_draft(db, batch_id) > 0:
        raise HTTPException(
            status_code=409,
            detail="В пакете есть ошибки Fashn — повторите или удалите их в таблице ниже",
        )
    if batch_id and count_moysklad_pending_for_draft(db, batch_id) > 0:
        raise HTTPException(
            status_code=409,
            detail="В пакете есть фото, которые не ушли в МойСклад — повторите загрузку в таблице",
        )
    try:
        result = publish_draft_batch(db, gender=g)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return AiIngestPublishOut(
        ok=bool(result.get("ok")),
        published=bool(result.get("published")),
        batch_id=result.get("batch_id"),
        photo_count=int(result.get("photo_count") or 0),
        message=str(result.get("message") or ""),
        failed=list(result.get("failed") or []),
    )


@router.get("/jobs", response_model=AiIngestJobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    queue: str | None = Query(None, description="inbox | fashn"),
) -> AiIngestJobListResponse:
    _ = _p
    cond = None
    if queue == "inbox":
        cond = AiIngestJob.status == "inbox"
    elif queue == "fashn":
        cond = AiIngestJob.status != "inbox"
    elif queue:
        raise HTTPException(status_code=400, detail="queue: inbox или fashn")
    total_stmt = select(func.count()).select_from(AiIngestJob)
    rows_stmt = select(AiIngestJob)
    if cond is not None:
        total_stmt = total_stmt.where(cond)
        rows_stmt = rows_stmt.where(cond)
    order = AiIngestJob.created_at.asc() if queue == "inbox" else AiIngestJob.created_at.desc()
    total = db.scalar(total_stmt) or 0
    rows = db.scalars(rows_stmt.order_by(order).offset(skip).limit(limit)).all()
    brands = list(db.scalars(select(Brand).order_by(Brand.name.asc())).all())
    return AiIngestJobListResponse(
        items=[_job_out(j, brands) for j in rows],
        total=int(total),
        skip=skip,
        limit=limit,
    )


async def _save_upload_limited(upload: UploadFile, dest: Path, max_bytes: int) -> None:
    total = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Файл больше {max_bytes} байт",
                    )
                f.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise


def _form_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


@router.post("/upload", response_model=AiIngestUploadResponse)
async def upload_batch(
    _p: AdminPrincipal = Depends(get_admin_principal),
    gender: str = Form(..., description="male | female"),
    source_mode: str = Form(
        "single",
        description="single (одна вещь-герой) | look (готовый образ) — правило для промпта Fashn",
    ),
    brand_id: uuid.UUID = Form(..., description="ID бренда, см. GET /admin/brands"),
    show_badge: str = Form(
        "false",
        description="true/false — поставить центральный бейдж (Sale) на готовые фото",
    ),
    files: list[UploadFile] = File(...),
) -> AiIngestUploadResponse:
    """
    Не используем Depends(get_db) здесь: Bearer уже проверен в get_admin_principal,
    второй get_db отнимает второе соединение на всё время приёма multipart (типичный «зависший» upload).
    БД трогаем короткими SessionLocal().
    """
    _ = _p
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise HTTPException(status_code=400, detail="gender: укажите male или female")
    try:
        mode = normalize_content_mode(source_mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"source_mode: укажите {' или '.join(sorted(VALID_CONTENT_MODES))}",
        ) from None
    badge_on = _form_bool(show_badge)

    db_brand = SessionLocal()
    try:
        b = db_brand.get(Brand, brand_id)
        if b is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="brand_id: бренд не найден. Создайте бренд в GET/POST /admin/brands",
            )
    finally:
        db_brand.close()

    if not settings.fashn_configured:
        raise HTTPException(
            status_code=503,
            detail="FASHN_API_KEY не задан в конфигурации сервера",
        )
    if not settings.yc_s3_configured:
        raise HTTPException(
            status_code=503,
            detail="Yandex Object Storage не настроен",
        )

    if not files:
        raise HTTPException(status_code=400, detail="Нужен хотя бы один файл")

    lim = _limits()
    if len(files) > lim.max_files_per_upload:
        raise HTTPException(
            status_code=400,
            detail=f"Не больше {lim.max_files_per_upload} файлов за один запрос",
        )

    db_check = SessionLocal()
    try:
        pending = count_pending_jobs(db_check)
        if pending + len(files) > lim.max_pending_jobs:
            raise HTTPException(
                status_code=409,
                detail=f"Очередь переполнена: pending={pending}, лимит {lim.max_pending_jobs}. "
                "Дождитесь обработки или увеличьте AI_INGEST_MAX_PENDING_JOBS.",
            )
    finally:
        db_check.close()

    tmp_root = settings.ai_ingest_temp_path
    tmp_root.mkdir(parents=True, exist_ok=True)

    planned: list[tuple[uuid.UUID, Path, str]] = []
    written_paths: list[Path] = []
    log.info(
        "ai_ingest upload: принимаем %s файл(ов) gender=%s source_mode=%s brand_id=%s show_badge=%s во временный каталог %s",
        len(files),
        g,
        mode,
        brand_id,
        badge_on,
        tmp_root,
    )
    try:
        for uf in files:
            raw_name = _safe_filename(uf.filename or "")
            ext = Path(raw_name).suffix.lower()
            if ext not in _ALLOWED_EXT:
                raise HTTPException(
                    status_code=400,
                    detail=f"Недопустимое расширение {ext!r}: допустимы {sorted(_ALLOWED_EXT)}",
                )
            jid = uuid.uuid4()
            disk_name = f"{jid}{ext}"
            dest = tmp_root / disk_name
            await _save_upload_limited(uf, dest, lim.max_file_bytes)
            written_paths.append(dest)
            planned.append((jid, dest.resolve(), raw_name))
    except HTTPException:
        for p in written_paths:
            p.unlink(missing_ok=True)
        raise
    except Exception:
        for p in written_paths:
            p.unlink(missing_ok=True)
        raise

    created_rows: list[AiIngestJob] = []
    db_ins = SessionLocal()
    try:
        draft = get_or_create_draft_batch(db_ins, gender=g)
        for jid, dest_resolved, raw_name in planned:
            job = AiIngestJob(
                id=jid,
                gender=g,
                source_mode=mode,
                brand_id=brand_id,
                show_badge=badge_on,
                original_filename=raw_name,
                temp_path=str(dest_resolved),
                status="pending",
                release_batch_id=draft.id,
            )
            db_ins.add(job)
            created_rows.append(job)
        db_ins.commit()
        for j in created_rows:
            db_ins.refresh(j)
        log.info("ai_ingest upload: в очередь добавлено задач=%s", len(created_rows))
    except Exception:
        db_ins.rollback()
        for p in written_paths:
            p.unlink(missing_ok=True)
        raise
    finally:
        db_ins.close()

    return AiIngestUploadResponse(
        created=[_job_out(j) for j in created_rows],
        limits=lim,
    )


@router.post("/jobs/{job_id}/retry", response_model=AiIngestJobOut)
def retry_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestJobOut:
    _ = _p
    j = db.get(AiIngestJob, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if j.status != "failed":
        raise HTTPException(status_code=400, detail="Повтор только для failed")
    p = Path(j.temp_path)
    if not j.fashn_job_id and not p.is_file():
        raise HTTPException(
            status_code=400,
            detail="Исходный файл отсутствует на диске — загрузите снова",
        )
    j.status = "pending"
    j.error_message = None
    j.stage = None
    j.stage_at = None
    j.started_at = None
    j.finished_at = None
    j.result_bucket = None
    j.result_key = None
    db.commit()
    db.refresh(j)
    return _job_out(j)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> None:
    _ = _p
    j = db.get(AiIngestJob, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if j.status == "processing" and not is_processing_stale(j):
        raise HTTPException(status_code=409, detail="Задача выполняется — подождите")
    p = Path(j.temp_path)
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass
    db.delete(j)
    db.commit()


def _source_file(job: AiIngestJob) -> Path:
    root = settings.ai_ingest_temp_path.resolve()
    path = Path(job.temp_path).resolve()
    if not path.is_file() or path.parent != root:
        raise HTTPException(status_code=404, detail="Исходник не найден")
    return path


_SOURCE_MEDIA = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


@router.get("/jobs/{job_id}/source")
def job_source(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> FileResponse:
    _ = _p
    job = db.get(AiIngestJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    path = _source_file(job)
    media = _SOURCE_MEDIA.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, filename=job.original_filename or path.name)


@router.post("/inbox/enqueue", response_model=AiIngestEnqueueOut)
def enqueue_inbox(
    body: AiIngestEnqueueIn,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestEnqueueOut:
    """Кадры с телефона → обычная очередь Fashn. Id поставщика пишется на выбранный бренд."""
    _ = _p
    if not body.items or len(body.items) > 100:
        raise HTTPException(status_code=400, detail="Выберите от 1 до 100 кадров")
    if len({item.job_id for item in body.items}) != len(body.items):
        raise HTTPException(status_code=400, detail="В списке повторяется один и тот же кадр")
    try:
        mode = normalize_content_mode(body.source_mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"source_mode: укажите {' или '.join(sorted(VALID_CONTENT_MODES))}",
        ) from None
    if not settings.fashn_configured or not settings.yc_s3_configured:
        raise HTTPException(status_code=503, detail="Fashn или хранилище не настроены")

    lim = _limits()
    pending = count_pending_jobs(db)
    if pending + len(body.items) > lim.max_pending_jobs:
        raise HTTPException(
            status_code=409,
            detail=f"Очередь Fashn переполнена: pending={pending}, лимит {lim.max_pending_jobs}",
        )

    brands = list(db.scalars(select(Brand).order_by(Brand.name.asc())).all())
    by_id = {b.id: b for b in brands}
    drafts: dict[str, uuid.UUID] = {}
    updated: list[AiIngestJob] = []
    for item in body.items:
        job = db.get(AiIngestJob, item.job_id)
        if job is None or job.status != "inbox":
            raise HTTPException(status_code=400, detail="В выборке есть кадр не из очереди телефона")
        _source_file(job)
        brand_id = item.brand_id or job.brand_id
        brand = by_id.get(brand_id) if brand_id else None
        if brand is None:
            label = job.article or job.product_name or "кадр"
            raise HTTPException(status_code=400, detail=f"Выберите бренд: {label}")
        link_error = apply_supplier_link(brand, job.moysklad_supplier_id, brands)
        if link_error:
            raise HTTPException(status_code=409, detail=link_error)
        if job.gender not in drafts:
            drafts[job.gender] = get_or_create_draft_batch(db, gender=job.gender).id
        job.brand_id = brand.id
        job.source_mode = mode
        job.show_badge = bool(body.show_badge)
        job.status = "pending"
        job.release_batch_id = drafts[job.gender]
        job.error_message = None
        updated.append(job)
    db.commit()
    for job in updated:
        db.refresh(job)
    return AiIngestEnqueueOut(items=[_job_out(job, brands) for job in updated])


@router.post("/jobs/{job_id}/moysklad", response_model=AiIngestJobOut)
async def retry_moysklad_image(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(get_admin_principal),
) -> AiIngestJobOut:
    _ = _p
    job = db.get(AiIngestJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if not job.moysklad_product_id:
        raise HTTPException(status_code=400, detail="У кадра нет товара МойСклад")
    if job.moysklad_upload_status == "uploaded":
        brands = list(db.scalars(select(Brand)).all())
        return _job_out(job, brands)
    if job.status != "completed" or not job.result_bucket or not job.result_key or not job.photo_id:
        raise HTTPException(status_code=409, detail="Сначала дождитесь кадра Fashn")
    filename = f"collection-{job.id.hex[:12]}.png"
    try:
        png = image_bytes_to_png(read_object_bytes(job.result_bucket, job.result_key))
        await upload_catalog_png(job.moysklad_product_id, png, filename=filename)
    except Exception as e:
        job.moysklad_upload_status = "failed"
        job.moysklad_upload_error = f"{type(e).__name__}: {e}"[:2000]
        db.commit()
        raise HTTPException(status_code=502, detail=f"МойСклад: {job.moysklad_upload_error}") from e
    photo = db.get(Photo, job.photo_id)
    if photo is not None:
        photo.moy_sklad_id = job.moysklad_product_id[:128]
    job.moysklad_upload_status = "uploaded"
    job.moysklad_upload_error = None
    db.commit()
    db.refresh(job)
    brands = list(db.scalars(select(Brand)).all())
    return _job_out(job, brands)
