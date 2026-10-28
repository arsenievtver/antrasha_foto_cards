"""Итерация 6: что стало с клиентами A каждого статуса через год (база без вмешательства)."""
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
exec(open(Path(__file__).parent / "validate_weekly.py").read().split("t = time.time()")[0])
from app.services.weekly_insight.compute import CARD_DISCOUNT_MAX, _is_named, _prepare_lines  # noqa: E402

lines = [l for l in _prepare_lines(ds) if _is_named(l)]
T0 = date(2025, 10, 25)
H_FROM = date(2024, 7, 1)
OUT_TO = date(2026, 10, 25)

hist = defaultdict(list)
future = defaultdict(list)
for l in lines:
    (hist if H_FROM <= l["_day"] <= T0 else future if T0 < l["_day"] <= OUT_TO else {}).setdefault(l["agent_id"], []).append(l) if False else None
for l in lines:
    if H_FROM <= l["_day"] <= T0:
        hist[l["agent_id"]].append(l)
    elif T0 < l["_day"] <= OUT_TO:
        future[l["agent_id"]].append(l)

rev = {c: sum(l["sum"] for l in ls) for c, ls in hist.items()}
ranked = sorted(rev, key=lambda c: -rev[c])
n_a = round(len(ranked) * 0.2)
A = ranked[:n_a]


def status(ls):
    days = sorted({l["_day"] for l in ls})
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    since = (T0 - days[-1]).days
    if since > 365:
        return "ушёл (>12 мес)"
    if not gaps:
        return "одна покупка"
    g = statistics.median(gaps)
    if since > max(1.5 * g, 90):
        return "просрочил визит"
    half = T0 - timedelta(days=(T0 - H_FROM).days // 2)
    r1 = sum(l["sum"] for l in ls if l["_day"] <= half)
    r2 = sum(l["sum"] for l in ls if l["_day"] > half)
    if r1 > 0 and r2 < 0.5 * r1:
        return "покупает меньше"
    return "в ритме"


groups = defaultdict(list)
for c in A:
    groups[status(hist[c])].append(c)

print(f"A на {T0}: {len(A)} клиентов, история с {H_FROM}")
print(f"{'статус':18} {'клиентов':>8} {'выр. до':>9} {'вернулись':>9} {'выр. после':>10} {'на клиента':>10} {'уценка%':>7}")
for st, cs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
    before = sum(rev[c] for c in cs) / (T0 - H_FROM).days * 365
    back = [c for c in cs if future.get(c)]
    after = sum(sum(l["sum"] for l in future[c]) for c in back)
    units = sum(l["qty"] for c in back for l in future[c])
    md = sum(l["qty"] for c in back for l in future[c] if l["discount_pct"] > CARD_DISCOUNT_MAX)
    print(f"{st:18} {len(cs):8} {before/1e6:8.2f}м {len(back):4} ({len(back)/len(cs)*100:3.0f}%) {after/1e6:9.2f}м {after/len(cs)/1e3:9.0f}т {md/max(1,units)*100:6.0f}")

# Откуда берутся новые A: кем были A-2026 в окне до T0
rev26 = defaultdict(float)
for c, ls in future.items():
    rev26[c] = sum(l["sum"] for l in ls)
r26 = sorted(rev26, key=lambda c: -rev26[c])
A26 = r26[: round(len(r26) * 0.2)]
src = defaultdict(lambda: [0, 0.0])
Aset = set(A)
for c in A26:
    k = "был A" if c in Aset else ("был покупателем не A" if c in hist else "новый (не покупал с 07.2024)")
    src[k][0] += 1
    src[k][1] += rev26[c]
print("\nA за 26.10.2025–25.10.2026:", len(A26))
for k, (n, r) in src.items():
    print(f"  {k:30} {n:4} клиентов, {r/1e6:.2f} млн")

# Новые покупатели: сколько из них становятся повторными
first = {}
for l in lines:
    first[l["agent_id"]] = min(first.get(l["agent_id"], l["_day"]), l["_day"])
cohort = [c for c, d in first.items() if date(2025, 1, 1) <= d <= date(2025, 10, 25)]
repeat = [c for c in cohort if len({l["_day"] for l in lines if l["agent_id"] == c}) >= 2]
print(f"\nПервая покупка 01.01–25.10.2025 (с 07.2024 не покупали): {len(cohort)}, вернулись повторно: {len(repeat)} ({len(repeat)/max(1,len(cohort))*100:.0f}%)")
print(f"  из них стали A в 2026: {sum(1 for c in cohort if c in set(A26))}")
