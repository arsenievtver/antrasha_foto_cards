"""Fashn API client (product-to-model)."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from app.externals.http.base import BaseApiClient
from app.externals.http.exceptions import ApiClientAbortableException

log = logging.getLogger("app.fashn")

POLL_INTERVAL_SEC = 3.0
POLL_TIMEOUT_SEC = 300.0
MAX_RETRIES = 2

ASPECT_RATIO = "4:5"
RESOLUTION = "1k"
NUM_IMAGES = 1
SEED = 42

SOURCE_MODE_FLATLAY = "flatlay"
SOURCE_MODE_ON_MODEL = "on_model"
SOURCE_MODE_OUTLET_CATALOG = "outlet_catalog"
# AI ingest UI / очередь — только эти режимы.
VALID_INGEST_SOURCE_MODES = frozenset({SOURCE_MODE_FLATLAY, SOURCE_MODE_ON_MODEL})
VALID_SOURCE_MODES = frozenset(
    {*VALID_INGEST_SOURCE_MODES, SOURCE_MODE_OUTLET_CATALOG}
)

# on_model / outlet_catalog: tighter garment fidelity; costs more credits / slower.
GENERATION_MODE_BY_SOURCE = {
    SOURCE_MODE_FLATLAY: "balanced",
    SOURCE_MODE_ON_MODEL: "quality",
    SOURCE_MODE_OUTLET_CATALOG: "quality",
}

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
_PROMPT_CACHE: dict[str, str] = {}


def normalize_source_mode(source_mode: str | None) -> str:
    mode = (source_mode or SOURCE_MODE_FLATLAY).strip().lower()
    if mode not in VALID_SOURCE_MODES:
        raise ValueError(
            "source_mode must be flatlay, on_model, or outlet_catalog"
        )
    return mode


def load_prompt_for_gender(gender: str, source_mode: str = SOURCE_MODE_FLATLAY) -> str:
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise ValueError("gender must be male or female")
    mode = normalize_source_mode(source_mode)
    cache_key = f"{g}:{mode}"
    if cache_key in _PROMPT_CACHE:
        return _PROMPT_CACHE[cache_key]
    path = _PROMPTS_DIR / f"promt_{g}_{mode}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    _PROMPT_CACHE[cache_key] = path.read_text(encoding="utf-8")
    return _PROMPT_CACHE[cache_key]


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
        generation_mode: str = "balanced",
    ) -> str:
        """Submits a job to the Fashn API, returns job_id."""
        payload = {
            "model_name": "product-to-model",
            "inputs": {
                "product_image": product_image_data_url,
                "prompt": prompt,
                "aspect_ratio": ASPECT_RATIO,
                "resolution": RESOLUTION,
                "generation_mode": generation_mode,
                "num_images": NUM_IMAGES,
                "output_format": "png",
                "return_base64": False,
                "seed": SEED,
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
        source_mode: str = SOURCE_MODE_FLATLAY,
    ) -> bytes:
        """Full submit → poll → download cycle with MAX_RETRIES attempts."""
        mode = normalize_source_mode(source_mode)
        prompt = load_prompt_for_gender(gender, mode)
        generation_mode = GENERATION_MODE_BY_SOURCE[mode]
        last_err: Exception = RuntimeError("Unknown error")
        try:
            for attempt in range(MAX_RETRIES):
                log.info(
                    "fashn product-to-model attempt %s/%s gender=%s source_mode=%s generation_mode=%s",
                    attempt + 1,
                    MAX_RETRIES,
                    gender,
                    mode,
                    generation_mode,
                )
                try:
                    job_id = await self.submit(
                        product_image_data_url=product_image_data_url,
                        prompt=prompt,
                        generation_mode=generation_mode,
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