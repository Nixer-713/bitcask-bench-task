# Jupytext Validation Summary

Branch: `validation/jupytext`

Evidence commit: `8ee3e8f`

Task: `task/jupytext-realrepo-001`

Rubric size: 34 cases total, 20 unit / 14 system.

Validation assets are kept under `validation/jupytext/` only. This branch contains the reference implementation, scorer, reports, candidate workspaces, score summary, and this validation summary. These assets must not be merged into `main` unless the repository is explicitly converted into a validation package.

## Results

| Run | Unit | System | Unit Score | System Score | Gap pp | Failed Cases | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `reference` | 20/20 | 14/14 | 100.00 | 100.00 | 0.00 | - | satisfiable |
| `codex_agent_001` | 20/20 | 14/14 | 100.00 | 100.00 | 0.00 | - | no_positive_gap_observed |
| `codex_agent_002` | 20/20 | 14/14 | 100.00 | 100.00 | 0.00 | - | no_positive_gap_observed |
| `codex_agent_003` | 20/20 | 14/14 | 100.00 | 100.00 | 0.00 | - | no_positive_gap_observed |

## Qualitative Failure Reasons

- `reference`: no failures. The task is executable and reference-satisfiable for the current public PRD/rubric.
- `codex_agent_001`: no failures.
- `codex_agent_002`: no failures.
- `codex_agent_003`: no failures.

## Interpretation

The reference passed 20/20 unit and 14/14 system cases, so the current Jupytext handoff is reference-satisfiable in this validation branch.

All three independent Codex candidate implementations also passed 20/20 unit and 14/14 system cases. This validation batch therefore shows no positive unit/system gap. It should be recorded as no-positive-gap-observed evidence, not as `core_strong`, `confirmed benchmark`, or `gap-producing` evidence.

This does not make the task invalid. It means the current public PRD/rubric did not distinguish these three code-agent candidates. Future hardening, if any, should remain source-grounded and public; it should not add hidden requirements just to force failures.
