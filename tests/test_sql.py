import pytest

from servers.warehouse_mcp.sql import MultipleStatementsError, prepare_query


def test_adds_limit_when_missing():
    assert prepare_query("SELECT * FROM analytics.orders", 200).endswith("LIMIT 201")


def test_keeps_smaller_limit():
    assert prepare_query("SELECT * FROM analytics.orders LIMIT 5", 200).endswith("LIMIT 5")


def test_caps_larger_limit():
    assert prepare_query("SELECT * FROM analytics.orders LIMIT 99999", 200).endswith("LIMIT 201")


def test_strips_trailing_semicolon():
    assert ";" not in prepare_query("SELECT 1;", 10)


def test_cte_and_union_get_limit():
    assert "LIMIT 11" in prepare_query("WITH t AS (SELECT 1 AS x) SELECT x FROM t", 10)
    assert "LIMIT 11" in prepare_query("SELECT 1 UNION SELECT 2", 10)


def test_rejects_multiple_statements():
    with pytest.raises(MultipleStatementsError):
        prepare_query("SELECT 1; DELETE FROM analytics.orders", 10)


def test_non_query_passes_through_for_database_to_reject():
    sql = "DELETE FROM analytics.orders"
    assert prepare_query(sql, 10) == sql
