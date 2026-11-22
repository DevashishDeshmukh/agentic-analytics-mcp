# Contributing

## Branches

| Branch | Purpose |
|---|---|
| `main` | Always releasable. Protected: changes arrive only through pull requests; no force pushes or deletion. |
| `release/vX.Y` | Work for one version (see [RELEASE_PLAN.md](RELEASE_PLAN.md)). Patch releases (`vX.Y.Z`) reuse it. Kept after merge. |
| `fix/<topic>` | Hotfix off `main`, merged back by pull request. |

## Release flow

```bash
git switch main && git pull && git switch -c release/v0.2   # start a version
# ...atomic commits...
make lint test check-gold eval-all                          # Definition of Done
git push -u origin release/v0.2
gh pr create --base main --head release/v0.2 --title "Release v0.2: retrieval quality" --body-file <notes>
gh pr merge --merge                                         # merge commit, keeps history grouped
git switch main && git pull
git tag -a v0.2.0 -m "v0.2.0: retrieval quality" && git push origin v0.2.0
gh release create v0.2.0 --verify-tag --notes-file <notes>
```

Then run the close-out checklist in [RELEASE_PLAN.md](RELEASE_PLAN.md#1a-version-close-out).

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): subject`.

- Types: `feat`, `fix`, `test`, `docs`, `build`, `ci`, `refactor`, `perf`, `chore`.
- Scopes: `warehouse-mcp`, `knowledge-mcp`, `agent`, `ingestion`, `evals`, `infra`, `data`.
- Subject: imperative, lower case, no period, at most 72 characters.
- One logical change per commit; tests ship in the same commit as the code.
- Never commit `.env` or eval detail logs (`*.jsonl`).
