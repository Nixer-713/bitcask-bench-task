# Jupytext 002 Diverse Validation Summary

Branch: `validation/jupytext-002-diverse`

Task commit evaluated: `caba87c`

Task: `task/jupytext-realrepo-002`

Rubric size used in this run: 29 cases

- Unit: 16
- System: 13

Validation assets:

- `validation/jupytext-002-diverse/reference/minijupy.py`
- `validation/jupytext-002-diverse/score.py`
- `validation/jupytext-002-diverse/candidates/diverse_agent_*/minijupy.py`
- `validation/jupytext-002-diverse/logs/diverse_agent_*.log`
- `validation/jupytext-002-diverse/reports/*.json`
- `validation/jupytext-002-diverse/score_summary.csv`

## Scope

This run evaluates the diversified Jupytext 002 rubric after adding:

- `paths` paired-path reporting.
- `to-ipynb --update` output preservation.
- `paths -> pair -> paths -> status` consistency.
- `to-ipynb --update -> pair -> status` consistency.
- text-side pairing metadata fanout through inspect/check/status/state.

The reference implementation and scorer are validation assets only. They must
not be merged into `main`.

## Results

| Run | Unit | System | Unit Score | System Score | Gap pp | Failed cases |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| reference | 16/16 | 13/13 | 100.00 | 100.00 | 0.00 | none |
| diverse_agent_001 | 15/16 | 12/13 | 93.75 | 92.31 | 1.44 | JTU003, JTS010 |
| diverse_agent_002 | 14/16 | 13/13 | 87.50 | 100.00 | -12.50 | JTU004, JTU005 |
| diverse_agent_003 | 16/16 | 13/13 | 100.00 | 100.00 | 0.00 | none |

## Failure Rates

Candidate-level:

- 1/3 candidates passed all cases.
- 2/3 candidates failed at least one case.
- Candidate failure rate: 66.67%.

Case-run level across three candidates:

- Total failed case-runs: 4/87.
- Overall failure rate: 4.60%.
- Unit failed case-runs: 3/48.
- Unit failure rate: 6.25%.
- System failed case-runs: 1/39.
- System failure rate: 2.56%.

## Qualitative Failure Reasons

- `diverse_agent_001` failed `JTU003` and `JTS010` because percent writer
  marker formatting did not include the PRD-required public marker JSON shape
  such as `# %% {"id":"..."}`.
- `diverse_agent_002` failed `JTU004` and `JTU005` because missing counterpart
  reporting used a generic `"text"` marker instead of the concrete missing
  counterpart path required by the PRD, such as `demo.py` or
  `scripts/a/demo.py`.
- `diverse_agent_003` passed all 29 cases.

## Interpretation

Reference is satisfiable: 16/16 unit and 13/13 system.

The diversified rubric creates more candidate failures than the previous local
Jupytext 002 run, but this batch still does not show meaningful positive
unit/system gap evidence. One candidate has a very small positive gap
(`+1.44pp`), one has a negative gap, and one passes all cases. The observed
failures are mostly local public-format/report-shape issues, not clear
system-composition degradation.

Current status:

```text
jupytext-realrepo-002: reference-satisfiable with diversified cases;
candidate failure rate 66.67%; no meaningful positive unit/system gap observed.
```

Do not claim `core_strong`, `confirmed benchmark`, or `gap-producing` from this
batch.
