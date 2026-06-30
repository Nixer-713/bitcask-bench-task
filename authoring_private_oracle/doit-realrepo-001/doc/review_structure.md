# Structure Review: doit-realrepo-001

Status: `PASS`

This review records the benchmark-structure checks for the completed
`e2e_full_project_task` packet. It summarizes the independent subagent reviews
run during construction and the final mechanical checks.

## Artifact Boundary

| Tree | Status | Notes |
| --- | --- | --- |
| `public_candidate_packet/doit-realrepo-001/` | PASS | Contains only `prd.md`, `public_api_contract.md`, and `packaging_contract.md`. |
| `authoring_private_oracle/doit-realrepo-001/` | PASS | Contains source evidence, requirement map, hidden pytest oracle, harness, reference validation, and candidate reports. |
| Candidate workspaces | PASS | Temporary candidate source directories were not committed. |

## Required E2E Artifacts

| Artifact | Status |
| --- | --- |
| `scoring_manifest.json` | PASS |
| `doc/source_repo.md` | PASS |
| `doc/source_evidence_matrix.md` | PASS |
| `doc/behavior_inventory.md` | PASS |
| `doc/artifact_shape.md` | PASS |
| `doc/requirement_map.md` | PASS |
| `doc/test_inventory.md` | PASS |
| `doc/test_derivability_review.md` | PASS |
| `doc/environment_contract.md` | PASS |
| `doc/oracle_validation_report.md` | PASS |
| `doc/review_structure.md` | PASS |
| `doc/review_fairness.md` | PASS |
| `doc/review_oracle.md` | PASS |
| `oracle/contract_tests/` | PASS |
| `oracle/filtered_unit_tests/` | PASS |
| `oracle/filtered_integration_tests/` | PASS |
| `oracle/pytest.ini` | PASS |
| `docker/Dockerfile` | PASS |
| `docker/run_eval.sh` | PASS |
| `validation/original_report.json` | PASS |
| `validation/model_reports/` | PASS |

## Independent Review Log

| Stage | Reviewer | Verdict | Resolution |
| --- | --- | --- | --- |
| Test inventory and derivability | Beauvoir | PASS with nits | Decision labels and adaptation labels tightened. |
| Test inventory re-review | Huygens | PASS | No blocker. |
| PRD boundary lock | Banach | BLOCK | List-return and state-inspection ambiguities fixed. |
| PRD boundary re-review | Popper | PASS with nit | Stale wording fixed. |
| Public candidate packet | Boyle | BLOCK | `dumpdb` contradiction and state vocabulary fixed. |
| Public packet re-review | Ptolemy | PASS with nit | CLI synopsis tightened. |
| Requirement map | Pasteur | BLOCK | Runtime mapping, action DSL evidence, and stale matrix note fixed. |
| Requirement map re-review | Plato | PASS with nit | Private ignored file was force-added intentionally. |
| Oracle skeleton | Maxwell | BLOCK | Hidden failed-action persistence assertion removed; manifest-driven harness fixed; stderr exact-word checks removed. |
| Oracle skeleton re-review | Maxwell | PASS | No blocker. |
| Reference validation | Kant | BLOCK | Reference accepted `dumpdb --file`; fixed and added contract test. |
| Reference validation re-review | Kant | PASS | Local path cleanup completed. |
| Candidate evaluation | Sagan | PASS | Results and interpretation verified. |

## Mechanical Checks

The final local checks run before the candidate-evaluation commit included:

- `python3 -m json.tool` for scoring and validation JSON files.
- CSV parse for candidate summary.
- JUnit XML parse for all model report XML files.
- `bash -n` for `docker/run_eval.sh`.
- `git diff --check`.
- Public packet leakage scan for private oracle/report/source terms.
- Local path and cache scan for validation artifacts.

## Verdict

The structure is suitable for a private E2E benchmark authoring package. The
candidate-facing packet remains isolated from the hidden oracle.
