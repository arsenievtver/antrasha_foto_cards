"""Приходы по размерам: оприходования (+ редкие приёмки) и списания → data/arrivals.json, data/losses.json."""

from __future__ import annotations

import json
import sys

from ms_common import base_name, size_of
from ms_mcp import HERE, MsMcp

DATA = HERE / "data"
DATE_FROM = sys.argv[1] if len(sys.argv) > 1 else "2024-07-01"
DATE_TO = sys.argv[2] if len(sys.argv) > 2 else "2026-10-26"

m = MsMcp()


def doc_lines(tool: str, kind: str) -> list[dict]:
    docs = m.call_all(
        tool,
        {"momentFrom": DATE_FROM, "momentTo": DATE_TO, "expand": "positions.assortment", "sortBy": "moment", "sortOrder": "asc"},
        page=20,
    )
    rows = []
    truncated = 0
    for d in docs:
        if not d.get("applicable", True):
            continue
        pos = d.get("positions") or []
        total = sum((p.get("quantity") or 0) * (p.get("price") or 0) / 100 for p in pos)
        if d.get("sum") and abs(total - d["sum"]) > 1:
            truncated += 1
        for p in pos:
            ass = p.get("assortment") or {}
            rows.append(
                {
                    "doc": d.get("name"),
                    "kind": kind,
                    "moment": d["moment"],
                    "variant_id": ass.get("id"),
                    "variant_name": ass.get("name"),
                    "base_name": base_name(ass.get("name") or ""),
                    "size": size_of(ass.get("name"), ass.get("characteristics")),
                    "qty": p.get("quantity") or 0,
                    "cost": (p.get("price") or 0) / 100,
                }
            )
    print(tool, "docs", len(docs), "lines", len(rows), "sum mismatch docs", truncated, file=sys.stderr)
    return rows


arrivals = doc_lines("enter_list", "enter") + doc_lines("supply_list", "supply")
(DATA / "arrivals.json").write_text(json.dumps(arrivals, ensure_ascii=False))
losses = doc_lines("loss_list", "loss")
(DATA / "losses.json").write_text(json.dumps(losses, ensure_ascii=False))
