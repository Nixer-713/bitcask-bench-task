# Jupytext 002 Validation Summary

Branch: `validation/jupytext-002`

Task: `task/jupytext-realrepo-002`

Rubric size used in this run: 24 cases

- Unit: 14
- System: 10

Validation assets:

- `validation/jupytext-002/reference/minijupy.py`
- `validation/jupytext-002/score.py`
- `validation/jupytext-002/candidates/codex_agent_*/minijupy.py`
- `validation/jupytext-002/logs/*.log`
- `validation/jupytext-002/reports/*.json`
- `validation/jupytext-002/score_summary.csv`

## Validation Note

Reference validation exposed one rubric ambiguity in `JTU012`: the original case
used a single text file but expected a clean-pair `check` result. The PRD says
missing counterparts make `roundtrip_ok: false`, so the case was corrected in
this validation branch to provide a clean paired `.ipynb`, `.py`, and state
file. This is a rubric alignment fix, not a hidden hardening change.

Main should receive the same `JTU012` rubric patch before future validation.

## Results

| Run | Unit | System | Unit Score | System Score | Gap pp | Failed cases |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| reference | 14/14 | 10/10 | 100.00 | 100.00 | 0.00 | none |
| codex_agent_001 | 11/14 | 10/10 | 78.57 | 100.00 | -21.43 | JTU002, JTU004, JTU005 |
| codex_agent_002 | 13/14 | 10/10 | 92.86 | 100.00 | -7.14 | JTU002 |
| codex_agent_003 | 12/14 | 9/10 | 85.71 | 90.00 | -4.29 | JTU002, JTU003, JTS010 |
| codex_agent_004 | 14/14 | 10/10 | 100.00 | 100.00 | 0.00 | none |
| codex_agent_005 | 13/14 | 10/10 | 92.86 | 100.00 | -7.14 | JTU002 |

## Failure Rates

Candidate-level:

- 1/5 candidates passed all cases.
- 4/5 candidates failed at least one case.
- Candidate failure rate: 80.00%.

Case-run level across five candidates:

- Total failed case-runs: 8/120.
- Overall failure rate: 6.67%.
- Unit failed case-runs: 7/70.
- Unit failure rate: 10.00%.
- System failed case-runs: 1/50.
- System failure rate: 2.00%.

## Qualitative Failure Reasons

- `JTU002` failed in four candidates. The common issue was reporting
  `format: "text"` instead of the PRD-defined `format: "py:percent"` for
  percent scripts.
- `JTU004` and `JTU005` failed in one candidate because missing counterpart
  reporting used a generic `"text"` marker instead of the concrete missing
  path required by the PRD.
- `JTU003` and `JTS010` failed in one candidate because percent writer marker
  formatting omitted the expected public marker JSON shape.

## Interpretation

Reference is satisfiable: 14/14 unit and 10/10 system.

This validation batch does not show positive unit/system gap evidence. All
non-reference candidate gaps are zero or negative: system score is equal to or
higher than unit score. The observed failures are mostly local formatting and
report-shape issues, not system-composition degradation.

Current status:

```text
jupytext-realrepo-002: reference-satisfiable after JTU012 rubric alignment;
candidate failure rate 80%, but no positive unit/system gap observed.
```

Do not claim `core_strong`, `confirmed benchmark`, or `gap-producing` from this
batch.
