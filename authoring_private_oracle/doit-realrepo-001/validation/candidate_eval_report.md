# Candidate Evaluation Report: doit-realrepo-001

- Task: `doit-realrepo-001`
- Mode: `e2e_full_project_task`
- Public packet: `public_candidate_packet/doit-realrepo-001`
- Hidden oracle: `authoring_private_oracle/doit-realrepo-001/oracle`
- Oracle size: 27 tests total; 4 contract, 15 unit, 8 integration
- Reference gate: passed 27/27 before candidate evaluation
- Candidate isolation: each candidate received only the public packet; candidate
  source workspaces were temporary and are not committed

## Results

| Run | Contract | Unit | Integration | Overall | Gap pp | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `codex_agent_001` | 4/4 | 14/15 | 8/8 | 96.30% | -6.67 | negative local failure |
| `codex_agent_002` | 4/4 | 14/15 | 8/8 | 96.30% | -6.67 | negative local failure |
| `codex_agent_003` | 4/4 | 15/15 | 8/8 | 100.00% | 0.00 | no gap observed |

## Failed Cases

| Run | Failed test | Failure category | Qualitative reason |
| --- | --- | --- | --- |
| `codex_agent_001` | `filtered_unit_tests.test_state_and_status::test_missing_file_dependency_is_task_error` | weak local implementation | Missing file dependency failure returned non-zero but reported the error on stdout instead of stderr. |
| `codex_agent_002` | `filtered_unit_tests.test_state_and_status::test_missing_file_dependency_is_task_error` | weak local implementation | Missing file dependency failure returned non-zero but reported the error on stdout instead of stderr. |
| `codex_agent_003` | none | none | Passed all selected oracle tests. |

## Interpretation

This batch does not provide positive unit/system gap evidence.

- Two candidates had lower unit than integration (`14/15` unit, `8/8`
  integration), so the observed gap is negative.
- One candidate passed the full oracle (`27/27`).
- The repeated failure in `codex_agent_001` and `codex_agent_002` is a local
  error-channel issue, not a system-composition failure.

Current status:

```text
doit-realrepo-001: oracle-validated; candidate batch run completed; no positive gap observed
```

Do not claim `core_strong`, `confirmed_benchmark`, or `gap-producing` from this
evidence.

## Artifacts

- `candidate_eval_summary.csv`: compact tabular summary.
- `candidate_eval_summary.json`: structured summary.
- `model_reports/codex_agent_*/`: sanitized harness stage reports.
