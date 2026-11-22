from common.settings import get_settings
from ingestion.chunking import build_chunks


def chunks():
    s = get_settings()
    return {c.chunk_id: c for c in build_chunks(s.root / "data" / "docs", s.root)}


def test_one_chunk_per_source_unit():
    ids = chunks()
    assert "table:analytics.orders" in ids
    assert "metric:net_revenue" in ids
    assert "issue:ISSUE-001" in ids
    assert "glossary:marketing-glossary" in ids


def test_chunk_ids_unique_and_tables_qualified():
    cs = build_chunks(get_settings().root / "data" / "docs", get_settings().root)
    assert len(cs) == len({c.chunk_id for c in cs})
    for c in cs:
        assert all(t.startswith("analytics.") for t in c.table_names), c.chunk_id


def test_deprecated_and_outdated_are_flagged_in_content():
    ids = chunks()
    assert "DEPRECATED" in ids["table:analytics.legacy_orders_v1"].content
    assert ids["glossary:revenue-reporting-2022"].content.startswith("OUTDATED")


def test_hash_changes_with_content():
    c = chunks()["metric:gross_revenue"]
    h = c.content_hash
    c.content += " changed"
    assert c.content_hash != h
