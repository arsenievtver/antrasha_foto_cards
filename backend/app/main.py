import asyncio
import logging
import time

from sqlalchemy.exc import ProgrammingError

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DOTENV_LOADED_PATHS, settings
from app.logging_config import setup_logging
from app.database import SessionLocal
from app.routers import admin, admin_ai_ingest, auth, feed, guest, interactions, internal_sync, sessions
from app.services.ai_ingest_worker import reset_stale_processing_jobs, try_process_one_ingest_job
from app.services.yc_photo_sync import run_sync_job_commit

log = logging.getLogger("app.main")

# Чтобы не забивать лог при concurrency>1: одно предупреждение на все слоты воркера.
_last_ai_ingest_skip_warn_monotonic: float = 0.0


async def _yc_auto_sync_loop() -> None:
    interval_sec = max(60, settings.yc_auto_sync_interval_minutes * 60)
    await asyncio.sleep(45)
    while True:
        try:
            if settings.yc_s3_configured:
                await asyncio.to_thread(
                    lambda: run_sync_job_commit(
                        settings,
                        deactivate_not_in_bucket=True,
                    ),
                )
            else:
                log.warning("yc_auto_sync: пропуск — S3 ключи не заданы")
        except Exception:
            log.exception("yc_auto_sync: ошибка синхронизации с Object Storage")
        await asyncio.sleep(interval_sec)


async def _ai_ingest_worker_slots() -> None:
    n = max(1, settings.ai_ingest_worker_concurrency)
    await asyncio.gather(*[_ai_ingest_worker_slot() for _ in range(n)])


async def _ai_ingest_worker_slot() -> None:
    global _last_ai_ingest_skip_warn_monotonic
    while True:
        await asyncio.sleep(0.28)
        if not settings.fashn_configured or not settings.yc_s3_configured:
            now = time.monotonic()
            if now - _last_ai_ingest_skip_warn_monotonic >= 90:
                _last_ai_ingest_skip_warn_monotonic = now
                log.warning(
                    "ai_ingest: воркер не обрабатывает очередь — нужны FASHN_API_KEY и пара "
                    "YC_S3_ACCESS_KEY_ID / YC_S3_SECRET_ACCESS_KEY. Сейчас fashn_configured=%s "
                    "yc_s3_configured=%s",
                    settings.fashn_configured,
                    settings.yc_s3_configured,
                )
            await asyncio.sleep(2.5)
            continue
        try:
            await asyncio.to_thread(try_process_one_ingest_job, settings)
        except Exception:
            log.exception("ai_ingest worker")


async def lifespan(_app: FastAPI):
    setup_logging()
    log.info(
        "Antrasha API старт, LOG_LEVEL=%s, yc_auto_sync_interval_minutes=%s",
        settings.log_level,
        settings.yc_auto_sync_interval_minutes,
    )
    log.info(
        ".env подхвачен из (если список пуст — переменные только из окружения ОС): %s | "
        "FASHN_API_KEY задан=%s | API_XIMILAR (эксп.) задан=%s",
        [str(p) for p in DOTENV_LOADED_PATHS],
        settings.fashn_configured,
        settings.ximilar_configured,
    )
    db_boot = SessionLocal()
    try:
        try:
            reset_stale_processing_jobs(db_boot, older_than_minutes=90)
        except ProgrammingError:
            db_boot.rollback()
            log.warning(
                "lifespan: reset_stale_processing_jobs пропущен — БД без миграций или нет таблицы ai_ingest_jobs; выполните alembic upgrade head",
            )
    finally:
        db_boot.close()

    task: asyncio.Task | None = None
    ai_task: asyncio.Task | None = None
    if settings.yc_auto_sync_interval_minutes > 0:
        task = asyncio.create_task(_yc_auto_sync_loop())
        log.info("Фоновая синхронизация Object Storage включена")
    ai_task = asyncio.create_task(_ai_ingest_worker_slots())
    log.info(
        "Очередь ИИ-ingest: concurrency=%s fashn=%s yc=%s",
        settings.ai_ingest_worker_concurrency,
        settings.fashn_configured,
        settings.yc_s3_configured,
    )
    yield
    if ai_task:
        ai_task.cancel()
        try:
            await ai_task
        except asyncio.CancelledError:
            pass
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Antrasha API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(guest.router)
app.include_router(feed.router)
app.include_router(interactions.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(admin_ai_ingest.router)
app.include_router(internal_sync.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

