# ADR-001: Two MCP servers split by trust boundary

Status: accepted (v0.1)

## Context

The agent needs warehouse access and document retrieval. These could live in
one server or in several split by feature (catalog, dbt, tickets, ...).

## Decision

Two servers, split by what they can touch:

- `warehouse-mcp` reads sensitive data and connects as `agent_readonly`.
- `knowledge-mcp` reads only the docs index and connects as `knowledge_reader`.

Each role is denied the other's schema.

## Consequences

- A bug or prompt injection in the retrieval path cannot read warehouse rows.
- Each server can be deployed, scaled and permissioned on its own, and reused by
  any MCP client (Claude Desktop, Cursor, this agent).
- Feature-based splits (separate catalog or ticket servers) were rejected:
  they add processes without adding an isolation boundary.
- The agent makes two connections instead of one; the cost is negligible.
