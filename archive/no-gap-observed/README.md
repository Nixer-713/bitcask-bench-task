# No-Gap-Observed Task Archive

This directory preserves prior benchmark handoff drafts that were executable or
source-grounded but did not produce positive unit/system gap evidence in the
observed validation batches.

Archived task packets are evidence and design history, not active handoff
targets. They must not be claimed as `core_strong`, `confirmed benchmark`, or
`gap-producing`.

## Archived Tasks

| Task | Archived status |
| --- | --- |
| `jupytext-realrepo-001` | Reference-satisfiable on `validation/jupytext`; three candidates also passed all cases, so no-gap-observed. |

## REPO_POOL Cleanup

The archived Marmite packet was removed because upstream Bmk-dev `REPO_POOL.md`
lists `marmite` as non-Python/outside the current pipeline scope.

Jupytext is retained as historical no-gap evidence because it is not listed as
retired or outside scope in the checked REPO_POOL snapshot.
