"""Execution accuracy: does the predicted result set equal the gold result set?

Rules (documented in README > Evaluation):
- Row order is ignored (multiset comparison).
- Numbers are compared after rounding to 4 decimals; int 5 == float 5.0.
- Dates and midnight timestamps compare equal ('2024-01-01' == '2024-01-01T00:00:00').
- Extra predicted columns are allowed if a subset of them matches the gold
  columns exactly (e.g. returning region_id AND region name is fine).
- Row count must match exactly.
"""

from __future__ import annotations

import itertools
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Any

MAX_COMBINATIONS = 5000


def normalize(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float, Decimal)):
        return round(float(v), 4) + 0.0
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == datetime.min.time() else v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, str):
        s = v.strip()
        if len(s) >= 19 and s[10] == "T" and s[11:19] == "00:00:00" and s[19:] in ("", "+00:00"):
            return s[:10]
        try:
            return round(float(s), 4) + 0.0 if s and s[0] in "-0123456789" else s
        except ValueError:
            return s
    return v


def _norm_rows(rows: list[list[Any]]) -> list[tuple]:
    return [tuple(normalize(v) for v in r) for r in rows]


def _col_key(rows: list[tuple], j: int) -> Counter:
    return Counter(r[j] for r in rows)


def results_match(gold: list[list[Any]], pred: list[list[Any]]) -> bool:
    g, p = _norm_rows(gold), _norm_rows(pred)
    if len(g) != len(p):
        return False
    if not g:
        return True
    g_width, p_width = len(g[0]), len(p[0]) if p else 0
    if p_width < g_width:
        return False
    target = Counter(g)

    # For each gold column, the (predicted column, transform) pairs that produce
    # the same value distribution.
    candidates = []
    for j in range(g_width):
        key = _col_key(g, j)
        cands = [
            (k, name)
            for k in range(p_width)
            for name, fn in TRANSFORMS.items()
            if Counter(fn(r[k]) for r in p) == key
        ]
        if not cands:
            return False
        candidates.append(cands)

    for n, combo in enumerate(itertools.product(*candidates)):
        if n >= MAX_COMBINATIONS:
            break
        cols = [k for k, _ in combo]
        if len(set(cols)) != len(cols):
            continue
        projected = Counter(tuple(TRANSFORMS[t](r[k]) for k, t in combo) for r in p)
        if projected == target:
            return True
    return False


def _date_part(part: str):
    """Map an ISO date string to its year, quarter or month number (as normalized float)."""

    def fn(v: Any) -> Any:
        if not (isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-"):
            return _NO_MATCH
        y, m = int(v[:4]), int(v[5:7])
        return float({"year": y, "quarter": (m - 1) // 3 + 1, "month": m}[part])

    return fn


_NO_MATCH = object()

# A gold period number (2023, quarter 3, month 7) may match a predicted date
# label for the same period. Only date -> number transforms are allowed:
# general label remapping could accept answers with swapped labels.
TRANSFORMS = {
    "identity": lambda v: v,
    "year": _date_part("year"),
    "quarter": _date_part("quarter"),
    "month": _date_part("month"),
}
