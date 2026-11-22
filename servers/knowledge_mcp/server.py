"""knowledge-mcp: retrieval over table docs, metric definitions and known issues.

Trust boundary: this server only reads the RAG index (schema `knowledge`) as
the `knowledge_reader` role. It cannot see warehouse data.
"""

from __future__ import annotations

import argparse
from typing import Any

import numpy as np
import psycopg
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pgvector.psycopg import register_vector
from pydantic import BaseModel, Field

from common.embeddings import embed_query
from common.settings import get_settings

SOURCE_TYPES = ("table", "metric", "issue", "glossary")

mcp = FastMCP(
    name="knowledge",
    instructions=(
        "Search the analytics knowledge base: table documentation, governed metric "
        "definitions (gross_revenue, net_revenue, active_customers, ...), known data "
        "issues and glossaries. Search before writing SQL so definitions are correct, "
        "and cite chunk_id values in answers. Prefer governed metrics over glossary "
        "definitions; ignore documents marked OUTDATED or DEPRECATED."
    ),
)

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
             "openWorldHint": False}


class Document(BaseModel):
    chunk_id: str
    source_type: str
    title: str
    content: str
    source_path: str
    table_names: list[str]
    metadata: dict[str, Any]
    score: float | None = Field(default=None, description="Cosine similarity, 0-1")


def _connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().knowledge_dsn, connect_timeout=5)
    register_vector(conn)
    return conn


COLS = "chunk_id, source_type, title, content, source_path, table_names, metadata"


def _doc(row: tuple, score: float | None = None) -> Document:
    cid, st, title, content, path, tables, meta = row[:7]
    return Document(chunk_id=cid, source_type=st, title=title, content=content,
                    source_path=path, table_names=list(tables), metadata=meta, score=score)


def search(query: str, k: int = 5, source_types: list[str] | None = None) -> list[Document]:
    """Vector search (callable directly by evals, wrapped as an MCP tool below)."""
    k = max(1, min(k, 20))
    types = list(source_types or SOURCE_TYPES)
    bad = set(types) - set(SOURCE_TYPES)
    if bad:
        raise ToolError(f"Unknown source_types {sorted(bad)}; use {list(SOURCE_TYPES)}.")

    vec = np.array(embed_query(query), dtype=np.float32)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT {COLS}, 1 - (embedding <=> %s) AS score
            FROM knowledge.chunks
            WHERE source_type = ANY(%s)
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (vec, types, vec, k),
        ).fetchall()
    return [_doc(r, round(float(r[7]), 4)) for r in rows]


@mcp.tool(annotations=READ_ONLY)
def search_knowledge(
    query: str, k: int = 5, source_types: list[str] | None = None
) -> list[Document]:
    """Semantic search over the knowledge base. Returns the k most relevant chunks.

    source_types filters by kind: table, metric, issue, glossary (default: all).
    """
    return search(query, k, source_types)


@mcp.tool(annotations=READ_ONLY)
def get_documents(chunk_ids: list[str]) -> list[Document]:
    """Fetch chunks by id, e.g. ['table:analytics.orders', 'metric:net_revenue']."""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT {COLS} FROM knowledge.chunks WHERE chunk_id = ANY(%s) ORDER BY chunk_id",
            (chunk_ids,),
        ).fetchall()
    return [_doc(r) for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="knowledge-mcp server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    embed_query("warmup")  # load the embedding model before the first request
    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port, show_banner=False)
    else:
        mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
