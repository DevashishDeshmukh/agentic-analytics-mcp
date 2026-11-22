"""SQL preparation for warehouse-mcp.

v0.1 scope: enforce a single statement and a row LIMIT. Read-only access is
enforced by the Postgres role (see infra/db/init), not here. A full AST
allowlist policy arrives in v0.4.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class MultipleStatementsError(ValueError):
    pass


def prepare_query(sql: str, max_rows: int) -> str:
    """Return SQL with LIMIT max_rows + 1 applied to a single query.

    The extra row lets the caller detect truncation. Non-query statements and
    SQL that fails to parse are returned unchanged so Postgres can reject them
    with its own error (the database is the enforcement layer).
    """
    sql = sql.strip().rstrip(";").strip()
    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except ParseError:
        return sql
    if len(statements) > 1:
        raise MultipleStatementsError("Send exactly one SQL statement per call.")
    if not statements:
        return sql
    stmt = statements[0]
    if not isinstance(stmt, exp.Query):
        return sql

    fetch = max_rows + 1
    limit = stmt.args.get("limit")
    if limit is not None:
        try:
            current = int(limit.expression.this)
        except (AttributeError, TypeError, ValueError):
            current = None
        if current is not None and current <= fetch:
            return stmt.sql(dialect="postgres")
    return stmt.limit(fetch).sql(dialect="postgres")
