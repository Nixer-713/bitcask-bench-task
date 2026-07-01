# Benchmark Task Agent Rules

Scope: this repo contains benchmark task deliverables derived from open-source projects.

## 1. Deliverable Boundary

- Existing `task/<name>/` directories are legacy mini-product handoff packets.
  Their core deliverables are `prd.md` and `rubric.json`, plus supporting
  `doc/source_repo.md` and `doc/requirement_map.md`.
- New full-project tasks should default to the E2E split:
  `public_candidate_packet/<name>/` for model-visible PRD/API/packaging files
  and `authoring_private_oracle/<name>/` for private source evidence, filtered
  tests, scoring manifests, harnesses, and validation reports.
- `prd.md` is always the public requirement document shown to model/code agents.
- `rubric.json` or filtered oracle tests are hidden evaluation definitions used
  to score model outputs.
- Do not commit reference implementations, scorer scripts, candidate outputs, or score reports to public handoff branches unless explicitly requested for an internal validation branch.
- Do not present generated implementation code as the task deliverable.

## 2. Benchmark Design Principles

- Start from a real open-source project and document the source in `doc/source_repo.md`.
- For new E2E full-project tasks, preserve the source project's public behavior
  through a senior-engineer PRD and filtered upstream tests rather than
  hand-authoring all tests from scratch.
- Abstract mini-product tasks only when the source project is not suitable for
  E2E full-project evaluation.
- The task should test system-level composition, not only isolated API behavior.
- Prefer stateful workflows, cross-module interactions, error recovery, persistence, ordering sensitivity, or global invariants when they naturally exist in the source project.
- `rubric.json` cases or filtered oracle tests must be naturally inferable from
  candidate-facing documents; no hidden product requirements.
- Tests must not depend on private implementation details such as file names, internal formats, object layouts, or exact algorithm choices unless the PRD explicitly requires them.
- Unit cases check local capabilities; system cases check interactions across at least two capabilities.
- The target signal is a meaningful gap: high unit pass rate with lower system pass rate.

## 2.1 Task Selection Roadmap

- Check upstream Bmk-dev `REPO_POOL.md` before starting any new source
  repository. Repositories listed there as qualified, in progress, pending,
  retired, or outside scope are not available for local development unless the
  user explicitly overrides that rule.
- `bitcask`, `xitkit`, and `marmite` task deliverables were removed from this
  branch because REPO_POOL marks their sources as non-Python/out-of-scope or
  retired.
- `copier-realrepo-001` and `jupytext-realrepo-002` are legacy mini-product
  draft artifacts. Do not claim either as `core_strong` or confirmed.
- `doit-realrepo-001` is the current E2E-style local artifact. Keep
  `public_candidate_packet/doit-realrepo-001/` candidate-visible and
  `authoring_private_oracle/doit-realrepo-001/` private/oracle-only.
- For future source selection, default to `e2e_full_project_task`: candidates
  receive only `public_candidate_packet/<name>/`, while filtered upstream tests,
  scorer/harness assets, source evidence, and validation reports stay private.
- The local SpecBench pipeline is versioned under `skills/e2e-*`. Use
  `skills/e2e-00-task-synthesizer/SKILL.md` as the orchestrator, then follow
  `e2e-01` through `e2e-04` in order.
- Track active synthesis in `wip/<task-id>/`. Move only qualified tasks into
  `tasks/<task-id>/`. Keep candidate runs, logs, and result tables out of
  candidate-visible packets.

## 2.2 Case-Like Difficulty Requirements

- Follow the reference benchmark style: unit tests cover local features, while
  system tests cross heterogeneous modules and derived views.
- Prefer tasks where one source state drives several public outputs: parsed
  records, filters, indexes, summaries, graph/links, generated files, or config
  effects.
- Avoid tasks whose public behavior collapses into one simple state model, such
  as append log -> live map -> metadata, unless extra public source-derived
  lifecycle semantics are added to the PRD first.
- Do not hard-code failure: candidate implementations may score 100/100. Treat
  that as no-gap evidence, not as proof that the task is invalid.

## 3. PRD Requirements

- Describe the command/program surface, inputs, outputs, errors, constraints, non-goals, and global invariants.
- Keep PRD user-visible: do not include hidden case IDs, expected test outputs, or rubric internals.
- Make edge cases explicit when they materially affect correctness.
- If storage, parsing, scheduling, or state is involved, define observable semantics instead of implementation shape.

## 4. Rubric Requirements

- Use stable case IDs and mark each case as `unit` or `system`.
- Include `requirement_refs` that map to `doc/requirement_map.md`.
- System cases must include `system_dimension`.
- Each check must be observable through public behavior: stdout, stderr, exit code, files explicitly specified by PRD, or persisted user-visible state.
- Avoid tests that pass only for one reference implementation.

## 5. Build And Validation

- Validate every changed `rubric.json` with JSON parsing before handoff.
- Check at minimum: unique IDs, valid layers, non-empty requirement refs, system cases have dimensions, and no implementation fields such as `solution`, `reference`, `implementation`, or `test_code`.
- For E2E full-project tasks, inventory upstream tests first, filter by
  derivability from the public packet, and validate the filtered oracle against
  the checked source implementation before running candidates.
- E2E harnesses must run install, contract, unit, and integration stages
  separately, preserve stdout/stderr/JUnit or JSON artifacts, and write
  `summary.json` before deciding final exit code.
- Confirm repository file tree contains only allowed deliverables and supporting docs.
- If local validation tools exist outside the handoff tree, run them from ignored/local paths and do not commit them.
- Run a leakage scan before commit: search for `_reference`, `score_report`,
  `score.py`, `evaluator`, `runs/`, `validation/`, `candidates/`, `answer`,
  `expected output`, and implementation artifacts. `public_candidate_packet/`
  is allowed when it contains only model-visible files.
- Use `git ls-files` as the source of truth for what will be delivered.

## 6. Correctness And Leakage Gates

- Every rubric case must trace to `requirement_map.md` and a public PRD behavior.
- Every E2E selected test must trace to `test_inventory.md`, `requirement_map.md`,
  and a public PRD/API/packaging behavior.
- If a test cannot be inferred from PRD, either remove the test or update PRD.
- If PRD states an implementation choice is free, rubric must not constrain that choice.
- PRD must not contain case IDs, hidden assertions, score strategy, or reference implementation hints.
- Rubric must not contain solution code, reference outputs beyond public assertions, or private setup formats.
- Official handoff tree should stay small: `README.md`, `AGENTS.md`, optional
  `INDEX.md`, optional `PROJECT_CONTEXT.md`, legacy task PRD/rubric/docs, and
  E2E public packet files. Hidden oracle assets belong only in private branches
  or ignored/private workspaces.

## 7. Required Subagent Checks

- Before final handoff, spawn one subagent to run benchmark-structure validation.
- Spawn a second independent subagent to review PRD/rubric consistency and fairness.
- Subagents must not edit files unless explicitly assigned.
- The review subagent must cite concrete evidence from files, including relevant snippets or line references showing why the task is acceptable or what must be fixed.
- Main agent must independently inspect subagent findings before committing or pushing.

## 8. Handoff Standard

- Final repo should be understandable from `README.md`, `PROJECT_CONTEXT.md`, `prd.md`, `rubric.json`, `source_repo.md`, and `requirement_map.md`.
- State clearly whether the task is draft, candidate, or confirmed gap-producing.
- If gap evidence is unavailable, do not claim the task is core-strong.
