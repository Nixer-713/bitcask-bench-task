# Benchmark Task Deliverables

This repository contains benchmark task handoff files derived from real
open-source projects. Each task is represented by a public PRD and a hidden
rubric, plus supporting source and requirement mapping docs.

## Tasks

| Task | Source project | Status |
| --- | --- | --- |
| `task/bitcask-realrepo-001` | `SarthakMakhija/bitcask` | Candidate with no-gap-observed validation evidence; not core-strong |
| `task/xitkit-realrepo-001` | `hoechstleistungshaartrockner/xitkit` | Source-grounded candidate with initial no-gap-observed validation evidence; not core-strong |
| `task/marmite-realrepo-001` | `rochacbruno/marmite` | Prior handoff archived as no-positive-gap-observed evidence; active task reset for redesign |
| `task/jupytext-realrepo-001` | `mwouts/jupytext` | Prior handoff archived as no-gap-observed evidence; active task reset for redesign |
| `task/copier-realrepo-001` | `copier-org/copier` | Draft handoff created; pending validation on a validation branch |

## Deliverable Boundary

For each active handoff task, the core deliverables are:

- `prd.md`: public product requirement document shown to model/code agents.
- `rubric.json`: hidden unit/system evaluation definition.
- `doc/source_repo.md`: source-project evidence and adaptation rationale.
- `doc/requirement_map.md`: traceability from PRD requirements to rubric cases.

Reference implementations, scorer scripts, candidate outputs, and score reports
must stay out of `main` unless the repository is explicitly converted into a
validation package.

## Current Direction

Bitcask remains useful as a clean candidate handoff and no-gap evidence, but it
must not be claimed as `core_strong`. Xitkit is source-grounded and executable,
but initial validation also produced no observed unit/system gap. The prior
Marmite and Jupytext handoff packets have been archived under
`archive/no-gap-observed/` because validation did not show positive unit/system
gap evidence. Their active task directories now keep source-grounding material
and rewrite notes only. The active construction path is:

1. Keep Bitcask and xitkit recorded as candidate/no-gap-observed evidence.
2. Do not merge validation assets into `main`.
3. Treat archived Marmite and Jupytext packets as evidence/history, not current
   handoff deliverables.
4. Redesign Marmite and Jupytext from public behavior inventory, capability
   modules, state/artifact models, and system invariants before drafting new
   PRDs or rubrics.
5. Build and validate `copier-realrepo-001` as the next active candidate. Its
   current `main` packet is a draft handoff, not a confirmed or core-strong
   benchmark.

For AI reviewers, start from `PROJECT_CONTEXT.md`, `INDEX.md`, and `AGENTS.md`.
