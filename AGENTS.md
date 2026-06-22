# Benchmark Task Agent Rules

Scope: this repo contains benchmark task deliverables derived from open-source projects.

## 1. Deliverable Boundary

- Core deliverables are only `prd.md` and `rubric.json` under each task directory.
- `prd.md` is the public requirement document shown to model/code agents.
- `rubric.json` is the hidden evaluation definition used to score model outputs.
- `doc/source_repo.md` and `doc/requirement_map.md` are supporting review materials.
- Do not commit reference implementations, scorer scripts, candidate outputs, or score reports unless explicitly requested for an internal validation branch.
- Do not present generated implementation code as the task deliverable.

## 2. Benchmark Design Principles

- Start from a real open-source project and document the source in `doc/source_repo.md`.
- Abstract the source project into a smaller, self-contained task with clear public behavior.
- The task should test system-level composition, not only isolated API behavior.
- Prefer stateful workflows, cross-module interactions, error recovery, persistence, ordering sensitivity, or global invariants when they naturally exist in the source project.
- `rubric.json` cases must be naturally inferable from `prd.md`; no hidden product requirements.
- Tests must not depend on private implementation details such as file names, internal formats, object layouts, or exact algorithm choices unless the PRD explicitly requires them.
- Unit cases check local capabilities; system cases check interactions across at least two capabilities.
- The target signal is a meaningful gap: high unit pass rate with lower system pass rate.

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
- Confirm repository file tree contains only allowed deliverables and supporting docs.
- If local validation tools exist outside the handoff tree, run them from ignored/local paths and do not commit them.
- Run a leakage scan before commit: search for `_reference`, `score_report`, `score.py`, `evaluator`, `candidate`, `answer`, `expected output`, and implementation artifacts.
- Use `git ls-files` as the source of truth for what will be delivered.

## 6. Correctness And Leakage Gates

- Every rubric case must trace to `requirement_map.md` and a public PRD behavior.
- If a test cannot be inferred from PRD, either remove the test or update PRD.
- If PRD states an implementation choice is free, rubric must not constrain that choice.
- PRD must not contain case IDs, hidden assertions, score strategy, or reference implementation hints.
- Rubric must not contain solution code, reference outputs beyond public assertions, or private setup formats.
- Official handoff tree should stay small: `README.md`, `AGENTS.md`, optional `INDEX.md`, and task PRD/rubric/docs.

## 7. Required Subagent Checks

- Before final handoff, spawn one subagent to run benchmark-structure validation.
- Spawn a second independent subagent to review PRD/rubric consistency and fairness.
- Subagents must not edit files unless explicitly assigned.
- The review subagent must cite concrete evidence from files, including relevant snippets or line references showing why the task is acceptable or what must be fixed.
- Main agent must independently inspect subagent findings before committing or pushing.

## 8. Handoff Standard

- Final repo should be understandable from `README.md`, `prd.md`, `rubric.json`, `source_repo.md`, and `requirement_map.md`.
- State clearly whether the task is draft, candidate, or confirmed gap-producing.
- If gap evidence is unavailable, do not claim the task is core-strong.
