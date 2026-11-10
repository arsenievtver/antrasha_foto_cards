"""Очередь кадра аутлета. Телефон её только создаёт и опрашивает."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.deps import AdminPrincipal
from app.externals.http.fashn import (
    CONTENT_MODE_SINGLE,
    FRAME_OUTLET,
    STAGE_SUBMIT,
    FashnClient,
    FashnJobFailed,
    FashnJobGone,
)
from app.models.outlet_photo_job import OPEN_JOB_STATUSES, OutletPhotoJob
from app.services.image_prepare import jpeg_bytes_for_fashn_bytes, normalize_png_bytes
from app.services.yc_storage import delete_fashn_source, public_object_url, put_fashn_source_jpeg

log = logging.getLogger("app.outlet_photo")

JOB_DEADLINE_SEC = 15 * 60


class OutletJobCancelled(Exception):
    """Сотрудник отменил кадр до заказа в Fashn — платить не за что."""


def _job_status(job_id: uuid.UUID) -> str | None:
    db = SessionLocal()
    try:
        return db.scalar(select(OutletPhotoJob.status).where(OutletPhotoJob.id == job_id))
    finally:
        db.close()


def describe_fashn_error(e: BaseException) -> str:
    """Текст для экрана сотрудника, а не имя исключения."""
    if isinstance(e, FashnJobFailed):
        return "Fashn не смог сделать кадр. Попробуйте другой ракурс или фон."
    if isinstance(e, FashnJobGone):
        return "Fashn потерял заказ. Отправьте кадр ещё раз."
    if isinstance(e, (TimeoutError, asyncio.TimeoutError)):
        return "Fashn не ответил вовремя. Отправьте кадр ещё раз."
    return f"Ошибка связи с Fashn ({type(e).__name__}). Отправьте кадр ещё раз."


def _root() -> Path:
    root = settings.outlet_photo_temp_path
    root.mkdir(parents=True, exist_ok=True)
    return root


def _file(name: str) -> Path:
    """Имя файла из нашей папки, без путей снаружи."""
    if not name or "/" in name or "\\" in name or name.startswith("."):
        raise ValueError("bad outlet photo filename")
    root = _root().resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("bad outlet photo path")
    return path


def delete_job_files(job: OutletPhotoJob) -> None:
    for name in (job.source_name, job.result_name):
        if not name:
            continue
        try:
            _file(name).unlink(missing_ok=True)
        except (OSError, ValueError):
            log.warning("outlet job %s: не удалось удалить %s", job.id, name)


def result_file(job: OutletPhotoJob) -> Path:
    if not job.result_name:
        raise FileNotFoundError("result is not ready")
    path = _file(job.result_name)
    if not path.is_file():
        raise FileNotFoundError(job.result_name)
    return path


def _owner_filter(principal: AdminPrincipal):
    if principal.user is not None:
        return OutletPhotoJob.owner_user_id == principal.user.id
    return OutletPhotoJob.owner_is_superuser.is_(True)


def job_visible_to(job: OutletPhotoJob, principal: AdminPrincipal) -> bool:
    if principal.user is not None:
        return job.owner_user_id == principal.user.id
    return bool(job.owner_is_superuser) and job.owner_user_id is None


def dismiss_job(db: Session, job: OutletPhotoJob) -> OutletPhotoJob:
    if job.status == "uploaded":
        return job
    was_running = job.status == "running"
    job.status = "cancelled"
    job.finished_at = datetime.now(timezone.utc)
    job.error_message = None
    db.commit()
    db.refresh(job)
    if not was_running:
        delete_job_files(job)
    return job


def cancel_open_jobs(db: Session, principal: AdminPrincipal) -> None:
    rows = db.scalars(
        select(OutletPhotoJob).where(
            _owner_filter(principal),
            OutletPhotoJob.status.in_(OPEN_JOB_STATUSES),
        ),
    ).all()
    for row in rows:
        dismiss_job(db, row)


def create_job(
    db: Session,
    principal: AdminPrincipal,
    *,
    raw: bytes,
    gender: str,
    product_id: str,
    name: str,
    article: str | None,
    code: str | None,
    barcode: str | None,
    path_name: str | None,
    product_gender: str | None,
) -> OutletPhotoJob:
    cancel_open_jobs(db, principal)
    job_id = uuid.uuid4()
    source_name = f"{job_id}.jpg"
    path = _file(source_name)
    path.write_bytes(raw)
    job = OutletPhotoJob(
        id=job_id,
        status="pending",
        gender=gender,
        product_id=product_id,
        product_name=name or "Без названия",
        article=article,
        code=code,
        barcode=barcode,
        path_name=path_name,
        product_gender=product_gender,
        source_name=source_name,
        owner_user_id=principal.user.id if principal.user is not None else None,
        owner_is_superuser=principal.user is None,
    )
    db.add(job)
    try:
        db.commit()
    except Exception:
        path.unlink(missing_ok=True)
        db.rollback()
        raise
    db.refresh(job)
    log.info("outlet job %s queued product=%s", job.id, product_id)
    return job


def current_job(db: Session, principal: AdminPrincipal) -> OutletPhotoJob | None:
    row = db.scalars(
        select(OutletPhotoJob)
        .where(
            _owner_filter(principal),
            OutletPhotoJob.status.in_(OPEN_JOB_STATUSES),
        )
        .order_by(OutletPhotoJob.created_at.desc())
        .limit(1),
    ).first()
    if row is None:
        return None
    # Старая ошибка не должна встречать сотрудника на следующий день.
    if row.status == "failed":
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created < datetime.now(timezone.utc) - timedelta(hours=12):
            return None
    return row


def reset_running_jobs(db: Session) -> int:
    """
    Очередь живёт в процессе API. После рестарта running уже никто не ведёт.
    fashn_job_id остаётся — задача продолжит оплаченный заказ.
    """
    res = db.execute(
        update(OutletPhotoJob)
        .where(OutletPhotoJob.status == "running")
        .values(status="pending", started_at=None),
    )
    db.commit()
    n = res.rowcount or 0
    if n:
        log.warning("outlet photo: возвращено в очередь зависших running: %s", n)
    return n


def _fail(db: Session, job: OutletPhotoJob, message: str) -> None:
    job.status = "failed"
    job.error_message = (message or "Ошибка Fashn")[:2000]
    job.finished_at = datetime.now(timezone.utc)
    db.commit()
    delete_job_files(job)


def _save_fashn_job_id(job_id: uuid.UUID, remote_id: str | None) -> None:
    db = SessionLocal()
    try:
        db.execute(
            update(OutletPhotoJob).where(OutletPhotoJob.id == job_id).values(fashn_job_id=remote_id),
        )
        db.commit()
    finally:
        db.close()


def _render_png(job_id: uuid.UUID, raw: bytes, gender: str, remote_id: str | None) -> bytes:
    g = (gender or "").strip().lower()
    bucket = settings.yc_bucket_men if g == "male" else settings.yc_bucket_women
    uploaded: list[str] = []

    def on_stage(stage: str) -> None:
        if stage == STAGE_SUBMIT and _job_status(job_id) != "running":
            raise OutletJobCancelled()

    def source_url() -> str:
        jpeg, _size = jpeg_bytes_for_fashn_bytes(raw)
        key = put_fashn_source_jpeg(bucket, jpeg)
        uploaded.append(key)
        return public_object_url(bucket, key)

    client = FashnClient(
        api_key=str(settings.fashn_api_key).strip(),
        proxy=settings.fashn_proxy_url,
        connect_timeout=settings.fashn_http_connect_timeout,
        submit_timeout=settings.fashn_http_read_timeout_submit,
        poll_timeout=settings.fashn_http_read_timeout_poll,
        download_timeout=settings.fashn_http_read_timeout_download,
    )
    try:
        png = asyncio.run(
            asyncio.wait_for(
                client.run_product_to_model(
                    gender=gender,
                    product_image_url=source_url,
                    content_mode=CONTENT_MODE_SINGLE,
                    frame=FRAME_OUTLET,
                    remote_id=remote_id,
                    on_submitted=lambda rid: _save_fashn_job_id(job_id, rid),
                    on_stage=on_stage,
                ),
                timeout=JOB_DEADLINE_SEC,
            ),
        )
        return normalize_png_bytes(png)
    finally:
        for key in uploaded:
            try:
                delete_fashn_source(bucket, key)
            except Exception:
                log.warning("outlet source delete %s failed", key, exc_info=True)


def _acquire() -> uuid.UUID | None:
    db = SessionLocal()
    try:
        job = db.scalars(
            select(OutletPhotoJob)
            .where(OutletPhotoJob.status == "pending")
            .order_by(OutletPhotoJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True),
        ).first()
        if job is None:
            return None
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.error_message = None
        db.commit()
        return job.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(OutletPhotoJob, job_id)
        if not job or job.status != "running":
            return
        gender = job.gender
        source_name = job.source_name
        remote_id = job.fashn_job_id
    finally:
        db.close()

    try:
        raw = _file(source_name).read_bytes()
    except (OSError, ValueError) as e:
        db = SessionLocal()
        try:
            job = db.get(OutletPhotoJob, job_id)
            if job and job.status == "running":
                _fail(db, job, "Файл кадра не найден")
            log.warning("outlet job %s source missing: %s", job_id, e)
        finally:
            db.close()
        return

    t0 = time.monotonic()
    try:
        png = _render_png(job_id, raw, gender, remote_id)
    except OutletJobCancelled:
        log.info("outlet job %s отменён до заказа в Fashn", job_id)
        db = SessionLocal()
        try:
            job = db.get(OutletPhotoJob, job_id)
            if job:
                delete_job_files(job)
        finally:
            db.close()
        return
    except Exception as e:
        dt = time.monotonic() - t0
        log.warning(
            "outlet job %s Fashn за %.1fs: %s: %s",
            job_id,
            dt,
            type(e).__name__,
            e,
            exc_info=True,
        )
        db = SessionLocal()
        try:
            job = db.get(OutletPhotoJob, job_id)
            if job and isinstance(e, (FashnJobFailed, FashnJobGone)):
                job.fashn_job_id = None
            if job and job.status == "running":
                _fail(db, job, describe_fashn_error(e))
            elif job:
                delete_job_files(job)
        finally:
            db.close()
        return

    result_name = f"{job_id}.png"
    try:
        _file(result_name).write_bytes(png)
    except OSError as e:
        db = SessionLocal()
        try:
            job = db.get(OutletPhotoJob, job_id)
            if job and job.status == "running":
                _fail(db, job, f"Не удалось сохранить результат: {e}")
        finally:
            db.close()
        return

    db = SessionLocal()
    try:
        job = db.get(OutletPhotoJob, job_id)
        if not job or job.status != "running":
            try:
                _file(result_name).unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
            if job:
                delete_job_files(job)
            return
        job.result_name = result_name
        job.status = "ready"
        job.error_message = None
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        try:
            _file(source_name).unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
        log.info(
            "outlet job %s ready за %.1fs, png=%s байт",
            job_id,
            time.monotonic() - t0,
            len(png),
        )
    finally:
        db.close()


def try_process_one_outlet_photo_job() -> bool:
    if not settings.fashn_configured:
        return False
    job_id = _acquire()
    if job_id is None:
        return False
    _run(job_id)
    return True
