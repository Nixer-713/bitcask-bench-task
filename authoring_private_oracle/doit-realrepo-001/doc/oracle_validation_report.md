# Oracle Validation Report: doit-realrepo-001

- Task: `doit-realrepo-001`
- Source repo: `pydoit/doit`
- Checked commit: `1f9cbbce78a9`
- Candidate-facing package: `minidoit`
- Validation implementation: private reference implementation under
  `authoring_private_oracle/doit-realrepo-001/reference/minidoit_project`
- Environment: local Python harness compatible with the Docker/AutoDL contract
- Install command: `${PYTHON_BIN:-python3} -m pip install -e .`
- Harness command:

```bash
SUBMISSION_DIR=authoring_private_oracle/doit-realrepo-001/reference/minidoit_project \
SCORING_MANIFEST=authoring_private_oracle/doit-realrepo-001/scoring_manifest.json \
REPORT_DIR=<report_dir> \
PYTHON_BIN=python3 \
authoring_private_oracle/doit-realrepo-001/docker/run_eval.sh
```

## Scope Note

The upstream `pydoit/doit` implementation is the source of public behavior, but
it does not expose the translated `minidoit` package/API required by the public
candidate packet. This validation therefore uses a private reference
implementation that implements the public PRD/API/packaging contracts exactly.

This is a satisfiability gate for the filtered oracle, not candidate evidence.

## Results

| Layer | Passed | Total | Pass rate | Notes |
| --- | ---: | ---: | ---: | --- |
| Contract | 4 | 4 | 100% | install/import/CLI contract passed |
| Unit | 15 | 15 | 100% | local task parsing, reports, actions, config, state, and errors passed |
| Integration | 8 | 8 | 100% | cross-command state, clean/forget, config boundary, and error atomicity passed |

Overall pass rate: 100% (`27/27` selected oracle tests).

## Failed/Excluded Tests

| Test | Classification | Action | Reason |
| --- | --- | --- | --- |
| None | n/a | n/a | Private reference passed all selected oracle tests |

## Validation Artifacts

- `validation/original_report.json`: raw harness summary for the private
  reference pass.
- `validation/oracle_pass_summary.csv`: compact layer pass summary.

## Verdict

`validation_ready`

Candidate evaluation may begin only in isolated candidate workspaces. Candidate
agents must receive only `public_candidate_packet/doit-realrepo-001` and must
not see this private oracle, reference implementation, reports, source evidence,
or other candidate outputs.
