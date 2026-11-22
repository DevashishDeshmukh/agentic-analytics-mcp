# ADR-002: Small explicit agent loop instead of a framework

Status: accepted (v0.1)

## Context

Options: LangChain/LangGraph, an agent SDK, or a hand-written loop.

## Decision

A hand-written loop in `agent/loop.py`: retrieve, link schema, generate SQL,
execute, answer. Each step is a plain function call with its own timing and
token accounting.

## Consequences

- Every step is visible in traces and testable in isolation.
- Feature flags (`config/features.yaml`) switch steps on or off for ablations
  without touching framework internals.
- Easy to explain line by line.
- Branching (clarification, self-correction, routing) arrives in v0.3. If the
  graph grows beyond a few branches, revisit LangGraph; the MCP tools and evals
  stay the same either way.
