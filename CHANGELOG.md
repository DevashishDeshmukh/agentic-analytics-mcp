# Changelog

All notable changes to this project. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-11-22

### Added
- `warehouse-mcp`: `list_tables`, `describe_table`, `run_query` with structured output,
  read-only tool annotations, auto `LIMIT`, single-statement check.
- `knowledge-mcp`: `search_knowledge` (pgvector, bge-small embeddings) and `get_documents`.
- Postgres roles `agent_readonly` and `knowledge_reader`: SELECT-only grants, read-only
  transactions, statement timeouts, no cross-schema access.
- Synthetic e-commerce warehouse (~900k rows, fixed seed) with planted data issues.
- Knowledge sources: table docs, 10 governed metrics, 3 known issues, 2 glossaries
  (one outdated, one conflicting).
- Structure-aware chunking and idempotent ingestion.
- Agent loop: retrieve, link schema, generate SQL, execute, answer with citations.
- Feature-flag configs `baseline` and `rag` for ablations.
- Eval harness: 30 questions with gold SQL, execution accuracy, table recall@5,
  latency, cost; README table generated from results.
- Unit and integration tests, Makefile, Claude Desktop config example.

### Eval set changes
- q011, q016: added "Only include customers with a known region". After the first
  runs, the model sometimes (correctly, per ISSUE-003) added an unknown-region
  bucket that the gold query excludes. Ambiguity is tested separately in v0.3.
- Comparator: a gold period number (year, quarter, month) may match a predicted
  date label for the same period (q022 was a false negative). Text labels are
  never remapped.

### Verified manually
- `agent_readonly` gets `permission denied for table orders` even inside
  `BEGIN READ WRITE`, so the SELECT-only grant holds if read-only mode is bypassed.
