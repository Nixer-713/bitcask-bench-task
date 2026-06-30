# Artifact Shape: pydoit/doit Candidate

Status: final artifact-shape record. This file began as a planning artifact;
the packet and oracle shapes below have since been realized for
`doit-realrepo-001`.

## Current Source Artifact Shape

| Artifact | Source evidence | Notes |
| --- | --- | --- |
| Python package | `pyproject.toml` | Package `doit`, Python `>=3.10`, console script `doit`. |
| CLI entrypoint | `doit/__main__.py` | Calls `DoitMain().run(sys.argv[1:])`. |
| Task source file | `README.rst`, `doc/tasks.rst` | Default task file is `dodo.py`; task creators return dictionaries. |
| Task graph state | `doit/task.py`, `doit/runner.py` | Tasks include actions, deps, targets, clean, metadata, and status. |
| Dependency DB | `doc/cmd-run.rst`, `doit/dependency.py` | Default `.doit.db`; multiple backends in source. |
| CLI reports | `doc/cmd-run.rst`, `doc/cmd-other.rst` | Run/list/info/clean/forget/dumpdb outputs. |
| Tests | `tests/test_*.py` | Command and dependency tests can seed filtered oracle. |

## Public Candidate Packet Shape

The public packet is:

```text
public_candidate_packet/doit-realrepo-001/
  prd.md
  public_api_contract.md
  packaging_contract.md
```

Candidate-visible documents must define only public behavior. They must not
include upstream test names, hidden case IDs, source file paths required for
implementation, scorer logic, reference code, or expected oracle outputs.

## Private Oracle Shape

The private authoring tree contains:

```text
authoring_private_oracle/doit-realrepo-001/
  scoring_manifest.json
  doc/source_repo.md
  doc/source_evidence_matrix.md
  doc/behavior_inventory.md
  doc/artifact_shape.md
  doc/requirement_map.md
  doc/test_inventory.md
  doc/test_derivability_review.md
  doc/environment_contract.md
  doc/oracle_validation_report.md
  doc/review_structure.md
  doc/review_fairness.md
  doc/review_oracle.md
  oracle/contract_tests/
  oracle/filtered_unit_tests/
  oracle/filtered_integration_tests/
  oracle/pytest.ini
  docker/Dockerfile
  docker/run_eval.sh
  validation/original_report.json
  validation/model_reports/
```

## Candidate Package Contract

The candidate implementation is required to provide:

- An installable Python package named `minidoit`.
- A console script named `minidoit`.
- A constrained task file loader.
- Commands:
  - `run`
  - `list`
  - `info`
  - `clean`
  - `forget`
  - `dumpdb`
- JSON modes for stable scoring where specified in the public API contract.

## Likely Input Artifacts

- `dodo.py` or constrained task file.
- Source files referenced by `file_dep`.
- Existing target files.
- Existing dependency database file.
- Optional `pyproject.toml` subset.
- CLI command-line options and selected task names.

## Likely Output Artifacts

- Generated target files.
- Persistent dependency DB.
- stdout/stderr/exit code.
- `dumpdb` or normalized JSON DB report.
- `list` and `info` reports.

## Persistent State Model

The source supports multiple DB backends. The E2E task uses one deterministic
public state format, `.minidoit.db.json`, with:

- task name
- dependency signatures
- target signatures or existence
- successful-run marker
- saved result marker

This is a deterministic subset of source behavior and is public in the PRD/API
contract. Tests assert only the public fields declared there.

## Oracle Construction Constraints

Selected oracle filtering follows these constraints:

- Prefer upstream command tests that exercise public CLI behavior.
- Convert private internal class tests into public contract tests only when the
  behavior is documented and observable.
- Exclude tests that require source internals, plugin APIs, exact reporters,
  platform-specific `strace`, multiprocessing, or non-selected DB backends.
- Keep at least one integration test for each selected system dimension.
- Validate the original source implementation at the checked commit before
  candidate evaluation.

## Non-Goals For V1 Candidate Shape

These should remain excluded unless later source-boundary review explicitly
changes scope:

- Full `doit` feature parity.
- Plugin architecture and custom loaders.
- Parallel execution.
- `strace`.
- Full subprocess shell portability.
- All DB backend behavior.
- Exact private DB file format.
- Exact internal class names or module layout.
- Network services, credentials, GUI, or external daemons.

## Final State

Boundary decisions, public packet, requirement map, selected oracle,
environment contract, reference validation, and candidate evaluation have been
completed for `doit-realrepo-001`.
