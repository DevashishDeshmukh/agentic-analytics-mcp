"""Regenerate the README results table from evals/results/*.json.

The table lives between <!-- RESULTS:START --> and <!-- RESULTS:END --> in README.md.
Numbers in the README are never typed by hand.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
START, END = "<!-- RESULTS:START -->", "<!-- RESULTS:END -->"
CONFIG_ORDER = ["baseline", "rag", "bm25", "hybrid", "hybrid_rerank"]


def fmt_pct(v):
    return "—" if v is None else f"{v * 100:.1f}%"


def fmt(v, spec):
    return "—" if v is None else format(v, spec)


def build_table() -> str:
    rows = []
    for p in sorted((ROOT / "evals" / "results").glob("*.json")):
        rows.append(json.loads(p.read_text()))
    if not rows:
        return "_No eval results yet. Run `make eval CONFIG=baseline` and `make eval CONFIG=rag`._"

    def key(r):
        c = r["config"]
        return (r["version"], CONFIG_ORDER.index(c) if c in CONFIG_ORDER else 99, c)

    lines = [
        ("| Version | Config | Model | Questions | Exec accuracy | Table recall@5 "
        "| p50 (s) | p95 (s) | $ / success |"),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=key):
        lines.append(
            f"| {r['version']} | {r['config']} | {r['model']} | {r['questions']} "
            f"| {fmt_pct(r['exec_accuracy'])} | {fmt(r.get('recall_at_5'), '.2f')} "
            f"| {fmt(r['latency_p50_s'], '.1f')} | {fmt(r['latency_p95_s'], '.1f')} "
            f"| {fmt(r['cost_per_success_usd'], '.4f')} |"
        )

    cats = sorted({c for r in rows for c in r["by_category"]})
    lines += ["", "Accuracy by category:", "",
              "| Version | Config | " + " | ".join(cats) + " |",
              "|---|---|" + "---|" * len(cats)]
    for r in sorted(rows, key=key):
        vals = " | ".join(fmt_pct(r["by_category"].get(c)) for c in cats)
        lines.append(f"| {r['version']} | {r['config']} | {vals} |")
    return "\n".join(lines)


def main() -> None:
    readme = ROOT / "README.md"
    text = readme.read_text()
    if START not in text or END not in text:
        raise SystemExit("README.md is missing the RESULTS markers.")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    readme.write_text(f"{head}{START}\n{build_table()}\n{END}{tail}")
    print("README results table updated.")


if __name__ == "__main__":
    main()
