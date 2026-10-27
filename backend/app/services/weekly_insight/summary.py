"""Текст недельного отчёта: сжатые метрики → Anthropic → markdown; без ключа — по правилам."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import Settings

log = logging.getLogger("app.weekly_insight.summary")

SYSTEM_PROMPT = """Ты аналитик мультибрендового бутика одежды «Антраша» (Тверь, 20 лет, европейский сдержанный стиль, средняя вещь ~20 тыс ₽).
Тебе дают недельные метрики из МойСклад в JSON. Суммы в рублях, *_pct — проценты.
Скидка до 20% — цена по карте лояльности, выше — уценка. st90/st180 — доля проданных штук за 90/180 дней от прихода.

Правила бизнеса:
- Публичная распродажа старого стока не работает: она съедает маржу и приучает клиентов A ждать скидок. Старый товар — в личные подборки клиентам с подходящим размером и брендом.
- Главный риск — уход клиентов A. Список «на контроле» отдаётся продавцам на обзвон.
- Закупку планировать от продаж (себестоимости) и размерной сетки, а не от прошлого заказа.

Напиши отчёт на русском в markdown ровно с разделами:
## В общем
## За неделю
## Динамика
## Предложения

В «В общем» — 12 месяцев к прошлым 12: выручка, закупка против себестоимости, склад и запас в месяцах, клиенты A.
В «За неделю» — выручка к прошлой неделе и к той же неделе год назад, скидки и уценка, новые покупатели и клиенты A, вернувшиеся из прошлого списка, приход.
В «Динамике» — тренд 13 недель одним-двумя абзацами, без таблицы.
В «Предложениях» — 4–7 конкретных действий на эту неделю с цифрами и названиями (бренды, модели, размеры). Каждое — что сделать и почему.

Пиши коротко, полными предложениями, без воды и без повторения JSON. Не выдумывай цифр, которых нет во входных данных. До 450 слов."""


def compact_metrics(metrics: dict) -> dict:
    """Урезанные метрики для модели и MCP: верх списков без длинных хвостов."""
    asm = metrics.get("assortment") or {}
    keep = ("model", "brand", "gender", "category", "season", "sold_out_sizes", "received", "st_to_date_pct", "st180_pct", "stock_cost", "revenue")
    sizes = [r for r in asm.get("size_curve") or [] if r.get("verdict")]
    return {
        "run_day": metrics.get("run_day"),
        "week": metrics.get("week"),
        "dynamics": metrics.get("dynamics"),
        "overall": metrics.get("overall"),
        "clients": metrics.get("clients"),
        "assortment": {
            "seasons": asm.get("seasons"),
            "mature_seasons": asm.get("mature_seasons"),
            "categories": (asm.get("categories") or [])[:14],
            "brands": (asm.get("brands") or [])[:25],
            "size_flags": sizes[:30],
            "depth": asm.get("depth"),
            "dead": {
                "models": (asm.get("dead") or {}).get("models"),
                "stock_cost": (asm.get("dead") or {}).get("stock_cost"),
                "top": [{k: r.get(k) for k in keep} for r in ((asm.get("dead") or {}).get("top") or [])[:10]],
            },
            "reorder_candidates": [{k: r.get(k) for k in keep} for r in (asm.get("reorder_candidates") or [])[:12]],
        },
        "staff_feedback": metrics.get("staff_feedback"),
        "rule_suggestions": metrics.get("suggestions"),
    }


def ai_configured(settings: Settings) -> bool:
    return bool(settings.anthropic_api_key and str(settings.anthropic_api_key).strip())


def _money(x: Any) -> str:
    try:
        return f"{float(x) / 1e6:.2f} млн ₽"
    except (TypeError, ValueError):
        return "—"


def _pct_change(cur: Any, prev: Any) -> str:
    try:
        return f"{(float(cur) / float(prev) - 1) * 100:+.0f}%"
    except (TypeError, ValueError, ZeroDivisionError):
        return "—"


def rule_summary(metrics: dict) -> str:
    o, w, cl = metrics["overall"], metrics["week"], metrics["clients"]
    ws, prev, ly = w["sales"], w["prev_week"], w["same_week_last_year"]
    seg_a = cl["segments"]["A"]
    dyn = metrics.get("dynamics") or []
    last4 = sum(d["revenue"] or 0 for d in dyn[-4:])
    prev4 = sum(d["revenue"] or 0 for d in dyn[-8:-4])
    lines = [
        "## В общем",
        f"Выручка по чекам за 12 мес — {_money(o['sales_cur']['revenue'])} ({_pct_change(o['sales_cur']['revenue'], o['sales_prev']['revenue'])} к прошлым 12). "
        f"Закуплено на {_money(o['bought_cost_cur'])} при себестоимости продаж {_money(o['cogs_cur'])}. "
        f"Склад {_money(o['stock_cost_now'])} по себестоимости — {o['months_of_stock'] or '—'} мес продаж. "
        f"Клиенты A: {seg_a['clients']}, выручка {_money(seg_a['rev_cur12'])} против {_money(seg_a['rev_prev12'])}.",
        "",
        "## За неделю",
        f"{w['period']['from']} – {w['period']['to']}: {_money(ws['revenue'])}, {ws['checks']} чеков, средний чек {ws['avg_check'] or '—'} ₽ "
        f"({_pct_change(ws['revenue'], prev['revenue'])} к прошлой неделе, {_pct_change(ws['revenue'], ly['revenue'])} к году назад). "
        f"Средняя скидка {ws['avg_discount_pct'] or 0}%, с уценкой {ws['markdown_units_pct'] or 0}% штук. "
        f"Покупателей с картой {w['buyers_named']}, новых {w['buyers_new']}, клиентов A {w['buyers_a']}. "
        f"Приход: {w['arrivals']['units']} шт на {_money(w['arrivals']['cost'])}.",
        "",
        "## Динамика",
        f"Последние 4 недели — {_money(last4)}, предыдущие 4 — {_money(prev4)} ({_pct_change(last4, prev4)}).",
        "",
        "## Предложения",
    ]
    lines += [f"- {s}" for s in metrics.get("suggestions") or []]
    return "\n".join(lines)


def generate_summary(settings: Settings, metrics: dict) -> tuple[str, str | None, dict[str, int]]:
    """→ (markdown, модель или None, usage)."""
    if not ai_configured(settings):
        return rule_summary(metrics), None, {}
    from app.services.warehouse_analytics.orchestrator import _anthropic_raw

    model = (settings.warehouse_ai_writer_model or settings.anthropic_model or "claude-sonnet-4-6").strip()
    payload = {
        "model": model,
        "max_tokens": 2500,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": json.dumps(compact_metrics(metrics), ensure_ascii=False, separators=(",", ":"))}
        ],
    }
    try:
        data = _anthropic_raw(settings, model=model, payload=payload)
    except Exception as e:  # noqa: BLE001
        log.warning("weekly_insight summary: Anthropic failed, rule fallback: %s", e)
        return rule_summary(metrics), None, {}
    content = data.get("content") if isinstance(data.get("content"), list) else []
    text = "\n\n".join(
        str(b.get("text") or "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    ).strip()
    usage = {k: int(v) for k, v in (data.get("usage") or {}).items() if k in ("input_tokens", "output_tokens") and isinstance(v, int)}
    if not text:
        return rule_summary(metrics), None, usage
    return text, model, usage
