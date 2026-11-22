"""Retrieval metrics over expected tables."""

from __future__ import annotations


def table_recall_at_k(retrieved: list[dict], expected_tables: list[str], k: int) -> float:
    """Share of expected tables covered by the table_names of the top-k chunks."""
    if not expected_tables:
        return 1.0
    covered = {t for d in retrieved[:k] for t in d.get("table_names", [])}
    return sum(t in covered for t in expected_tables) / len(expected_tables)
