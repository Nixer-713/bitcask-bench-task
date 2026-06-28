# Copier Structure Review

## Scope

Reviewed files:

- `task/copier-realrepo-001/prd.md`
- `task/copier-realrepo-001/rubric.json`
- `task/copier-realrepo-001/doc/source_repo.md`
- `task/copier-realrepo-001/doc/requirement_map.md`
- `task/copier-realrepo-001/doc/boundary_decisions.md`

## JSON And Schema Issues

- Verdict: keep.
- `rubric.json` parses as JSON.
- The rubric contains 26 cases: 16 unit cases and 10 system cases.
- The rubric uses the task-local CLI/filesystem adapter documented in
  `doc/requirement_map.md`.

## Duplicate IDs

- Verdict: keep.
- Case IDs are unique.
- Unit cases use `CPU001` through `CPU016`.
- System cases use `CPS001` through `CPS010`.

## Missing Requirement Refs

- Verdict: keep.
- Every rubric case has non-empty `requirement_refs`.
- Every referenced requirement appears in `doc/requirement_map.md`.

## Missing System Dimensions

- Verdict: keep.
- Every system case includes `system_dimension`.
- The selected dimensions are:
  - `cross_feature_dataflow`
  - `state_accumulation`
  - `global_invariant`
  - `error_atomicity`
  - `boundary_crossing`
  - `operation_order_sensitivity`

## Forbidden Fields

- Verdict: keep.
- No rubric case contains `solution`, `reference`, `implementation`,
  `test_code`, `code`, or `answer`.

## Leakage Scan Findings

- No reference implementation, scorer, candidate output, score report, or
  validation report is part of the Copier handoff on `main`.
- The task directory contains only PRD/rubric and supporting review/source docs.

## Resolved Review Items

- Added `tests/test_config.py` to the source evidence path list because
  configuration parsing is part of the unit coverage.
- Added a Rubric Adapter Contract to `doc/requirement_map.md` so the scorer
  contract for `setup_files`, `setup_git`, `steps`, `expect_error`,
  `write_file`, `stdout_json_contains`, and public file checks is explicit.

## Unresolved Blockers

None for structure validation.
