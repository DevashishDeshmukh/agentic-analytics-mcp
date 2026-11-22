"""Integration tests: need `make up seed ingest` first. Run with: make test-db"""

import pytest
from fastmcp import Client

from servers.knowledge_mcp.server import mcp as knowledge
from servers.warehouse_mcp.server import mcp as warehouse

pytestmark = pytest.mark.db


async def call(server, tool, args, ok=True):
    async with Client(server) as c:
        r = await c.call_tool(tool, args, raise_on_error=False)
        assert r.is_error is not ok, r.content
        return r


async def test_list_tables_includes_orders():
    r = await call(warehouse, "list_tables", {})
    tables = [t["table"] for t in r.structured_content["result"]]
    assert "analytics.orders" in tables


async def test_run_query_returns_rows_and_applies_limit():
    r = await call(warehouse, "run_query",
                   {"sql": "SELECT order_id FROM analytics.orders", "max_rows": 10})
    s = r.structured_content
    assert s["row_count"] == 10 and s["truncated"] is True
    assert s["sql_executed"].endswith("LIMIT 11")


@pytest.mark.parametrize("sql", [
    "DELETE FROM analytics.orders",
    "UPDATE analytics.orders SET amount = 0",
    "DROP TABLE analytics.orders",
    "CREATE TABLE analytics.x (i int)",
])
async def test_writes_rejected_by_database(sql):
    r = await call(warehouse, "run_query", {"sql": sql}, ok=False)
    assert "read-only" in r.content[0].text


async def test_write_hidden_in_cte_rejected_by_database():
    # Parses as a query (so it passes the LIMIT step); Postgres must stop it.
    sql = "WITH d AS (DELETE FROM analytics.orders RETURNING *) SELECT count(*) FROM d"
    r = await call(warehouse, "run_query", {"sql": sql}, ok=False)
    assert "read-only" in r.content[0].text


async def test_warehouse_role_cannot_read_knowledge_schema():
    r = await call(warehouse, "run_query",
                   {"sql": "SELECT * FROM knowledge.chunks"}, ok=False)
    assert "permission denied" in r.content[0].text


async def test_multiple_statements_rejected():
    await call(warehouse, "run_query", {"sql": "SELECT 1; SELECT 2"}, ok=False)


async def test_search_finds_metric_definition():
    r = await call(knowledge, "search_knowledge",
                   {"query": "revenue after refunds", "k": 3})
    ids = [d["chunk_id"] for d in r.structured_content["result"]]
    assert "metric:net_revenue" in ids


async def test_search_filters_by_source_type():
    r = await call(knowledge, "search_knowledge",
                   {"query": "orders", "k": 5, "source_types": ["issue"]})
    assert all(d["source_type"] == "issue" for d in r.structured_content["result"])


async def test_get_documents_by_id():
    r = await call(knowledge, "get_documents", {"chunk_ids": ["table:analytics.orders"]})
    assert r.structured_content["result"][0]["chunk_id"] == "table:analytics.orders"
