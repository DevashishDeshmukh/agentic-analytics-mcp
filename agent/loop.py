"""Agent orchestration: retrieve -> generate SQL -> execute -> answer.

A small explicit loop instead of a framework: each step is visible in the
trace, testable on its own and switchable by feature flag for ablations.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Self

from fastmcp import Client
from openai import APIError

from agent.config import Features, load_features, load_mcp_config
from agent.llm import Usage, chat_json
from common.settings import get_settings

PROMPTS = get_settings().root / "agent" / "prompts"
ANSWER_ROWS = 50


@dataclass
class AgentAnswer:
    question: str
    config: str
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    truncated: bool = False
    answer: str | None = None
    citations: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    retrieved: list[dict[str, Any]] = field(default_factory=list)
    tables_in_context: list[str] = field(default_factory=list)
    tables_used: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    error: str | None = None
    timings_ms: dict[str, int] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unwrap(structured: Any) -> Any:
    if isinstance(structured, dict) and set(structured) == {"result"}:
        return structured["result"]
    return structured


class AnalyticsAgent:
    """Use as an async context manager so MCP connections are reused across questions."""

    def __init__(self, features: Features | None = None):
        self.features = features or load_features()
        self.client = Client(load_mcp_config())
        self._schema_cache: dict[str, str] = {}
        self._all_tables: list[str] | None = None

    async def __aenter__(self) -> Self:
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.client.__aexit__(*exc)

    async def _tool(self, server: str, tool: str, args: dict[str, Any]) -> Any:
        result = await self.client.call_tool(f"{server}_{tool}", args, raise_on_error=False)
        if result.is_error:
            text = result.content[0].text if result.content else "unknown tool error"
            raise ToolCallError(text)
        return _unwrap(result.structured_content)

    async def _schema(self, table: str) -> str:
        if table not in self._schema_cache:
            t = await self._tool("warehouse", "describe_table", {"table": table})
            cols = ", ".join(f"{c['name']} {c['type']}" for c in t["columns"])
            self._schema_cache[table] = f"{t['table']}({cols})"
        return self._schema_cache[table]

    async def _tables(self) -> list[str]:
        if self._all_tables is None:
            rows = await self._tool("warehouse", "list_tables", {"schema": "analytics"})
            self._all_tables = [r["table"] for r in rows]
        return self._all_tables

    async def build_context(self, question: str, out: AgentAnswer) -> str:
        parts: list[str] = []
        if self.features.rag:
            docs = await self._tool(
                "knowledge", "search_knowledge", {"query": question, "k": self.features.k}
            )
            out.retrieved = [
                {"chunk_id": d["chunk_id"], "score": d["score"], "table_names": d["table_names"]}
                for d in docs
            ]
            parts.append("DOCUMENTS:")
            for d in docs:
                parts.append(f"[{d['chunk_id']}] ({d['source_type']}) {d['title']}\n{d['content']}")
            known = set(await self._tables())
            tables = sorted({t for d in docs for t in d["table_names"] if t in known})
        else:
            tables = await self._tables()
        out.tables_in_context = tables
        parts.append("SCHEMA:")
        parts += [await self._schema(t) for t in tables]
        return "\n\n".join(parts)

    async def ask(self, question: str, answer: bool = True) -> AgentAnswer:
        out = AgentAnswer(question=question, config=self.features.name)
        usage = Usage()
        t_start = time.perf_counter()

        def mark(step: str, t0: float) -> None:
            out.timings_ms[step] = int((time.perf_counter() - t0) * 1000)

        try:
            t0 = time.perf_counter()
            context = await self.build_context(question, out)
            mark("retrieve", t0)

            t0 = time.perf_counter()
            gen = chat_json(
                (PROMPTS / "generate_sql.md").read_text(),
                f"CONTEXT:\n{context}\n\nQUESTION: {question}",
                usage, "generate_sql",
            )
            mark("generate_sql", t0)
            out.sql = gen.get("sql")
            out.tables_used = gen.get("tables_used", [])
            out.assumptions = gen.get("assumptions", [])
            if not out.sql:
                raise ToolCallError(gen.get("error", "model returned no SQL"))

            t0 = time.perf_counter()
            res = await self._tool("warehouse", "run_query", {"sql": out.sql, "max_rows": 1000})
            mark("execute", t0)
            out.columns, out.rows = res["columns"], res["rows"]
            out.row_count, out.truncated = res["row_count"], res["truncated"]

            if answer:
                t0 = time.perf_counter()
                preview = {"columns": out.columns, "rows": out.rows[:ANSWER_ROWS],
                           "row_count": out.row_count, "truncated": out.truncated}
                ans = chat_json(
                    (PROMPTS / "answer.md").read_text(),
                    f"CONTEXT:\n{context}\n\nQUESTION: {question}\n\nSQL:\n{out.sql}\n\n"
                    f"RESULT:\n{preview}",
                    usage, "answer",
                )
                mark("answer", t0)
                out.answer = ans.get("answer")
                out.citations = ans.get("citations", [])
                out.caveats = ans.get("caveats", [])
        except ToolCallError as e:
            out.error = str(e)
        except APIError as e:
            # Provider failure after retries (rate limit, 503): record it, don't crash the run.
            out.error = f"LLM API error: {type(e).__name__}: {str(e)[:200]}"

        out.timings_ms["total"] = int((time.perf_counter() - t_start) * 1000)
        s = get_settings()
        out.usage = {"provider": s.llm_provider, "model": s.llm_model,
                     "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                     "llm_calls": usage.calls, "cost_usd": usage.cost_usd(),
                     "by_step": usage.by_step}
        return out


class ToolCallError(RuntimeError):
    pass
