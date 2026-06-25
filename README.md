# Benchmark Task Deliverables

This repository contains benchmark task handoff files derived from real
open-source projects. Each task is represented by a public PRD and a hidden
rubric, plus supporting source and requirement mapping docs.

## Tasks

| Task | Source project | Status |
| --- | --- | --- |
| `task/bitcask-realrepo-001` | `SarthakMakhija/bitcask` | Candidate with no-gap-observed validation evidence; not core-strong |
| `task/xitkit-realrepo-001` | `hoechstleistungshaartrockner/xitkit` | Source-grounded candidate with initial no-gap-observed validation evidence; not core-strong |
| `task/marmite-realrepo-001` | `rochacbruno/marmite` | Reference-satisfiable on `validation/marmite`; no positive gap observed; not core-strong |

## Deliverable Boundary

For each task, the core deliverables are:

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
but initial validation also produced no observed unit/system gap. Marmite is
reference-satisfiable, but the validation batch did not produce a positive
unit/system gap. The active construction path is:

1. Keep Bitcask and xitkit recorded as candidate/no-gap-observed evidence.
2. Do not merge validation assets into `main`.
3. Keep Marmite recorded as reference-satisfiable/no-positive-gap-observed
   evidence unless a future source-grounded hardening pass changes validation
   results.

For AI reviewers, start from `PROJECT_CONTEXT.md`, `INDEX.md`, and `AGENTS.md`.
