"""Run the eval suite.

    uv run python -m evals.runners.run_eval --config rag
    uv run python -m evals.runners.run_eval --config baseline
    uv run python -m evals.runners.run_eval --check-gold     # no LLM: verify gold SQL runs

Writes:
    evals/results/<version>-<config>-<model>.json    summary (committed, feeds README table)
    evals/results/<version>-<config>-<model>.jsonl  per-question detail (gitignored)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import yaml

from agent.config import load_features
from agent.loop import AnalyticsAgent
from common.settings import get_settings
from evals.metrics.compare import results_match
from evals.metrics.retrieval import table_recall_at_k

VERSION = "v0.1"
RECALL_K = 5


def load_questions(path: Path, only: list[str] | None) -> list[dict]:
    qs = yaml.safe_load(path.read_text())
    return [q for q in qs if not only or q["id"] in only]


def run_gold(conn: psycopg.Connection, sql: str) -> list[list]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return [list(r) for r in cur.fetchall()]


def check_gold(questions: list[dict]) -> int:
    failures = 0
    with psycopg.connect(get_settings().warehouse_dsn, autocommit=True) as conn:
        for q in questions:
            try:
                rows = run_gold(conn, q["gold_sql"])
                print(f"  ok   {q['id']}  {len(rows):>4} rows  {str(rows[:2])[:70]}")
            except psycopg.Error as e:
                conn.rollback()
                failures += 1
                print(f"  FAIL {q['id']}  {e}")
    print(f"{len(questions) - failures}/{len(questions)} gold queries ran")
    return failures


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", s.lower()).strip("-")


def pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(p * (len(xs) - 1)))]


async def evaluate(
    questions: list[dict], config: str, with_answer: bool, partial: bool = False
) -> dict:
    s = get_settings()
    features = load_features(config)
    out_dir = s.root / "evals" / "results"
    run_name = f"{VERSION}-{features.name}-{slug(s.llm_model)}"
    if partial:  # --only runs never overwrite the full results that feed the README
        out_dir = out_dir / "partial"
        out_dir.mkdir(exist_ok=True)
    detail_path = out_dir / f"{run_name}.jsonl"
    details = []

    with psycopg.connect(s.warehouse_dsn, autocommit=True) as gold_conn:
        async with AnalyticsAgent(features) as agent:
            for i, q in enumerate(questions, 1):
                gold = run_gold(gold_conn, q["gold_sql"])
                a = await agent.ask(q["question"], answer=with_answer)
                correct = a.error is None and not a.truncated and results_match(gold, a.rows)
                recall = (table_recall_at_k(a.retrieved, q["expected_tables"], RECALL_K)
                          if features.rag else None)
                rec = {
                    "id": q["id"], "category": q["category"], "correct": correct,
                    "recall_at_k": recall, "error": a.error, "gold_rows": len(gold),
                    "pred_rows": a.row_count, **a.to_dict(),
                }
                rec["rows"] = a.rows[:20]
                details.append(rec)
                mark = "PASS" if correct else "FAIL"
                print(f"[{i:>2}/{len(questions)}] {mark} {q['id']} {q['category']:<11} "
                      f"{a.timings_ms.get('total', 0):>6} ms"
                      + (f"  recall@{RECALL_K}={recall:.2f}" if recall is not None else "")
                      + (f"  error: {a.error[:80]}" if a.error else ""), flush=True)

    with detail_path.open("w") as f:
        for d in details:
            f.write(json.dumps(d, default=str) + "\n")

    n = len(details)
    by_cat: dict[str, list[bool]] = defaultdict(list)
    for d in details:
        by_cat[d["category"]].append(d["correct"])
    latencies = [d["timings_ms"]["total"] / 1000 for d in details]
    raw_costs = [d["usage"]["cost_usd"] for d in details]
    known_cost = all(c is not None for c in raw_costs)
    costs = [c or 0 for c in raw_costs]
    n_correct = sum(d["correct"] for d in details)
    recalls = [d["recall_at_k"] for d in details if d["recall_at_k"] is not None]

    summary = {
        "version": VERSION,
        "config": features.name,
        "features": features.__dict__,
        "provider": s.llm_provider,
        "model": s.llm_model,
        "questions": n,
        "exec_accuracy": round(n_correct / n, 4) if n else 0,
        "by_category": {c: round(sum(v) / len(v), 4) for c, v in sorted(by_cat.items())},
        f"recall_at_{RECALL_K}": round(statistics.mean(recalls), 4) if recalls else None,
        "errors": sum(1 for d in details if d["error"]),
        "latency_p50_s": round(pct(latencies, 0.5), 2),
        "latency_p95_s": round(pct(latencies, 0.95), 2),
        "cost_total_usd": round(sum(costs), 4) if known_cost else None,
        "cost_per_success_usd": (
            round(sum(costs) / n_correct, 5) if n_correct and known_cost else None
        ),
        "with_answer_step": with_answer,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    (out_dir / f"{run_name}.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config")
    p.add_argument("--questions", default="evals/questions/v0_1.yaml")
    p.add_argument("--only", nargs="*", help="question ids to run")
    p.add_argument("--answer", action="store_true", help="also run the answer step")
    p.add_argument("--check-gold", action="store_true")
    args = p.parse_args()

    questions = load_questions(get_settings().root / args.questions, args.only)
    if args.check_gold:
        sys.exit(1 if check_gold(questions) else 0)

    t0 = time.time()
    summary = asyncio.run(
        evaluate(questions, args.config, args.answer, partial=bool(args.only))
    )
    print(json.dumps(summary, indent=2))
    print(f"Finished in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
