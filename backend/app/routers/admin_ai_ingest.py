"""Суперпользователь: загрузка сырья → очередь → Fashn → Object Storage."""

from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import DOTENV_CANDIDATE_PATHS, DOTENV_LOADED_PATHS, settings
from app.database import SessionLocal, get_db
from app.deps import require_superuser, AdminPrincipal
from app.models import AiIngestJob, Brand
from app.schemas.ai_ingest import (
    AiIngestDiagnosticsOut,
    AiIngestJobListResponse,
    AiIngestJobOut,
    AiIngestLimitsOut,
    AiIngestQueueStatsOut,
    AiIngestUploadResponse,
)
from app.services.ai_ingest_worker import count_pending_jobs
from app.services.yc_storage import public_object_url

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


def _job_out(j: AiIngestJob) -> AiIngestJobOut:
    url = None
    if j.result_bucket and j.result_key:
        url = public_object_url(j.result_bucket, j.result_key)
    brand_name = None
    if j.brand_id and j.brand is not None:
        brand_name = j.brand.name
    return AiIngestJobOut(
        id=j.id,
        gender=j.gender,
        brand_id=j.brand_id,
        brand_name=brand_name,
        original_filename=j.original_filename,
        status=j.status,
        error_message=j.error_message,
        result_url=url,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
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
    _su: AdminPrincipal = Depends(require_superuser),
) -> AiIngestLimitsOut:
    _ = _su
    return _limits()


@router.get("/diagnostics", response_model=AiIngestDiagnosticsOut)
def ingest_network_diagnostics(
    _su: AdminPrincipal = Depends(require_superuser),
) -> AiIngestDiagnosticsOut:
    """TCP до api.fashn.ai:443 с машины, где крутится бэкенд (Docker/VPS — не ваш ноутбук)."""
    _ = _su
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
    _su: AdminPrincipal = Depends(require_superuser),
) -> AiIngestQueueStatsOut:
    _ = _su
    return AiIngestQueueStatsOut(
        pending=_count_status(db, "pending"),
        processing=_count_status(db, "processing"),
        failed=_count_status(db, "failed"),
    )


@router.get("/jobs", response_model=AiIngestJobListResponse)
def list_jobs(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> AiIngestJobListResponse:
    _ = _su
    total = db.scalar(select(func.count()).select_from(AiIngestJob)) or 0
    rows = db.scalars(
        select(AiIngestJob)
        .order_by(AiIngestJob.created_at.desc())
        .offset(skip)
        .limit(limit),
    ).all()
    return AiIngestJobListResponse(
        items=[_job_out(j) for j in rows],
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


@router.post("/upload", response_model=AiIngestUploadResponse)
async def upload_batch(
    _su: AdminPrincipal = Depends(require_superuser),
    gender: str = Form(..., description="male | female"),
    brand_id: uuid.UUID = Form(..., description="ID бренда, см. GET /admin/brands"),
    files: list[UploadFile] = File(...),
) -> AiIngestUploadResponse:
    """
    Не используем Depends(get_db) здесь: у superuser уже есть сессия из get_admin_principal,
    второй get_db отнимает второе соединение на всё время приёма multipart (типичный «зависший» upload).
    БД трогаем короткими SessionLocal().
    """
    _ = _su
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise HTTPException(status_code=400, detail="gender: укажите male или female")

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
        "ai_ingest upload: принимаем %s файл(ов) gender=%s brand_id=%s во временный каталог %s",
        len(files),
        g,
        brand_id,
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
        for jid, dest_resolved, raw_name in planned:
            job = AiIngestJob(
                id=jid,
                gender=g,
                brand_id=brand_id,
                original_filename=raw_name,
                temp_path=str(dest_resolved),
                status="pending",
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
    _su: AdminPrincipal = Depends(require_superuser),
) -> AiIngestJobOut:
    _ = _su
    j = db.get(AiIngestJob, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if j.status != "failed":
        raise HTTPException(status_code=400, detail="Повтор только для failed")
    p = Path(j.temp_path)
    if not p.is_file():
        raise HTTPException(
            status_code=400,
            detail="Исходный файл отсутствует на диске — загрузите снова",
        )
    j.status = "pending"
    j.error_message = None
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
    _su: AdminPrincipal = Depends(require_superuser),
) -> None:
    _ = _su
    j = db.get(AiIngestJob, job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    if j.status == "processing":
        raise HTTPException(status_code=409, detail="Задача выполняется — подождите")
    p = Path(j.temp_path)
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass
    db.delete(j)
    db.commit()
