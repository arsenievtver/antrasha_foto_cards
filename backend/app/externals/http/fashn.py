"""Fashn API client (product-to-model)."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from pathlib import Path

from app.externals.http.base import BaseApiClient
from app.externals.http.exceptions import ApiClientAbortableException

log = logging.getLogger("app.fashn")

POLL_INTERVAL_SEC = 3.0
POLL_TIMEOUT_SEC = 300.0
MAX_RETRIES = 2

RESOLUTION = "2k"
GENERATION_MODE = "quality"
# Выбор лучшего кадра из нескольких не делаем — стараемся попасть с первого.
NUM_IMAGES = 1
MAX_SEED = 2**32 - 1

# Что делать с остальной одеждой: досочинить вокруг вещи-героя или сохранить весь образ.
# Вешалка это или человек, Fashn видит сам по картинке — в промпте различать не нужно.
CONTENT_MODE_SINGLE = "single"
CONTENT_MODE_LOOK = "look"
VALID_CONTENT_MODES = frozenset({CONTENT_MODE_SINGLE, CONTENT_MODE_LOOK})

# Значения source_mode до миграции 055; старые сборки админки могут ещё их присылать.
_LEGACY_CONTENT_MODES = {
    "flatlay": CONTENT_MODE_SINGLE,
    "on_model": CONTENT_MODE_LOOK,
}

# Куда уедет кадр: свайп-лента PWA или картинка товара в МойСклад.
FRAME_FEED = "feed"
FRAME_OUTLET = "outlet"
VALID_FRAMES = frozenset({FRAME_FEED, FRAME_OUTLET})

# Карточка ленты — 400×700 (≈9:16), картинка товара в МойСклад — 3:4.
# Промах по соотношению съедает пиксели в object-fit: cover ещё до показа.
ASPECT_RATIO_BY_FRAME = {
    FRAME_FEED: "9:16",
    FRAME_OUTLET: "3:4",
}

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
_PROMPT_PART_CACHE: dict[str, str] = {}


def normalize_content_mode(content_mode: str | None) -> str:
    mode = (content_mode or CONTENT_MODE_SINGLE).strip().lower()
    mode = _LEGACY_CONTENT_MODES.get(mode, mode)
    if mode not in VALID_CONTENT_MODES:
        raise ValueError("content_mode must be single or look")
    return mode


def normalize_frame(frame: str | None) -> str:
    f = (frame or FRAME_FEED).strip().lower()
    if f not in VALID_FRAMES:
        raise ValueError("frame must be feed or outlet")
    return f


def _load_prompt_part(name: str) -> str:
    if name in _PROMPT_PART_CACHE:
        return _PROMPT_PART_CACHE[name]
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt part missing: {path}")
    _PROMPT_PART_CACHE[name] = path.read_text(encoding="utf-8").strip()
    return _PROMPT_PART_CACHE[name]


def load_prompt(
    gender: str,
    content_mode: str = CONTENT_MODE_SINGLE,
    frame: str = FRAME_FEED,
) -> str:
    """
    Собирает промпт из блоков в порядке, который советует Fashn: сначала тип кадра
    и субъект, затем правило по содержанию, в конце свет и палитра — хвост длинного
    промпта модель игнорирует, поэтому важное идёт первым.
    """
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise ValueError("gender must be male or female")
    parts = (
        f"frame_{normalize_frame(frame)}",
        f"model_{g}",
        f"content_{normalize_content_mode(content_mode)}",
        "style",
    )
    return "\n".join(_load_prompt_part(p) for p in parts)


class FashnClient(BaseApiClient):
    BASE_URL = "https://api.fashn.ai/v1/"

    def __init__(
        self,
        api_key: str,
        *,
        proxy: str | None = None,
        connect_timeout: float = 10.0,
        submit_timeout: float = 60.0,
        poll_timeout: float = 30.0,
        download_timeout: float = 60.0,
    ) -> None:
        super().__init__(keep_session=True)
        self._api_key = api_key.strip()
        self._proxy = proxy or None
        self._connect_timeout = connect_timeout
        self._submit_timeout = submit_timeout
        self._poll_timeout = poll_timeout
        self._download_timeout = download_timeout

    @property
    def base_url(self) -> str:
        return self.BASE_URL

    @property
    def base_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _proxy_kwargs(self) -> dict:
        return {"proxy": self._proxy} if self._proxy else {}

    async def submit(
        self,
        *,
        product_image_data_url: str,
        prompt: str,
        aspect_ratio: str,
        seed: int,
        generation_mode: str = GENERATION_MODE,
    ) -> str:
        """Submits a job to the Fashn API, returns job_id."""
        payload = {
            "model_name": "product-to-model",
            "inputs": {
                "product_image": product_image_data_url,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": RESOLUTION,
                "generation_mode": generation_mode,
                "num_images": NUM_IMAGES,
                "output_format": "png",
                "return_base64": False,
                "seed": seed,
            },
        }
        try:
            resp = await self.post("/run", json=payload, **self._proxy_kwargs())
        except ApiClientAbortableException as e:
            log.warning(
                "fashn submit HTTP %s body=%s",
                e.response.status,
                str(e.parsed_response)[:500],
            )
            raise
        log.info("fashn submit HTTP %s body=%s", resp.status, str(resp.parsed_response)[:300])
        job_id = (resp.parsed_response or {}).get("id")
        if not job_id:
            raise ValueError(f"Fashn: response missing id (HTTP {resp.status}): {resp.parsed_response}")
        jid = str(job_id)
        log.info("fashn submit OK remote_id=%s… (len=%s)", jid[:10], len(jid))
        return jid

    async def poll_status(self, job_id: str) -> list[str]:
        """Polls job status until completion, returns list of result URLs."""
        started = time.monotonic()
        next_log_at = 0.0
        while True:
            elapsed = time.monotonic() - started
            if elapsed > POLL_TIMEOUT_SEC:
                raise TimeoutError(f"Fashn: polling timeout after {POLL_TIMEOUT_SEC}s (job={job_id})")
            try:
                resp = await self.get(f"/status/{job_id}", **self._proxy_kwargs())
            except ApiClientAbortableException as e:
                raise RuntimeError(f"Fashn poll HTTP {e.response.status}") from e

            data: dict = resp.parsed_response or {}
            status = data.get("status")

            now = time.monotonic()
            if now >= next_log_at:
                log.info(
                    "fashn poll id=%s… status=%s elapsed=%.0fs/%.0fs",
                    job_id[:12], status, now - started, POLL_TIMEOUT_SEC,
                )
                next_log_at = now + 45.0

            if status == "completed":
                out = data.get("output") or []
                if not isinstance(out, list):
                    raise ValueError("Fashn: unexpected output format")
                return [str(u) for u in out if u]
            if status == "failed":
                raise RuntimeError(f"Fashn job failed: {str(data.get('error') or data)[:500]}")

            await asyncio.sleep(POLL_INTERVAL_SEC)

    async def download_png(self, url: str) -> bytes:
        """Downloads PNG from a Fashn result URL."""
        async with self.session.get(url, **self._proxy_kwargs()) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Fashn download HTTP {resp.status}: {url}")
            return await resp.read()

    async def submit_tryon_v16(
        self,
        *,
        model_image: str,
        garment_image: str,
        garment_photo_type: str = "model",
    ) -> str:
        """Virtual try-on v1.6: person + garment → job_id."""
        payload = {
            "model_name": "tryon-v1.6",
            "inputs": {
                "model_image": model_image,
                "garment_image": garment_image,
                "garment_photo_type": garment_photo_type,
                "category": "auto",
                "mode": "quality",
                "segmentation_free": True,
                "output_format": "png",
                "return_base64": False,
            },
        }
        try:
            resp = await self.post("/run", json=payload, **self._proxy_kwargs())
        except ApiClientAbortableException as e:
            log.warning(
                "fashn tryon submit HTTP %s body=%s",
                e.response.status,
                str(e.parsed_response)[:500],
            )
            raise
        log.info("fashn tryon submit HTTP %s body=%s", resp.status, str(resp.parsed_response)[:300])
        job_id = (resp.parsed_response or {}).get("id")
        if not job_id:
            raise ValueError(
                f"Fashn tryon: response missing id (HTTP {resp.status}): {resp.parsed_response}"
            )
        jid = str(job_id)
        log.info("fashn tryon submit OK remote_id=%s…", jid[:10])
        return jid

    async def run_tryon_v16(
        self,
        *,
        model_image: str,
        garment_image: str,
        garment_photo_type: str = "model",
    ) -> bytes:
        """submit → poll → download PNG."""
        last_err: Exception = RuntimeError("Unknown error")
        try:
            for attempt in range(MAX_RETRIES):
                log.info("fashn tryon-v1.6 attempt %s/%s", attempt + 1, MAX_RETRIES)
                try:
                    job_id = await self.submit_tryon_v16(
                        model_image=model_image,
                        garment_image=garment_image,
                        garment_photo_type=garment_photo_type,
                    )
                    urls = await self.poll_status(job_id)
                    if not urls:
                        raise ValueError("Fashn tryon: empty output")
                    return await self.download_png(urls[0])
                except Exception as e:
                    last_err = e
                    log.warning(
                        "fashn tryon attempt %s/%s failed: %s: %s",
                        attempt + 1,
                        MAX_RETRIES,
                        type(e).__name__,
                        e,
                        exc_info=True,
                    )
            raise last_err
        finally:
            await self.close()

    async def run_product_to_model(
        self,
        *,
        gender: str,
        product_image_data_url: str,
        content_mode: str = CONTENT_MODE_SINGLE,
        frame: str = FRAME_FEED,
    ) -> bytes:
        """Full submit → poll → download cycle with MAX_RETRIES attempts."""
        mode = normalize_content_mode(content_mode)
        frm = normalize_frame(frame)
        prompt = load_prompt(gender, mode, frm)
        aspect_ratio = ASPECT_RATIO_BY_FRAME[frm]
        # Seed на задачу, а не на модуль: на фиксированном seed лента из сотни фото
        # сходилась к одному лицу и одной позе.
        seed = random.randint(0, MAX_SEED)
        last_err: Exception = RuntimeError("Unknown error")
        try:
            for attempt in range(MAX_RETRIES):
                log.info(
                    "fashn product-to-model attempt %s/%s gender=%s content_mode=%s "
                    "frame=%s aspect=%s resolution=%s seed=%s",
                    attempt + 1,
                    MAX_RETRIES,
                    gender,
                    mode,
                    frm,
                    aspect_ratio,
                    RESOLUTION,
                    seed,
                )
                try:
                    job_id = await self.submit(
                        product_image_data_url=product_image_data_url,
                        prompt=prompt,
                        aspect_ratio=aspect_ratio,
                        seed=seed,
                    )
                    urls = await self.poll_status(job_id)
                    if not urls:
                        raise ValueError("Fashn: empty output")
                    return await self.download_png(urls[0])
                except Exception as e:
                    last_err = e
                    log.warning(
                        "fashn attempt %s/%s failed: %s: %s",
                        attempt + 1, MAX_RETRIES, type(e).__name__, e,
                        exc_info=True,
                    )
            raise last_err
        finally:
            await self.close()