# Candidate Evaluation Report: doit-realrepo-001

- Task: `doit-realrepo-001`
- Mode: `e2e_full_project_task`
- Public packet: `public_candidate_packet/doit-realrepo-001`
- Hidden oracle: `authoring_private_oracle/doit-realrepo-001/oracle`
- Oracle size: 27 tests total; 4 contract, 15 unit, 8 integration
- Reference gate: passed 27/27 before candidate evaluation
- Candidate isolation: each candidate received only the public packet; candidate source workspaces were temporary and are not committed
- Enhanced evidence batch: added `codex_agent_004` through `codex_agent_008`

## Results

| Run | Contract | Unit | Integration | Overall | Gap pp | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `codex_agent_001` | 4/4 | 14/15 | 8/8 | 96.30% | -6.67 | negative gap local failure |
| `codex_agent_002` | 4/4 | 14/15 | 8/8 | 96.30% | -6.67 | negative gap local failure |
| `codex_agent_003` | 4/4 | 15/15 | 8/8 | 100.00% | 0.00 | no gap observed |
| `codex_agent_004` | 4/4 | 15/15 | 8/8 | 100.00% | 0.00 | no gap observed |
| `codex_agent_005` | 4/4 | 15/15 | 8/8 | 100.00% | 0.00 | no gap observed |
| `codex_agent_006` | 4/4 | 14/15 | 8/8 | 96.30% | -6.67 | negative gap local failure |
| `codex_agent_007` | 4/4 | 15/15 | 8/8 | 100.00% | 0.00 | no gap observed |
| `codex_agent_008` | 4/4 | 15/15 | 8/8 | 100.00% | 0.00 | no gap observed |

## Failed Cases

| Run | Failed test | Failure category | Qualitative reason |
| --- | --- | --- | --- |
| `codex_agent_001` | `filtered_unit_tests.test_state_and_status::test_missing_file_dependency_is_task_error` | weak local implementation | missing file dependency error reported on stdout instead of stderr. |
| `codex_agent_002` | `filtered_unit_tests.test_state_and_status::test_missing_file_dependency_is_task_error` | weak local implementation | missing file dependency error reported on stdout instead of stderr. |
| `codex_agent_006` | `filtered_unit_tests.test_state_and_status::test_missing_file_dependency_is_task_error` | weak local implementation | missing file dependency error reported on stdout instead of stderr. |

## Structure Review

A read-only structure/fairness subagent returned `PASS`. It found the public packet to be a real E2E project task, public/private separation clean, source grounding and adaptations traceable, filtered oracle derivable from the public packet, contract/unit/integration grouping reasonable, and the harness mechanically clean.

Residual risk from that review: the private tree includes reference/oracle/model reports and must remain private/internal; current evidence still cannot support `core_strong`.

## Interpretation

This combined candidate evidence does not provide positive unit/integration gap evidence.

- Five candidates passed the full oracle (`27/27`).
- Three candidates had lower unit than integration (`14/15` unit, `8/8` integration), so the observed gap is negative.
- The repeated failure is a local error-channel issue: missing file dependency errors are reported on stdout instead of stderr.
- No run shows the desired high-unit / lower-integration pattern.

Current status:

```text
doit-realrepo-001: oracle-validated; enhanced candidate batch completed; no positive gap observed
```

Do not claim `core_strong`, `confirmed_benchmark`, or `gap-producing` from this evidence.

## Artifacts

- `candidate_eval_summary.csv`: compact tabular summary for `codex_agent_001` through `codex_agent_008`.
- `candidate_eval_summary.json`: structured summary for all eight candidate runs.
- `model_reports/codex_agent_*/`: sanitized harness stage reports.
