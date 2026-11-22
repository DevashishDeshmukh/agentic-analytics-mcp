"""CLI: uv run python -m agent "What was net revenue in 2024?" [--config baseline] [--json]"""

from __future__ import annotations

import argparse
import asyncio
import json

from agent.config import load_features
from agent.loop import AnalyticsAgent


def render(a) -> str:
    lines = [f"Q: {a.question}  [{a.config}]", ""]
    if a.error:
        lines += [f"ERROR: {a.error}", ""]
    if a.answer:
        lines += [a.answer, ""]
    if a.sql:
        lines += ["SQL:", a.sql, ""]
    if a.columns:
        lines.append(" | ".join(a.columns))
        lines += [" | ".join(str(v) for v in r) for r in a.rows[:15]]
        if a.row_count > 15 or a.truncated:
            lines.append(f"... {a.row_count} rows{' (truncated)' if a.truncated else ''}")
        lines.append("")
    if a.citations:
        lines.append("Sources: " + ", ".join(a.citations))
    if a.caveats:
        lines += ["Caveats:"] + [f"- {c}" for c in a.caveats]
    u = a.usage
    cost = f"${u['cost_usd']:.4f}" if u["cost_usd"] is not None else "cost n/a"
    lines.append(f"\n{a.timings_ms.get('total', 0)} ms | {u['input_tokens']}+{u['output_tokens']} "
                 f"tokens | {cost} | {u['model']}")
    return "\n".join(lines)


async def run(question: str, config: str | None, as_json: bool) -> None:
    async with AnalyticsAgent(load_features(config)) as agent:
        a = await agent.ask(question)
    print(json.dumps(a.to_dict(), indent=2, default=str) if as_json else render(a))


def main() -> None:
    p = argparse.ArgumentParser(description="Ask the analytics agent a question")
    p.add_argument("question")
    p.add_argument("--config", help="feature config from config/features.yaml")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    asyncio.run(run(args.question, args.config, args.json))


main()
