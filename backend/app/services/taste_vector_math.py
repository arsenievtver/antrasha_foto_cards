from __future__ import annotations

import math
from typing import Sequence


def l2_normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(float(x) * float(x) for x in vec))
    if norm <= 1e-12:
        return [float(x) for x in vec]
    return [float(x) / norm for x in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        fx = float(x)
        fy = float(y)
        dot += fx * fy
        na += fx * fx
        nb += fy * fy
    denom = math.sqrt(na) * math.sqrt(nb)
    if denom <= 1e-12:
        return 0.0
    return dot / denom


def ema_step(
    current: Sequence[float] | None,
    target: Sequence[float],
    *,
    alpha: float,
    sign: float,
) -> list[float]:
    """sign=+1 лайк (тянем к target), sign=-1 дизлайк (отталкиваем)."""
    t = l2_normalize(target)
    if sign < 0:
        t = [-x for x in t]
    a = max(0.0, min(1.0, alpha))
    if current is None:
        return t if a >= 0.5 else l2_normalize([a * x for x in t])
    out = [(1.0 - a) * float(c) + a * x for c, x in zip(current, t, strict=True)]
    return l2_normalize(out)


def min_max_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo + 1e-12:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]
