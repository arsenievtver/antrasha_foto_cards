"""Фоновая обработка очереди ai_ingest_jobs."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, noload

from app.config import Settings, settings
from app.database import SessionLocal
from app.externals.http.fashn import (
    FRAME_FEED,
    FashnClient,
    FashnJobFailed,
    FashnJobGone,
    normalize_content_mode,
)
from app.models import AiIngestJob, Photo
from app.services.feed_release_batch import (
    get_or_create_draft_batch,
    pick_draft_photo_needing_embedding,
)
from app.services.image_prepare import jpeg_bytes_for_fashn_file, png_bytes_to_webp
from app.services.photo_embedding import (
    embed_image_bytes,
    embed_photo_url,
    upsert_photo_embedding,
)
from app.services.yc_photo_sync import ensure_photo_row_for_yc_key
from app.services.yc_storage import (
    delete_fashn_source,
    public_object_url,
    put_fashn_source_jpeg,
    put_image_object,
)

log = logging.getLogger("app.ai_ingest")

STAGE_UPLOAD = "upload"
STAGE_SAVE = "save"
# Вся задача: отправка, ожидание до 5 минут и скачивание. Дольше — значит зависла.
JOB_DEADLINE_SEC = 15 * 60
# Этап не менялся дольше — задача ничья, её можно вернуть в очередь или удалить.
STALE_PROCESSING_MINUTES = 20


def reset_stale_processing_jobs(
    db: Session,
    *,
    older_than_minutes: int = STALE_PROCESSING_MINUTES,
) -> int:
    """
    processing без движения дольше срока → pending (воркер упал или перезапущен).
    fashn_job_id остаётся: повтор продолжит оплаченный заказ, а не закажет новый.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    res = db.execute(
        update(AiIngestJob)
        .where(
            AiIngestJob.status == "processing",
            func.coalesce(AiIngestJob.stage_at, AiIngestJob.started_at, AiIngestJob.created_at) < cutoff,
        )
        .values(
            status="pending",
            started_at=None,
            stage=None,
            stage_at=None,
            error_message=None,
        ),
    )
    db.commit()
    n = res.rowcount or 0
    if n:
        log.warning("ai_ingest: сброшено зависших processing: %s", n)
    return n


def is_processing_stale(job: AiIngestJob) -> bool:
    last = job.stage_at or job.started_at or job.created_at
    if last is None:
        return True
    return last < datetime.now(timezone.utc) - timedelta(minutes=STALE_PROCESSING_MINUTES)


def _complete_job(
    db: Session,
    job: AiIngestJob,
    *,
    bucket: str,
    key: str,
    photo_id: uuid.UUID,
    release_batch_id: uuid.UUID,
) -> None:
    job.status = "completed"
    job.stage = None
    job.error_message = None
    job.result_bucket = bucket
    job.result_key = key
    job.photo_id = photo_id
    job.release_batch_id = release_batch_id
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def _fail_job(db: Session, job: AiIngestJob, message: str) -> None:
    job.status = "failed"
    job.stage = None
    job.error_message = (message or "")[:4000]
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
    return f"{p}ai/{uuid.uuid4()}.webp"


def acquire_next_pending_job_id() -> uuid.UUID | None:
    db = SessionLocal()
    try:
        # Без noload: у AiIngestJob brand — lazy="joined", в SELECT попадает JOIN к brands.
        # Тогда execute().scalar_one_or_none() не подходит для строки ORM+JOIN (см. SA 2 «ORM Rows»);
        # в итоге воркер мог не получать ни одной задачи при живой очереди.
        job = db.scalars(
            select(AiIngestJob)
            .options(noload(AiIngestJob.brand))
            .where(AiIngestJob.status == "pending")
            .order_by(AiIngestJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True),
        ).first()
        if job is None:
            return None
        jid = job.id
        now = datetime.now(timezone.utc)
        job.status = "processing"
        job.started_at = now
        job.stage = None
        job.stage_at = now
        db.commit()
        return jid
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _set_stage(job_id: uuid.UUID, stage: str) -> None:
    db = SessionLocal()
    try:
        db.execute(
            update(AiIngestJob)
            .where(AiIngestJob.id == job_id, AiIngestJob.status == "processing")
            .values(stage=stage, stage_at=datetime.now(timezone.utc)),
        )
        db.commit()
    finally:
        db.close()


def _save_fashn_job_id(job_id: uuid.UUID, remote_id: str | None) -> None:
    db = SessionLocal()
    try:
        db.execute(
            update(AiIngestJob).where(AiIngestJob.id == job_id).values(fashn_job_id=remote_id),
        )
        db.commit()
    finally:
        db.close()


def _fashn_client(cfg: Settings) -> FashnClient:
    return FashnClient(
        api_key=str(cfg.fashn_api_key).strip(),
        proxy=cfg.fashn_proxy_url,
        connect_timeout=cfg.fashn_http_connect_timeout,
        submit_timeout=cfg.fashn_http_read_timeout_submit,
        poll_timeout=cfg.fashn_http_read_timeout_poll,
        download_timeout=cfg.fashn_http_read_timeout_download,
    )


def _generate_png(cfg: Settings, job: AiIngestJob, path: Path) -> bytes:
    """Fashn: новый заказ или продолжение уже оплаченного (job.fashn_job_id)."""
    job_id = job.id
    source_bucket, _prefix = _bucket_and_prefix_for_gender(cfg, job.gender)
    uploaded: list[str] = []

    def source_url() -> str:
        _set_stage(job_id, STAGE_UPLOAD)
        jpeg = jpeg_bytes_for_fashn_file(path)
        key = put_fashn_source_jpeg(source_bucket, jpeg)
        uploaded.append(key)
        url = public_object_url(source_bucket, key)
        log.info("ai_ingest job_id=%s исходник для Fashn %s (%s байт)", job_id, url, len(jpeg))
        return url

    async def run() -> bytes:
        client = _fashn_client(cfg)
        return await asyncio.wait_for(
            client.run_product_to_model(
                gender=job.gender,
                product_image_url=source_url,
                content_mode=normalize_content_mode(job.source_mode),
                frame=FRAME_FEED,
                remote_id=job.fashn_job_id,
                on_submitted=lambda rid: _save_fashn_job_id(job_id, rid),
                on_stage=lambda st: _set_stage(job_id, st),
            ),
            timeout=JOB_DEADLINE_SEC,
        )

    try:
        return asyncio.run(run())
    finally:
        for key in uploaded:
            try:
                delete_fashn_source(source_bucket, key)
            except Exception:
                log.warning("ai_ingest job_id=%s не удалился исходник %s", job_id, key, exc_info=True)


def _embed_new_photo(db: Session, photo_id: uuid.UUID, webp_bytes: bytes) -> None:
    """Вектор сразу из готового файла. Ошибка не валит задачу — фото подберёт embed-цикл воркера."""
    try:
        vec = embed_image_bytes(webp_bytes, suffix=".webp")
        upsert_photo_embedding(db, photo_id=photo_id, embedding=vec)
        photo = db.get(Photo, photo_id)
        if photo:
            photo.vector_embed_error = None
        db.commit()
        log.info("ai_ingest вектор записан photo_id=%s", photo_id)
    except Exception as e:
        db.rollback()
        log.warning("ai_ingest вектор photo_id=%s: %s", photo_id, e, exc_info=True)
        photo = db.get(Photo, photo_id)
        if photo:
            photo.vector_embed_error = f"{type(e).__name__}: {e}"[:2000]
            db.commit()


def run_single_ingest_job(cfg: Settings, job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(AiIngestJob, job_id)
        if not job or job.status != "processing":
            return
        path = Path(job.temp_path)
        log.info(
            "ai_ingest job_id=%s gender=%s content_mode=%s fashn_job_id=%s file=%s",
            job_id,
            job.gender,
            job.source_mode,
            job.fashn_job_id,
            path.is_file(),
        )
        if not job.fashn_job_id and not path.is_file():
            _fail_job(db, job, "Временный файл не найден — загрузите фото снова")
            return

        t0 = time.monotonic()
        try:
            png_bytes = _generate_png(cfg, job, path)
        except (FashnJobFailed, FashnJobGone) as e:
            db.rollback()
            job = db.get(AiIngestJob, job_id)
            if job:
                # Этот заказ уже не вернёт картинку: «Повтор» сделает новый.
                job.fashn_job_id = None
                _fail_job(db, job, f"Fashn: {e}")
            return
        except Exception as e:
            dt = time.monotonic() - t0
            log.warning(
                "ai_ingest job_id=%s Fashn за %.1fs: %s: %s",
                job_id, dt, type(e).__name__, str(e)[:500],
                exc_info=True,
            )
            db.rollback()
            job = db.get(AiIngestJob, job_id)
            if job:
                hint = " — «Повтор» продолжит оплаченный заказ" if job.fashn_job_id else ""
                _fail_job(db, job, f"{type(e).__name__}: {e}{hint}"[:4000])
            return
        log.info(
            "ai_ingest job_id=%s Fashn OK за %.1fs, png=%s байт",
            job_id, time.monotonic() - t0, len(png_bytes),
        )

        _set_stage(job_id, STAGE_SAVE)
        try:
            webp_bytes = png_bytes_to_webp(png_bytes, quality=100)
            bucket, prefix = _bucket_and_prefix_for_gender(cfg, job.gender)
            key = _build_result_key(prefix)
            put_image_object(bucket, key, webp_bytes, content_type="image/webp")
            db.refresh(job)
            batch_id = job.release_batch_id
            if batch_id is None:
                batch_id = get_or_create_draft_batch(db, gender=job.gender).id
            photo = ensure_photo_row_for_yc_key(
                db,
                settings=cfg,
                gender=job.gender,
                bucket=bucket,
                key=key,
                brand_id=job.brand_id,
                show_badge=bool(job.show_badge),
                feed_visible=False,
                release_batch_id=batch_id,
            )
            _complete_job(
                db,
                job,
                bucket=bucket,
                key=key,
                photo_id=photo.id,
                release_batch_id=batch_id,
            )
            log.info("ai_ingest job_id=%s OK → photo_id=%s batch=%s", job_id, photo.id, batch_id)
        except Exception as e:
            log.exception("save job_id=%s", job_id)
            db.rollback()
            job = db.get(AiIngestJob, job_id)
            if job:
                _fail_job(db, job, f"Сохранение результата: {e} — «Повтор» продолжит оплаченный заказ")
            return

        if path.is_file():
            try:
                path.unlink()
            except OSError as unlink_err:
                log.warning("unlink temp %s: %s", path, unlink_err)

        _embed_new_photo(db, photo.id, webp_bytes)
    except Exception as e:
        log.exception("run_single_ingest_job job_id=%s", job_id)
        db.rollback()
        job = db.get(AiIngestJob, job_id)
        if job and job.status == "processing":
            _fail_job(db, job, str(e))
    finally:
        db.close()


def embed_one_draft_photo() -> bool:
    """Догоняет векторы черновиков (ошибка при создании, фото до этой версии). True — было что делать."""
    db = SessionLocal()
    try:
        photo = pick_draft_photo_needing_embedding(db)
        if photo is None:
            return False
        pid, url = photo.id, photo.url
        try:
            vec = embed_photo_url(url)
            upsert_photo_embedding(db, photo_id=pid, embedding=vec)
            photo.vector_embed_error = None
            db.commit()
            log.info("embed draft photo_id=%s OK", pid)
            return True
        except Exception as e:
            db.rollback()
            row = db.get(Photo, pid)
            if row:
                row.vector_embed_error = f"{type(e).__name__}: {e}"[:2000]
                db.commit()
            log.warning("embed draft photo_id=%s: %s", pid, e)
            raise
    finally:
        db.close()


def try_process_one_ingest_job(cfg: Settings | None = None) -> None:
    cfg = cfg or settings
    if not cfg.fashn_configured or not cfg.yc_s3_configured:
        return
    jid = acquire_next_pending_job_id()
    if jid is None:
        return
    log.info("ai_ingest взял задачу в работу job_id=%s", jid)
    run_single_ingest_job(cfg, jid)


def count_pending_jobs(db: Session) -> int:
    n = db.scalar(
        select(func.count()).select_from(AiIngestJob).where(AiIngestJob.status == "pending"),
    )
    return int(n or 0)
