# Repository Index For AI Review

Purpose: this repository is a benchmark task handoff and authoring workspace,
not an implementation repository.

## Entry Points

- `README.md`: repository purpose, active artifacts, and REPO_POOL alignment.
- `PROJECT_CONTEXT.md`: current status and review expectations.
- `AGENTS.md`: repo-wide construction rules, correctness gates, and leakage
  prevention.
- `doc/e2e_full_project_pipeline.md`: full-project source-selection-to-eval
  workflow.
- `doc/repo_pool_alignment.md`: current Bmk-dev REPO_POOL interpretation and
  cleanup record.
- `MANIFEST.json`: local workspace layout and active skill list.
- `skills/README.md`: repository-maintained E2E skill copies and install notes.
- `CANDIDATES.md`: source selection and retirement log for the local pipeline.
- `wip/_template/PIPELINE_STATE.md`: reusable state-machine seed for new
  SpecBench-style task candidates.
- `tasks/README.md`: destination for qualified tasks.
- `candidate-runs/README.md`, `results/README.md`, `logs/README.md`: ignored
  runtime output directories.
- `public_candidate_packet/README.md`: candidate-visible E2E packet boundary.
- `authoring_private_oracle/README.md`: private oracle/evaluation boundary.

## Pipeline Skill Index

The main orchestrator is `skills/e2e-00-task-synthesizer/SKILL.md`. It routes
the full workflow through:

1. `skills/e2e-01-candidate-selector/SKILL.md`
2. `skills/e2e-02-spec-writer/SKILL.md`
3. `skills/e2e-03-test-filter/SKILL.md`
4. cleanroom candidate evaluation
5. `skills/e2e-04-task-judge/SKILL.md`

Runtime copies are installed under `/Users/nixer/.codex/skills/e2e-*`.

## Active And Historical Artifacts

### `doit-realrepo-001`

- Source project: `pydoit/doit`
- Mode: E2E full-project task.
- Candidate-visible packet:
  - `public_candidate_packet/doit-realrepo-001/prd.md`
  - `public_candidate_packet/doit-realrepo-001/public_api_contract.md`
  - `public_candidate_packet/doit-realrepo-001/packaging_contract.md`
- Authoring/oracle material:
  - `authoring_private_oracle/doit-realrepo-001/doc/`
  - `authoring_private_oracle/doit-realrepo-001/oracle/`
  - `authoring_private_oracle/doit-realrepo-001/docker/`
  - `authoring_private_oracle/doit-realrepo-001/validation/`
- Status: local E2E authoring/evaluation artifact. Keep candidate-visible and
  private oracle boundaries explicit.

### `copier-realrepo-001`

- Source project: `copier-org/copier`
- Checked source revision: `454ec4244132bce478e60c4707ee418312ca8922`
- Mode: legacy mini-product task.
- Files:
  - `task/copier-realrepo-001/prd.md`
  - `task/copier-realrepo-001/rubric.json`
  - `task/copier-realrepo-001/doc/source_repo.md`
  - `task/copier-realrepo-001/doc/boundary_decisions.md`
  - `task/copier-realrepo-001/doc/requirement_map.md`
  - `task/copier-realrepo-001/doc/review_structure.md`
  - `task/copier-realrepo-001/doc/review_fairness.md`
- Status: draft handoff. It has not been converted to the updated
  full-project filtered-test workflow and must not be claimed as confirmed.

### `jupytext-realrepo-002`

- Source project: `mwouts/jupytext`
- Mode: rewritten mini-product task.
- Files:
  - `task/jupytext-realrepo-002/prd.md`
  - `task/jupytext-realrepo-002/rubric.json`
  - `task/jupytext-realrepo-002/doc/source_repo.md`
  - `task/jupytext-realrepo-002/doc/boundary_decisions.md`
  - `task/jupytext-realrepo-002/doc/requirement_map.md`
- Status: draft/rewrite artifact. No `core_strong` or confirmed gap claim.

### Historical Jupytext Archive

- `archive/no-gap-observed/jupytext-realrepo-001/`
- Status: historical no-gap evidence. It is not an active task target.

## Removed By REPO_POOL Cleanup

These artifacts were removed because Bmk-dev `REPO_POOL.md` marks their sources
as retired or outside the current Python-only pipeline:

- `task/bitcask-realrepo-001`
- `task/xitkit-realrepo-001`
- `task/marmite-realrepo-001`
- `archive/no-gap-observed/marmite-realrepo-001`

## Mechanical Checks

```console
python3 -m json.tool task/copier-realrepo-001/rubric.json >/dev/null
python3 -m json.tool task/jupytext-realrepo-002/rubric.json >/dev/null
python3 -m json.tool archive/no-gap-observed/jupytext-realrepo-001/rubric.json >/dev/null
git diff --check
git ls-files | rg 'bitcask|xitkit|marmite|SarthakMakhija|hoechstleistungshaartrockner|rochacbruno'
```

The last command should return no tracked paths for removed/disallowed task
deliverables.

## Review Checklist

- Candidate-facing packets do not expose oracle tests, scoring logic, source
  implementation, reference solutions, reports, or candidate outputs.
- PRDs describe public behavior only.
- Legacy rubrics are inferable from the matching PRD and avoid private
  implementation details.
- Every future source selection checks Bmk-dev `REPO_POOL.md` first.
- No removed/disallowed repository is reintroduced without explicit user
  approval.
