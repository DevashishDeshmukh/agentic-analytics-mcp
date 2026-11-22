# Contributing

## Branches

| Branch | Purpose |
|---|---|
| `main` | Always releasable. Only release merges land here. |
| `release/vX.Y` | Work for one version (see [RELEASE_PLAN.md](RELEASE_PLAN.md)). Kept after merge. |
| `fix/<topic>` | Hotfix off `main`, merged back to `main` and the open release branch. |

## Release flow

```bash
git switch main && git switch -c release/v0.2     # start a version
# ...atomic commits...
make lint test check-gold eval-all                # Definition of Done
git switch main
git merge --no-ff release/v0.2 -m "Merge release/v0.2"
git tag -a v0.2.0 -m "v0.2.0: retrieval quality"
```

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject`.

- Types: `feat`, `fix`, `test`, `docs`, `build`, `ci`, `refactor`, `perf`, `chore`.
- Scopes: `warehouse-mcp`, `knowledge-mcp`, `agent`, `ingestion`, `evals`, `infra`, `data`.
- Subject: imperative, lower case, no period, at most 72 characters.
- One logical change per commit; tests ship in the same commit as the code.
- Never commit `.env` or eval detail logs (`*.jsonl`).
