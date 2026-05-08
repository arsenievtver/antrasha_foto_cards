"""Клиент Fashn API (product-to-model)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

from app.config import Settings

log = logging.getLogger("app.fashn")

RUN_URL = "https://api.fashn.ai/v1/run"
STATUS_URL = "https://api.fashn.ai/v1/status/{}"

POLL_INTERVAL_SEC = 3.0
TIMEOUT_SEC = 300.0
MAX_RETRIES = 2

ASPECT_RATIO = "4:5"
RESOLUTION = "1k"
NUM_IMAGES = 1
SEED = 42

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PROMPT_CACHE: dict[str, str] = {}


def _timeout(settings: Settings, read_sec: float) -> tuple[float, float]:
    """Connect / read для requests (тяжёлый POST на submit нуждается в большом read)."""
    return (settings.fashn_http_connect_timeout, read_sec)


def _proxies(settings: Settings) -> dict[str, str] | None:
    p = settings.fashn_https_proxy
    if not p or not str(p).strip():
        return None
    u = str(p).strip()
    return {"http": u, "https": u}


def _prompt_filename_for_gender(gender: str) -> str:
    g = gender.strip().lower()
    if g == "male":
        return "promt_male.txt"
    if g == "female":
        return "promt_female.txt"
    raise ValueError("gender must be male or female")


def load_prompt_for_gender(gender: str) -> str:
    key = gender.strip().lower()
    if key in _PROMPT_CACHE:
        return _PROMPT_CACHE[key]
    name = _prompt_filename_for_gender(gender)
    path = _PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    text = path.read_text(encoding="utf-8")
    _PROMPT_CACHE[key] = text
    return text


def submit_job(settings: Settings, *, product_image_data_url: str, prompt: str) -> tuple[str | None, str | None]:
    api_key = settings.fashn_api_key
    if not api_key or not str(api_key).strip():
        return None, "FASHN_API_KEY не задан"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model_name": "product-to-model",
        "inputs": {
            "product_image": product_image_data_url,
            "prompt": prompt,
            "aspect_ratio": ASPECT_RATIO,
            "resolution": RESOLUTION,
            "num_images": NUM_IMAGES,
            "output_format": "png",
            "return_base64": False,
            "seed": SEED,
        },
    }
    try:
        r = requests.post(
            RUN_URL,
            headers=headers,
            json=payload,
            timeout=_timeout(settings, settings.fashn_http_read_timeout_submit),
            proxies=_proxies(settings),
        )
    except requests.RequestException as e:
        return None, str(e)
    if r.status_code != 200:
        return None, r.text[:2000]
    data = r.json()
    jid = data.get("id")
    if not jid:
        return None, "Ответ Fashn без id"
    return str(jid), None


def poll_status(settings: Settings, job_id: str) -> tuple[list[str], str | None]:
    api_key = settings.fashn_api_key
    if not api_key:
        return [], "FASHN_API_KEY не задан"
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    started = time.monotonic()
    while True:
        if time.monotonic() - started > TIMEOUT_SEC:
            return [], "Timeout ожидания Fashn"
        try:
            r = requests.get(
                STATUS_URL.format(job_id),
                headers=headers,
                timeout=_timeout(settings, settings.fashn_http_read_timeout_poll),
                proxies=_proxies(settings),
            )
        except requests.RequestException as e:
            return [], str(e)
        if r.status_code != 200:
            return [], r.text[:2000]
        data = r.json()
        status = data.get("status")
        if status == "completed":
            out = data.get("output") or []
            if isinstance(out, list):
                return [str(u) for u in out if u], None
            return [], "Некорректный output"
        if status == "failed":
            return [], str(data.get("error") or data)[:2000]
        time.sleep(POLL_INTERVAL_SEC)


def download_png_bytes(url: str, *, settings: Settings) -> tuple[bytes | None, str | None]:
    try:
        r = requests.get(
            url,
            timeout=_timeout(settings, settings.fashn_http_read_timeout_download),
            proxies=_proxies(settings),
        )
    except requests.RequestException as e:
        return None, str(e)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    return r.content, None


def run_product_to_model_png(settings: Settings, *, gender: str, product_image_data_url: str) -> tuple[bytes | None, str | None]:
    """Полный цикл с ретраями submit/poll/download."""
    prompt = load_prompt_for_gender(gender)
    last_err = "Неизвестная ошибка"
    for attempt in range(MAX_RETRIES):
        jid, err = submit_job(settings, product_image_data_url=product_image_data_url, prompt=prompt)
        if err:
            last_err = err
            log.warning("fashn submit attempt %s: %s", attempt + 1, err)
            continue
        urls, err = poll_status(settings, jid)
        if err:
            last_err = err
            log.warning("fashn poll attempt %s: %s", attempt + 1, err)
            continue
        if not urls:
            last_err = "Пустой output"
            continue
        png, derr = download_png_bytes(urls[0], settings=settings)
        if derr or not png:
            last_err = derr or "Пустые байты"
            continue
        return png, None
    return None, last_err
