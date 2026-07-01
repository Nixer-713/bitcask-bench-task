# Benchmark Task Deliverables

This repository contains benchmark task handoff material derived from real
open-source projects.

The active direction follows the updated Bmk-dev workflow:

- prefer full-project E2E tasks over compact mini rewrites;
- give candidates only a public PRD/API/packaging packet;
- keep source evidence, filtered tests, oracle assets, harnesses, and validation
  reports out of the candidate packet;
- check Bmk-dev `REPO_POOL.md` before starting any new source repository.

## REPO_POOL Alignment

The upstream Bmk-dev `REPO_POOL.md` was checked on 2026-07-01. Repositories
listed there as already occupied, retired, or outside scope must not be used for
new local task development unless the user explicitly overrides that rule.

The following prior local task artifacts were removed from this branch because
their sources are explicitly retired or outside the current Python-only pool:

| Removed local task | Source | REPO_POOL status |
| --- | --- | --- |
| `task/bitcask-realrepo-001` | `SarthakMakhija/bitcask` | Non-Python / out of scope |
| `task/xitkit-realrepo-001` | `hoechstleistungshaartrockner/xitkit` | Retired / cannot continue |
| `task/marmite-realrepo-001` and archived Marmite packet | `rochacbruno/marmite` | Non-Python / out of scope |

## Current Local Artifacts

| Artifact | Source project | Status |
| --- | --- | --- |
| `task/copier-realrepo-001` | `copier-org/copier` | Legacy mini-product draft; not aligned to current full-project oracle workflow |
| `task/jupytext-realrepo-001` | `mwouts/jupytext` | Source-grounding/rewrite notes only |
| `task/jupytext-realrepo-002` | `mwouts/jupytext` | Rewritten mini-product packet; no `core_strong` claim |
| `archive/no-gap-observed/jupytext-realrepo-001` | `mwouts/jupytext` | Historical no-gap evidence |
| `public_candidate_packet/doit-realrepo-001` | `pydoit/doit` | E2E public candidate packet |
| `authoring_private_oracle/doit-realrepo-001` | `pydoit/doit` | Authoring/oracle material for local validation; not candidate-visible |

No current task in this repository is claimed as `core_strong`, confirmed
gap-producing, or a confirmed benchmark.

## Deliverable Boundary

Legacy mini-product tasks may contain:

- `prd.md`: public product requirement document shown to model/code agents.
- `rubric.json`: hidden unit/system evaluation definition.
- `doc/source_repo.md`: source-project evidence and adaptation rationale.
- `doc/requirement_map.md`: traceability from PRD requirements to rubric cases.

New full-project tasks should use:

```text
public_candidate_packet/<task-name>/
  prd.md
  public_api_contract.md
  packaging_contract.md

authoring_private_oracle/<task-name>/
  doc/
  oracle/
  docker/
  validation/
```

During live candidate evaluation, candidates must receive only the
`public_candidate_packet`. They must not see filtered tests, scorer/harness
logic, source implementation, reference solutions, reports, or other candidate
outputs.

See `doc/e2e_full_project_pipeline.md` and `doc/repo_pool_alignment.md` for the
current process.

## Local Pipeline Setup

The local Codex environment and this repository both carry the Bmk-dev stage
skills. The main orchestrator is installed and versioned as
`e2e-00-task-synthesizer`; it is the skill that chains Stage 1 through Stage 5.

- `e2e-00-task-synthesizer`
- `e2e-01-candidate-selector`
- `e2e-02-spec-writer`
- `e2e-03-test-filter`
- `e2e-04-task-judge`

Repository copies live under `skills/`. Runtime copies live under
`/Users/nixer/.codex/skills/`.

New candidates should start from `wip/_template/PIPELINE_STATE.md` and append
their selection or retirement result to `CANDIDATES.md`.

After editing a repository skill, run:

```bash
scripts/sync_e2e_skills.sh
```

Then restart Codex so the skill list refreshes.

## Workspace Layout

| Path | Purpose |
| --- | --- |
| `skills/` | Versioned E2E pipeline skill copies for team review and iteration |
| `wip/` | Active task synthesis state, one directory per in-progress task |
| `tasks/` | Qualified tasks only, after the judge marks them complete |
| `candidate-runs/` | Ignored local candidate run outputs |
| `results/` | Ignored local aggregate reports |
| `logs/` | Ignored local pipeline logs |
| `archive/` | Historical, retired, or no-gap materials |
| `task/` | Legacy mini-product task drafts retained for reference only |
