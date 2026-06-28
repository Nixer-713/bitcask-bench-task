# Copier Validation Summary

## Scope

- Branch: `validation/copier`
- Evidence commit: `2889ba1`
- Task: `task/copier-realrepo-001`
- Program: `minicopier.py`
- Rubric size: 26 cases, 16 unit / 10 system
- Validation assets are under `validation/copier/`.
- Main branch must not receive reference, scorer, candidates, reports, or score
  summaries.

## Evidence Files

- Reference: `validation/copier/reference/minicopier.py`
- Scorer: `validation/copier/score.py`
- Reports:
  - `validation/copier/reports/reference.json`
  - `validation/copier/reports/codex_agent_001.json`
  - `validation/copier/reports/codex_agent_002.json`
  - `validation/copier/reports/codex_agent_003.json`
- Summary CSV: `validation/copier/score_summary.csv`

## Results

| Run | Unit | System | Unit score | System score | Gap pp | Failed cases |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| reference | 16/16 | 10/10 | 100.00 | 100.00 | 0.00 | none |
| codex_agent_001 | 16/16 | 9/10 | 100.00 | 90.00 | 10.00 | `CPS001` |
| codex_agent_002 | 16/16 | 9/10 | 100.00 | 90.00 | 10.00 | `CPS001` |
| codex_agent_003 | 14/16 | 8/10 | 87.50 | 80.00 | 7.50 | `CPU015`, `CPU016`, `CPS001`, `CPS003` |

## Failure Analysis

`codex_agent_001` and `codex_agent_002` both pass all unit cases and fail only
`CPS001`, the copy -> answers file -> check-update system workflow. The concrete
failure is that `dst/.copier-answers.yml` does not contain the public normalized
source-path entry `_src_path: tpl`. This is a cross-feature persistence/report
invariant: copy must write the answers state in a form that later
check-update/update/recopy workflows can consume consistently.

`codex_agent_003` fails local conflict behavior in `CPU015` and `CPU016`, and
also fails related conflict/update system behavior in `CPS003`. This is weaker
local implementation evidence, not clean unit/system gap evidence.

## Interpretation

Reference validation passed 100% unit and 100% system, so the task is
reference-satisfiable under the current scorer.

This batch shows positive unit/system gap evidence for two independent
candidate runs:

- `codex_agent_001`: 100.00 unit vs 90.00 system, gap 10.00 pp.
- `codex_agent_002`: 100.00 unit vs 90.00 system, gap 10.00 pp.

The evidence supports treating `copier-realrepo-001` as a validated candidate
with observed positive gap in this batch. It should still not be claimed as
`core_strong` or a confirmed benchmark until this evidence is reviewed and
accepted.
