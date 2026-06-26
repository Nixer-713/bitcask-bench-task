# Benchmark Task Deliverables

This repository contains benchmark task handoff files derived from real
open-source projects. Each task is represented by a public PRD and a hidden
rubric, plus supporting source and requirement mapping docs.

## Tasks

| Task | Source project | Status |
| --- | --- | --- |
| `task/bitcask-realrepo-001` | `SarthakMakhija/bitcask` | Candidate with no-gap-observed validation evidence; not core-strong |
| `task/xitkit-realrepo-001` | `hoechstleistungshaartrockner/xitkit` | Source-grounded candidate with initial no-gap-observed validation evidence; not core-strong |
| `task/marmite-realrepo-001` | `rochacbruno/marmite` | Hardened reference-satisfiable on `validation/marmite-hardened`; no positive unit/system gap observed; not core-strong |
| `task/jupytext-realrepo-001` | `mwouts/jupytext` | Source-grounded handoff draft with PRD, requirement map, and rubric; validation not started |

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
but initial validation also produced no observed unit/system gap. Marmite's
hardened rubric has been validated on `validation/marmite-hardened`: the
reference passed 19/19 unit and 15/15 system cases, one candidate passed all
cases, and two candidates passed 17/19 unit and 14/15 system cases. Those
failures were local filename metadata / stream parsing issues, not positive
unit/system gap evidence. The active construction path is:

1. Keep Bitcask and xitkit recorded as candidate/no-gap-observed evidence.
2. Do not merge validation assets into `main`.
3. Treat Marmite as hardened reference-satisfiable/no-positive-gap-observed
   evidence unless future source-grounded work changes the validation result.
4. Treat Jupytext as the active source-grounded candidate ready for validation
   planning; do not claim `core_strong` before reference/candidate evidence.

For AI reviewers, start from `PROJECT_CONTEXT.md`, `INDEX.md`, and `AGENTS.md`.
