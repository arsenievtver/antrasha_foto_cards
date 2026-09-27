#!/usr/bin/env python3
"""Локальный прогон Fashn product-to-model (без админки/S3/ленты)."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "backend"))

from app.config import Settings  # noqa: E402
from app.externals.http.fashn import CONTENT_MODE_SINGLE, FRAME_FEED, FashnClient  # noqa: E402
from app.services.image_prepare import build_fashn_product_image_data_url  # noqa: E402

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}


def _safe_stem(path: Path) -> str:
    stem = path.stem.strip()
    stem = re.sub(r"[^\w\-]+", "_", stem, flags=re.UNICODE)
    return stem[:80] or "image"


def _list_images(folder: Path) -> list[Path]:
    files = [p for p in sorted(folder.iterdir()) if p.is_file() and p.suffix.lower() in _IMAGE_EXTS]
    return files


async def _run_one(
    client: FashnClient,
    *,
    gender: str,
    src: Path,
    out: Path,
    content_mode: str,
    frame: str,
) -> None:
    data_url = build_fashn_product_image_data_url(src)
    png = await client.run_product_to_model(
        gender=gender,
        product_image_data_url=data_url,
        content_mode=content_mode,
        frame=frame,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)


async def _run_batch(
    *,
    gender: str,
    input_dir: Path,
    output_dir: Path,
    content_mode: str,
    frame: str,
    skip_existing: bool,
    cfg: Settings,
) -> tuple[int, int]:
    images = _list_images(input_dir)
    if not images:
        print(f"No images in {input_dir}", file=sys.stderr)
        return 0, 0

    client = FashnClient(
        api_key=str(cfg.fashn_api_key).strip(),
        proxy=str(cfg.fashn_https_proxy).strip() if cfg.fashn_https_proxy else None,
        connect_timeout=cfg.fashn_http_connect_timeout,
        submit_timeout=cfg.fashn_http_read_timeout_submit,
        poll_timeout=cfg.fashn_http_read_timeout_poll,
        download_timeout=cfg.fashn_http_read_timeout_download,
    )
    ok, fail = 0, 0
    try:
        for i, src in enumerate(images, 1):
            out = output_dir / f"{_safe_stem(src)}.png"
            if skip_existing and out.is_file() and out.stat().st_size > 0:
                print(f"[{i}/{len(images)}] skip {src.name} → {out.name}")
                ok += 1
                continue
            print(f"[{i}/{len(images)}] {src.name} → {out.name} …", flush=True)
            t0 = time.monotonic()
            try:
                await _run_one(
                    client,
                    gender=gender,
                    src=src,
                    out=out,
                    content_mode=content_mode,
                    frame=frame,
                )
                print(f"    OK {out.stat().st_size // 1024} KiB in {time.monotonic() - t0:.1f}s")
                ok += 1
            except Exception as e:
                print(f"    FAIL {type(e).__name__}: {e}", file=sys.stderr)
                fail += 1
    finally:
        await client.close()
    return ok, fail


def main() -> int:
    p = argparse.ArgumentParser(description="Fashn product-to-model locally")
    p.add_argument("--gender", required=True, choices=("male", "female"))
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--content-mode",
        default=CONTENT_MODE_SINGLE,
        choices=("single", "look"),
        help="single — одна вещь-герой, остальное досочиняется; look — сохранить весь образ",
    )
    p.add_argument(
        "--frame",
        default=FRAME_FEED,
        choices=("feed", "outlet"),
        help="feed — кадр для свайп-ленты; outlet — плотный кроп для карточки МойСклад",
    )
    p.add_argument("--skip-existing", action="store_true")
    args = p.parse_args()

    cfg = Settings()
    if not cfg.fashn_configured:
        print("FASHN_API_KEY not set (backend/.env or repo .env)", file=sys.stderr)
        return 1

    ok, fail = asyncio.run(
        _run_batch(
            gender=args.gender,
            input_dir=args.input,
            output_dir=args.output,
            content_mode=args.content_mode,
            frame=args.frame,
            skip_existing=args.skip_existing,
            cfg=cfg,
        )
    )
    print(f"Done: ok={ok} fail={fail} → {args.output}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
