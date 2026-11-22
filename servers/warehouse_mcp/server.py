"""warehouse-mcp: read-only access to the analytics warehouse.

Trust boundary: this server touches sensitive data. It connects as the
`agent_readonly` Postgres role, which can only SELECT, runs every transaction
read-only and kills queries after 10s.
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import psycopg
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from common.settings import get_settings
from servers.warehouse_mcp.sql import MultipleStatementsError, prepare_query

MAX_ROWS_CAP = 1000

mcp = FastMCP(
    name="warehouse",
    instructions=(
        "Read-only access to the analytics Postgres warehouse (schema `analytics`). "
        "Use list_tables and describe_table to discover structure, then run_query with "
        "a single SELECT. Writes are rejected by the database. Business definitions "
        "(revenue, active customers, etc.) live in the knowledge server, not here."
    ),
)

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True,
             "openWorldHint": False}


class TableInfo(BaseModel):
    table: str
    row_estimate: int


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool


class TableSchema(BaseModel):
    table: str
    columns: list[ColumnInfo]


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int = Field(description="Rows returned (after truncation)")
    truncated: bool = Field(description="True if more rows existed than max_rows")
    sql_executed: str
    elapsed_ms: int


def _connect() -> psycopg.Connection:
    return psycopg.connect(get_settings().warehouse_dsn, connect_timeout=5)


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _split_table(table: str) -> tuple[str, str]:
    schema, _, name = table.rpartition(".")
    return (schema or "analytics"), name


@mcp.tool(annotations=READ_ONLY)
def list_tables(schema: str = "analytics") -> list[TableInfo]:
    """List tables in a warehouse schema with approximate row counts."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT n.nspname || '.' || c.relname, GREATEST(c.reltuples, 0)::bigint
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname = %s
              AND has_table_privilege(c.oid, 'SELECT')
            ORDER BY 1
            """,
            (schema,),
        ).fetchall()
    return [TableInfo(table=t, row_estimate=n) for t, n in rows]


@mcp.tool(annotations=READ_ONLY)
def describe_table(table: str) -> TableSchema:
    """Column names, types and nullability for a table, e.g. 'analytics.orders'."""
    schema, name = _split_table(table)
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT column_name, data_type, is_nullable = 'YES'
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, name),
        ).fetchall()
    if not rows:
        raise ToolError(f"Table {schema}.{name} not found or not accessible.")
    return TableSchema(
        table=f"{schema}.{name}",
        columns=[ColumnInfo(name=c, type=t, nullable=n) for c, t, n in rows],
    )


@mcp.tool(annotations=READ_ONLY)
def run_query(sql: str, max_rows: int = 200) -> QueryResult:
    """Run ONE read-only SQL query against the warehouse and return rows.

    A LIMIT is applied automatically. Use fully qualified names (analytics.orders).
    """
    max_rows = max(1, min(max_rows, MAX_ROWS_CAP))
    try:
        prepared = prepare_query(sql, max_rows)
    except MultipleStatementsError as e:
        raise ToolError(str(e)) from e

    t0 = time.perf_counter()
    try:
        with _connect() as conn, conn.cursor() as cur:
            cur.execute(prepared)
            if cur.description is None:
                raise ToolError("Statement returned no rows. Only SELECT queries are supported.")
            columns = [d.name for d in cur.description]
            fetched = cur.fetchall()
    except psycopg.Error as e:
        msg = (e.diag.message_primary if e.diag and e.diag.message_primary else str(e)).strip()
        hint = f" Hint: {e.diag.message_hint}" if e.diag and e.diag.message_hint else ""
        raise ToolError(f"Database error: {msg}.{hint}") from e

    truncated = len(fetched) > max_rows
    rows = [[_jsonable(v) for v in r] for r in fetched[:max_rows]]
    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        sql_executed=prepared,
        elapsed_ms=int((time.perf_counter() - t0) * 1000),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="warehouse-mcp server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port, show_banner=False)
    else:
        mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
