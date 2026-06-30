# Oracle And Environment Review: doit-realrepo-001

Status: `PASS`

This review covers hidden oracle executability, scorer/harness behavior,
reference validation, environment constraints, and candidate evaluation
interpretation.

## Oracle Shape

| Component | Status | Notes |
| --- | --- | --- |
| `scoring_manifest.json` | PASS | Defines contract/unit/integration groups, refs, dimensions, timeouts, and fairness rules. |
| `oracle/contract_tests/` | PASS | 4 public package/CLI contract tests. |
| `oracle/filtered_unit_tests/` | PASS | 15 local-feature tests. |
| `oracle/filtered_integration_tests/` | PASS | 8 cross-feature workflow tests. |
| `docker/run_eval.sh` | PASS | Reads manifest task id, stage paths, and timeouts; writes stage reports and `summary.json` before final exit. |
| `docker/Dockerfile` | PASS | Provides minimal Python/pytest evaluation image. |

## Reference Validation

Private reference result:

| Layer | Passed | Total | Pass rate |
| --- | ---: | ---: | ---: |
| Contract | 4 | 4 | 100% |
| Unit | 15 | 15 | 100% |
| Integration | 8 | 8 | 100% |
| Overall | 27 | 27 | 100% |

The upstream `pydoit/doit` source is the behavioral source, but the task exposes
a translated package/API named `minidoit`. A private reference implementation is
therefore used as the oracle satisfiability gate.

## Candidate Evaluation

| Run | Contract | Unit | Integration | Gap pp | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `codex_agent_001` | 4/4 | 14/15 | 8/8 | -6.67 | local stderr-channel failure |
| `codex_agent_002` | 4/4 | 14/15 | 8/8 | -6.67 | local stderr-channel failure |
| `codex_agent_003` | 4/4 | 15/15 | 8/8 | 0.00 | no gap observed |

This is not positive unit/integration gap evidence. The task status is:

```text
doit-realrepo-001: oracle-validated; candidate batch evaluated; no positive gap observed
```

## Environment And Leakage Review

| Check | Verdict |
| --- | --- |
| Network/services/credentials required | PASS: none required |
| Real mtimes used for scoring | PASS: no |
| Local absolute paths in committed reports | PASS: sanitized |
| Candidate source committed | PASS: no |
| Cache artifacts committed | PASS: no `__pycache__`, `.pyc`, `.pytest_cache`, or `.egg-info` |
| Public packet contains hidden oracle terms | PASS: no private oracle/scoring/report references |

## Verdict

The oracle is executable, reference-satisfiable, and produces complete
candidate-evaluation reports. The current evidence does not justify
`core_strong`, `confirmed_benchmark`, or `gap-producing` claims.
