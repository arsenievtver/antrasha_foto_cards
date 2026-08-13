from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger("app.video_transcode")

FFMPEG_TIMEOUT_SEC = 180

# H.264 + AAC, faststart, длинная сторона ≤ 1280 — мобильный стрим без просадки качества.
_SCALE = (
    "scale='min(1280,iw)':'min(1280,ih)':force_original_aspect_ratio=decrease,"
    "scale=trunc(iw/2)*2:trunc(ih/2)*2"
)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _run(cmd: list[str], *, timeout: int = FFMPEG_TIMEOUT_SEC) -> None:
    try:
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Обработка видео заняла слишком много времени") from exc
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[-800:]
        raise RuntimeError(err or f"ffmpeg exit {proc.returncode}")


def transcode_to_mp4(src: Path, dest: Path) -> None:
    """Сжимает ролик в mp4 с moov в начале (быстрый старт на телефоне)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        _run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(src),
                "-vf",
                _SCALE,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-ac",
                "2",
                str(dest),
            ],
        )
        return
    except Exception:
        log.exception("ffmpeg transcode failed, trying remux +faststart")

    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(src),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(dest),
        ],
    )


def extract_poster(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "0.4",
            "-i",
            str(src),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(dest),
        ],
        timeout=30,
    )
