"""Фоновая обработка очереди try_on_jobs через FASHN VTON 1.5 (локальный инференс)."""

from __future__ import annotations

import base64
import io
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
from PIL import Image
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.database import SessionLocal
from app.models.try_on_job import (
    TRY_ON_STATUS_FAILED,
    TRY_ON_STATUS_PENDING,
    TRY_ON_STATUS_PROCESSING,
    TryOnJob,
)

log = logging.getLogger("app.try_on_worker")


def reset_stale_try_on_jobs(db: Session, *, older_than_minutes: int = 30) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    res = db.execute(
        update(TryOnJob)
        .where(
            TryOnJob.status == TRY_ON_STATUS_PROCESSING,
            TryOnJob.started_at.is_not(None),
            TryOnJob.started_at < cutoff,
        )
        .values(status=TRY_ON_STATUS_PENDING, started_at=None, error=None),
    )
    db.commit()
    n = res.rowcount or 0
    if n:
        log.warning("try_on_worker: сброшено зависших processing: %s", n)
    return n


def _fail_job(db: Session, job: TryOnJob, message: str) -> None:
    job.status = TRY_ON_STATUS_FAILED
    job.error = (message or "")[:4000]
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def _success_job(db: Session, job: TryOnJob, result_url: str) -> None:
    job.status = "done"
    job.result_url = result_url
    job.error = None
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def acquire_next_pending_job_id() -> uuid.UUID | None:
    db = SessionLocal()
    try:
        job = db.scalars(
            select(TryOnJob)
            .where(TryOnJob.status == TRY_ON_STATUS_PENDING)
            .order_by(TryOnJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True),
        ).first()
        if job is None:
            return None
        jid = job.id
        job.status = TRY_ON_STATUS_PROCESSING
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        return jid
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _load_image_from_path(path: str) -> Image.Image:
    return Image.open(path).convert("RGB")


def _download_image_from_url(url: str) -> Image.Image:
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def _pil_to_base64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def run_single_try_on_job(cfg: Settings, job_id: uuid.UUID, pipeline: object) -> None:
    db = SessionLocal()
    try:
        job = db.get(TryOnJob, job_id)
        if not job or job.status != TRY_ON_STATUS_PROCESSING:
            return

        log.info(
            "try_on job_id=%s category=%s person_path=%s garment_url_len=%s",
            job_id, job.category, job.person_image_path, len(job.garment_url),
        )

        try:
            person_image = _load_image_from_path(job.person_image_path)
        except Exception as e:
            log.exception("try_on job_id=%s: не удалось прочитать фото человека", job_id)
            _fail_job(db, job, f"Чтение фото человека: {e}")
            return

        try:
            garment_image = _download_image_from_url(job.garment_url)
        except Exception as e:
            log.exception("try_on job_id=%s: не удалось скачать фото одежды", job_id)
            _fail_job(db, job, f"Загрузка фото одежды: {e}")
            return

        t0 = time.monotonic()
        try:
            result = pipeline(person_image, garment_image, category=job.category)
            result_image: Image.Image = result.images[0]
        except Exception as e:
            dt = time.monotonic() - t0
            log.warning("try_on job_id=%s VTON failed за %.1fs: %s", job_id, dt, e, exc_info=True)
            _fail_job(db, job, f"VTON inference: {e}")
            return
        dt = time.monotonic() - t0
        log.info("try_on job_id=%s VTON OK за %.1fs", job_id, dt)

        try:
            result_url = _pil_to_base64(result_image)
        except Exception as e:
            log.exception("try_on job_id=%s: не удалось закодировать результат", job_id)
            _fail_job(db, job, f"Кодирование результата: {e}")
            return

        _success_job(db, job, result_url)

        # Удаляем временный файл фото человека
        try:
            os.unlink(job.person_image_path)
        except OSError as e:
            log.warning("try_on job_id=%s: не удалось удалить temp файл %s: %s", job_id, job.person_image_path, e)

        log.info("try_on job_id=%s завершён", job_id)

    except Exception as e:
        log.exception("try_on run_single_try_on_job job_id=%s", job_id)
        db.rollback()
        job = db.get(TryOnJob, job_id)
        if job and job.status == TRY_ON_STATUS_PROCESSING:
            _fail_job(db, job, str(e))
    finally:
        db.close()


def try_process_one_try_on_job(cfg: Settings, pipeline: object) -> None:
    jid = acquire_next_pending_job_id()
    if jid is None:
        return
    log.info("try_on_worker взял задачу job_id=%s", jid)
    run_single_try_on_job(cfg, jid, pipeline)