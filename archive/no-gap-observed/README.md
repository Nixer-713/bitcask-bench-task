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
| `marmite-realrepo-001` | Hardened reference-satisfiable on `validation/marmite-hardened`; no positive unit/system gap observed. |
| `jupytext-realrepo-001` | Reference-satisfiable on `validation/jupytext`; three candidates also passed all cases, so no-gap-observed. |

## Active Rewrite Boundary

The active `task/marmite-realrepo-001/` and `task/jupytext-realrepo-001/`
directories keep only source-grounding material and rewrite notes. New PRD and
rubric files should be drafted from a fresh public-behavior inventory, state /
artifact model, and system-invariant decomposition.
