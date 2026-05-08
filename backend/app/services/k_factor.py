def k_factor(view_time_ms: int | None) -> float:
    """Swipe speed → multiplier (ТЗ: быстрый 0.3, норма 1, задержка 1.5)."""
    if view_time_ms is None:
        return 1.0
    if view_time_ms < 500:
        return 0.3
    if view_time_ms > 3000:
        return 1.5
    return 1.0
