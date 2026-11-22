# Architecture (v0.1)

## Request flow

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent loop
    participant K as knowledge-mcp
    participant W as warehouse-mcp
    participant L as LLM
    U->>A: question
    A->>K: search_knowledge(question, k=6)
    K-->>A: chunks (tables, metrics, issues, glossary)
    A->>W: describe_table(t) for each table referenced by chunks
    W-->>A: columns + types
    A->>L: generate_sql(context, question)
    L-->>A: {sql, tables_used, chunk_ids_used, assumptions}
    A->>W: run_query(sql)
    W-->>A: rows (read-only role, LIMIT applied)
    A->>L: answer(question, sql, rows, context)
    L-->>A: {answer, citations, caveats}
    A-->>U: answer + SQL + rows + citations
```

`baseline` config skips the search step and describes every table instead.

## Database layout

| Schema | Contents | Readable by |
|---|---|---|
| `analytics` | Warehouse tables | `agent_readonly` |
| `knowledge` | `chunks` table with `vector(384)` embeddings, HNSW index | `knowledge_reader` |

Both roles: `default_transaction_read_only = on`, statement timeout, no CREATE.
Seeding and ingestion use the `postgres` admin role.

## Defense layers for `run_query`

1. Single-statement check and `LIMIT` injection (`servers/warehouse_mcp/sql.py`)
2. Read-only transactions (role setting)
3. SELECT-only grants (role privileges)
4. 10s statement timeout (role setting)

Layers 2 to 4 hold even if layer 1 is bypassed. That is the point: the
database is the enforcement layer.
