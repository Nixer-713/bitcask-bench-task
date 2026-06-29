# Environment Contract: doit-realrepo-001

## Platform

- Execution platform: Docker or AutoDL-compatible Linux container.
- Base image: Python `3.11` or newer compatible with Python `>=3.10`.
- OS: POSIX-like Linux environment.
- Python executable: `${PYTHON_BIN:-python3}`.
- CPU/GPU requirements: CPU only.
- Memory assumptions: 1 GB RAM is sufficient for the hidden oracle.

## Dependency Setup

- System packages: no task-specific system packages required.
- Candidate install command:

```bash
${PYTHON_BIN:-python3} -m pip install -e .
```

- Test dependency command:

```bash
${PYTHON_BIN:-python3} -m pip install pytest
```

- Lockfile or pinned versions: none required for the pilot oracle.

## Network and External Services

- Network: disabled by default during candidate execution.
- Credentials: none.
- External services: none.
- Cache policy: tests must not depend on global pip/cache state beyond installed
  Python packages.

## Evaluation Commands

- Full evaluation harness:

```bash
authoring_private_oracle/doit-realrepo-001/docker/run_eval.sh
```

- Contract check:

```bash
pytest authoring_private_oracle/doit-realrepo-001/oracle/contract_tests -q
```

- Unit tests:

```bash
pytest authoring_private_oracle/doit-realrepo-001/oracle/filtered_unit_tests -q
```

- Integration tests:

```bash
pytest authoring_private_oracle/doit-realrepo-001/oracle/filtered_integration_tests -q
```

- Timeout per command: install 300 seconds; contract 180 seconds; unit 300
  seconds; integration 600 seconds.
- Total timeout: 20 minutes recommended.

## Filesystem Policy

- Candidate mount location: provided by `SUBMISSION_DIR`, default
  `/workspace/submission`.
- Oracle test location: provided by `ORACLE_DIR`, default resolved from this
  private authoring tree.
- Report output location: provided by `REPORT_DIR`, default
  `/workspace/report`.
- Test workspaces: pytest `tmp_path` directories; every oracle test creates its
  own isolated workspace.
- Candidate commands may write only inside each test workspace or accepted
  PRD-defined paths.
- Cleanup behavior: pytest temporary directory cleanup is acceptable; harness
  preserves reports.

## Reproducibility

- Build command: no image build is required for local dry runs; Docker images
  should install Python, pip, and pytest.
- Run command:

```bash
SUBMISSION_DIR=/workspace/submission \
ORACLE_DIR=/oracle \
REPORT_DIR=/workspace/report \
PYTHON_BIN=python3 \
/oracle/../docker/run_eval.sh
```

- Expected original/reference pass rate before candidate evaluation: contract,
  unit, and integration all 100%.
- Known flaky tests: none selected.
- Excluded environment-dependent behavior: network, real mtimes, shell command
  parity, platform-specific tools, external DB backends, and plugin loading.

## Scorer Contract

- The harness consumes `scoring_manifest.json` and the filtered pytest oracle
  mechanically. Stage ids, oracle subpaths, and timeout values are read from
  `scoring_manifest.json`; the selected pytest files contain the assertions.
- It must not add assertions outside the selected pytest tests.
- It must report stage-level pass/fail, exit code, stdout/stderr paths, JUnit
  path when produced, and parsed passed/failed/error/skipped counts.
- It must run contract, unit, and integration stages in isolated pytest
  temporary workspaces.
- It must distinguish install, contract, unit, integration, stdout, stderr,
  exit code, and report-generation failures.
- It must not inspect private implementation files except the public package
  import and CLI entrypoints named by the PRD/API/packaging contracts.
