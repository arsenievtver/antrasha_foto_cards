"""Фоновая обработка очереди ai_ingest_jobs."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.database import SessionLocal
from app.models import AiIngestJob
from app.services.fashn_client import run_product_to_model_png
from app.services.image_prepare import build_fashn_product_image_data_url
from app.services.yc_photo_sync import ensure_photo_row_for_yc_key
from app.services.yc_storage import put_image_object

log = logging.getLogger("app.ai_ingest")


def reset_stale_processing_jobs(db: Session, *, older_than_minutes: int = 90) -> int:
    """Зависшие processing → pending (воркер упал)."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    res = db.execute(
        update(AiIngestJob)
        .where(
            AiIngestJob.status == "processing",
            AiIngestJob.started_at.is_not(None),
            AiIngestJob.started_at < cutoff,
        )
        .values(
            status="pending",
            started_at=None,
            error_message=None,
        ),
    )
    db.commit()
    n = res.rowcount or 0
    if n:
        log.warning("ai_ingest: сброшено зависших processing: %s", n)
    return n


def _fail_job(db: Session, job: AiIngestJob, message: str) -> None:
    job.status = "failed"
    job.error_message = (message or "")[:4000]
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def _success_job(
    db: Session,
    job: AiIngestJob,
    *,
    bucket: str,
    key: str,
) -> None:
    job.status = "completed"
    job.error_message = None
    job.result_bucket = bucket
    job.result_key = key
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def _bucket_and_prefix_for_gender(settings: Settings, gender: str) -> tuple[str, str]:
    g = gender.strip().lower()
    if g == "male":
        return settings.yc_bucket_men, (settings.yc_s3_prefix_men or "").strip()
    if g == "female":
        return settings.yc_bucket_women, (settings.yc_s3_prefix_women or "").strip()
    raise ValueError("gender must be male or female")


def _build_result_key(prefix: str) -> str:
    p = prefix.strip()
    if p and not p.endswith("/"):
        p += "/"
    return f"{p}ai/{uuid.uuid4()}.png"


def acquire_next_pending_job_id() -> uuid.UUID | None:
    db = SessionLocal()
    try:
        job = db.execute(
            select(AiIngestJob)
            .where(AiIngestJob.status == "pending")
            .order_by(AiIngestJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True),
        ).scalar_one_or_none()
        if job is None:
            return None
        jid = job.id
        job.status = "processing"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        return jid
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_single_ingest_job(cfg: Settings, job_id: uuid.UUID) -> None:
    db = SessionLocal()
    path: Path | None = None
    try:
        job = db.get(AiIngestJob, job_id)
        if not job:
            return
        if job.status != "processing":
            return
        path = Path(job.temp_path)
        if not path.is_file():
            _fail_job(db, job, "Временный файл не найден")
            return

        try:
            data_url = build_fashn_product_image_data_url(path)
        except Exception as e:
            log.exception("prepare image job_id=%s", job_id)
            _fail_job(db, job, f"Подготовка изображения: {e}")
            return

        png_bytes, err = run_product_to_model_png(
            cfg,
            gender=job.gender,
            product_image_data_url=data_url,
        )
        if err or not png_bytes:
            _fail_job(db, job, err or "Fashn не вернул изображение")
            return

        try:
            bucket, prefix = _bucket_and_prefix_for_gender(cfg, job.gender)
            key = _build_result_key(prefix)
            put_image_object(bucket, key, png_bytes, content_type="image/png")
            ensure_photo_row_for_yc_key(
                db,
                settings=cfg,
                gender=job.gender,
                bucket=bucket,
                key=key,
                brand_id=job.brand_id,
            )
            _success_job(db, job, bucket=bucket, key=key)
        except Exception as e:
            log.exception("s3 or db job_id=%s", job_id)
            db.rollback()
            job = db.get(AiIngestJob, job_id)
            if job:
                _fail_job(db, job, f"Загрузка или запись в БД: {e}")
            return

        if path.is_file():
            try:
                path.unlink()
            except OSError as unlink_err:
                log.warning("unlink temp %s: %s", path, unlink_err)
    except Exception as e:
        log.exception("run_single_ingest_job job_id=%s", job_id)
        db.rollback()
        job = db.get(AiIngestJob, job_id)
        if job and job.status == "processing":
            _fail_job(db, job, str(e))
    finally:
        db.close()


def try_process_one_ingest_job(cfg: Settings | None = None) -> None:
    cfg = cfg or settings
    if not cfg.fashn_configured or not cfg.yc_s3_configured:
        return
    jid = acquire_next_pending_job_id()
    if jid is None:
        return
    run_single_ingest_job(cfg, jid)


def count_pending_jobs(db: Session) -> int:
    n = db.scalar(
        select(func.count()).select_from(AiIngestJob).where(AiIngestJob.status == "pending"),
    )
    return int(n or 0)
