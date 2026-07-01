# REPO_POOL Alignment Note

Checked source: Bmk-dev `REPO_POOL.md` on 2026-07-01.

## Rule

Before starting a new source task, check upstream `REPO_POOL.md`.

Do not start local task development from a repository that appears in any of
these sections unless the user explicitly overrides the rule:

- `QUALIFIED`
- `IN_PROGRESS`
- `PENDING`
- retired / cannot continue
- non-Python / outside scope

This avoids duplicating upstream work and prevents spending effort on sources
that the reference pipeline already rejected.

## Cleanup Applied

Removed local task deliverables for sources explicitly unusable in the current
pool:

| Source | Local artifact removed | REPO_POOL reason |
| --- | --- | --- |
| `SarthakMakhija/bitcask` | `task/bitcask-realrepo-001` | Go / non-Python |
| `hoechstleistungshaartrockner/xitkit` | `task/xitkit-realrepo-001` | Retired / docs-test projection mismatch |
| `rochacbruno/marmite` | `task/marmite-realrepo-001`, archived Marmite packet | Rust / non-Python |

## Direction Update

Do not use stale local source-selection memos that recommend repositories now
listed in REPO_POOL, including:

- `cookiecutter/cookiecutter`
- `simonw/sqlite-utils`
- `pre-commit/pre-commit`
- `zk-org/zk`
- `sqlalchemy/alembic`

Current local work should either:

1. continue with an already-started source that is not listed as unavailable in
   REPO_POOL, or
2. select a new source only after a fresh REPO_POOL check.

Any new task should follow the updated full-project flow:

- public candidate packet under `public_candidate_packet/<name>/`;
- private source evidence, filtered tests, harnesses, and validation reports
  under a private oracle workspace;
- no candidate access to source implementation, filtered tests, scorer logic,
  reference solutions, or reports.
