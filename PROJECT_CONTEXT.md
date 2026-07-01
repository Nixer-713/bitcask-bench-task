# Project Context For External AI Review

## Background

This repository is part of a benchmark construction effort for evaluating AI
coding agents on end-to-end software tasks. The current direction follows the
updated Bmk-dev workflow: prefer full-project reconstruction tasks with a public
candidate packet and a private, source-grounded oracle built from filtered
upstream tests.

Older mini-product PRD/rubric tasks remain only when their source repository is
still acceptable and the files are useful as draft or historical material.

## REPO_POOL Alignment

Bmk-dev `REPO_POOL.md` was checked on 2026-07-01. It states that the listed
Python repositories are already occupied by the upstream pipeline, and it also
lists repositories that are retired or outside scope.

This cleanup removes local task deliverables for repositories that are explicitly
not usable in the current pipeline:

- `SarthakMakhija/bitcask`: non-Python / out of scope.
- `hoechstleistungshaartrockner/xitkit`: retired because of docs-test
  projection mismatch.
- `rochacbruno/marmite`: Rust / outside the Python-only pipeline.

Those tasks must not be revived or used as active development targets unless the
user explicitly changes the rule.

## Current Status

### Doit

`doit-realrepo-001` is the current E2E-style local artifact derived from
`pydoit/doit`. The candidate-visible files are under
`public_candidate_packet/doit-realrepo-001/`, while source evidence, filtered
tests, harnesses, and validation material are under
`authoring_private_oracle/doit-realrepo-001/`.

Treat it as a local authoring/evaluation artifact. Keep candidate-visible and
private oracle boundaries explicit.

### Copier

`task/copier-realrepo-001` is a legacy mini-product draft derived from
`copier-org/copier`. It has PRD, rubric, source evidence, requirement map, and
review docs, but it is not aligned to the updated full-project filtered-test
workflow.

Do not claim it as `core_strong`, confirmed benchmark, or gap-producing.

### Jupytext

`task/jupytext-realrepo-002` is a rewritten mini-product task draft derived from
`mwouts/jupytext`. `archive/no-gap-observed/jupytext-realrepo-001/` is retained
as historical no-gap evidence.

Do not claim either Jupytext packet as `core_strong`, confirmed benchmark, or
gap-producing.

## Current Direction

1. Check Bmk-dev `REPO_POOL.md` before selecting any source repository.
2. Do not start work on repositories listed as qualified, in progress, pending,
   retired, or outside scope unless the user explicitly overrides the pool.
3. Use `skills/e2e-00-task-synthesizer/SKILL.md` as the main orchestrator. It
   dispatches the installed/repository stage skills from candidate selection
   through judging.
4. Prefer the full-project workflow:
   - source evidence and capability decomposition;
   - boundary decisions;
   - public PRD/API/packaging packet;
   - filtered upstream oracle;
   - original/source validation;
   - isolated candidate evaluation.
5. Keep live evaluation packets clean: candidates see only
   `public_candidate_packet/<task-name>/`.
6. Keep task lifecycle directories distinct:
   - `wip/` for active synthesis;
   - `tasks/` for qualified tasks;
   - `candidate-runs/`, `results/`, and `logs/` for ignored local runtime
     artifacts;
   - `archive/` for historical or retired material.
7. Interpret results conservatively. Candidate 100/100 is no-gap evidence, not
   a reason to add hidden requirements.

## Review Questions

1. Does the repository still contain active task deliverables for a source
   marked unusable by Bmk-dev `REPO_POOL.md`?
2. Are public candidate packets separated from private oracle material?
3. Are any current docs recommending a repository already occupied by
   `REPO_POOL.md`?
4. Are any tasks claimed as `core_strong` without positive gap evidence?

## Non-Goals

- Do not revive Bitcask, Xitkit, or Marmite as local task targets.
- Do not add hidden tests or scorer logic to a public candidate packet.
- Do not evaluate generated implementations from this cleanup step.
