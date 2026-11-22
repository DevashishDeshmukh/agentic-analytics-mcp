from datetime import date, datetime
from decimal import Decimal

from evals.metrics.compare import results_match
from evals.metrics.retrieval import table_recall_at_k


def test_exact_match_ignores_row_order():
    assert results_match([["a", 1], ["b", 2]], [["b", 2], ["a", 1]])


def test_numeric_types_and_rounding():
    assert results_match([[Decimal("131.51840000")]], [[131.5184]])
    assert results_match([[5]], [[5.0]])
    assert not results_match([[131.51]], [[131.52]])


def test_date_vs_midnight_timestamp():
    assert results_match([[date(2024, 1, 1), 10]], [["2024-01-01T00:00:00", 10]])
    assert results_match([[date(2024, 1, 1)]], [[datetime(2024, 1, 1)]])


def test_extra_predicted_columns_allowed():
    gold = [["APAC", 10], ["India", 20]]
    pred = [[5, "APAC", 10], [6, "India", 20]]
    assert results_match(gold, pred)


def test_column_order_independent():
    assert results_match([["APAC", 10]], [[10, "APAC"]])


def test_row_count_must_match():
    assert not results_match([[1]], [[1], [2]])


def test_missing_column_fails():
    assert not results_match([["APAC", 10]], [["APAC"]])


def test_rows_must_align_not_just_columns():
    gold = [["a", 1], ["b", 2]]
    pred = [["a", 2], ["b", 1]]
    assert not results_match(gold, pred)


def test_empty_results():
    assert results_match([], [])


def test_table_recall():
    retrieved = [{"table_names": ["analytics.orders"]}, {"table_names": ["analytics.refunds"]}]
    assert table_recall_at_k(retrieved, ["analytics.orders", "analytics.refunds"], 5) == 1.0
    assert table_recall_at_k(retrieved, ["analytics.orders", "analytics.refunds"], 1) == 0.5


def test_period_number_matches_date_label():
    gold = [[1.0, 2105], [2.0, 3374]]
    pred = [["2023-01-01", 2105], ["2023-04-01", 3374]]
    assert results_match(gold, pred)


def test_period_transform_still_checks_alignment():
    gold = [[1.0, 2105], [2.0, 3374]]
    pred = [["2023-01-01", 3374], ["2023-04-01", 2105]]
    assert not results_match(gold, pred)


def test_no_remapping_of_text_labels():
    gold = [["APAC", 10], ["India", 20]]
    pred = [["India", 10], ["APAC", 20]]
    assert not results_match(gold, pred)
