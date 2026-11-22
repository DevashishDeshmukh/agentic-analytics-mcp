"""Ingest knowledge docs into knowledge.chunks (idempotent, hash-based upsert).

Usage:
    uv run python -m ingestion.ingest_docs
"""

from __future__ import annotations

import json
import time

import psycopg
from pgvector.psycopg import register_vector

from common.embeddings import embed_passages
from common.settings import get_settings
from ingestion.chunking import build_chunks


def main() -> None:
    s = get_settings()
    t0 = time.time()
    chunks = build_chunks(s.root / "data" / "docs", s.root)

    with psycopg.connect(s.admin_dsn) as conn:
        register_vector(conn)
        existing = dict(conn.execute("SELECT chunk_id, content_hash FROM knowledge.chunks"))
        changed = [c for c in chunks if existing.get(c.chunk_id) != c.content_hash]
        current_ids = {c.chunk_id for c in chunks}
        stale = [cid for cid in existing if cid not in current_ids]

        if changed:
            vectors = embed_passages([c.content for c in changed])
            for c, v in zip(changed, vectors):
                conn.execute(
                    """
                    INSERT INTO knowledge.chunks (chunk_id, source_type, source_path, title,
                        content, table_names, metadata, content_hash, embedding, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        source_type = EXCLUDED.source_type, source_path = EXCLUDED.source_path,
                        title = EXCLUDED.title, content = EXCLUDED.content,
                        table_names = EXCLUDED.table_names, metadata = EXCLUDED.metadata,
                        content_hash = EXCLUDED.content_hash, embedding = EXCLUDED.embedding,
                        updated_at = now()
                    """,
                    (c.chunk_id, c.source_type, c.source_path, c.title, c.content,
                     c.table_names, json.dumps(c.metadata, default=str), c.content_hash,
                     v),
                )
        if stale:
            conn.execute("DELETE FROM knowledge.chunks WHERE chunk_id = ANY(%s)", (stale,))
        conn.commit()

    print(f"{len(chunks)} chunks: {len(changed)} embedded, {len(stale)} removed, "
          f"{len(chunks) - len(changed)} unchanged ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
