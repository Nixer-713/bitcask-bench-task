# Requirement Map: doit-realrepo-001

Status: PRD/API/packaging traceability map. This document links public
candidate-facing requirements to source evidence and deterministic adaptations.
It does not define or copy oracle tests.

## Public Requirement Table

| Requirement ID | Public requirement | Public packet location | Source evidence / adaptation basis | Adaptation type | Future oracle focus |
| --- | --- | --- | --- | --- | --- |
| REQ-package | Candidate output is an installable Python package named `minidoit` with import path, console script, module execution, version, and editable install support. | `public_candidate_packet/doit-realrepo-001/prd.md#2-artifact-shape`; `public_api_contract.md#package`; `packaging_contract.md` | `DOIT-BEH-001`; source package exposes a CLI entrypoint and module execution. Package name is translated for candidate task isolation. | `interface_translation` | contract |
| REQ-runtime-env | Package supports Python `>=3.10`, editable offline-compatible install, no network/services/credentials/platform tools, arbitrary working directories, and isolated workspace file assumptions. | `packaging_contract.md#python-version`; `packaging_contract.md#installation`; `packaging_contract.md#runtime-constraints`; `packaging_contract.md#candidate-workspace-assumptions` | Source is a Python package with local CLI behavior; E2E evaluation requires deterministic container-friendly runtime constraints. | `deterministic_subset` | contract + environment |
| REQ-cli | CLI supports default `run`, explicit commands, global `--file` / `--db-file`, help, version, stdout/stderr/exit-code behavior. | `prd.md#3-cli-surface`; `public_api_contract.md#cli-entrypoints`; `public_api_contract.md#exit-codes` | `DOIT-BEH-001`, `DOIT-BEH-002`, `DOIT-BEH-016`; source docs define CLI/default run/return-code concepts. | `deterministic_subset` | contract + integration |
| REQ-config | Supports `[tool.minidoit]` `task_file` and `db_file` config keys with CLI override and pre-execution failure on malformed/unsupported config. | `prd.md#4-configuration` | `DOIT-BEH-015`; source supports `pyproject.toml` config. V1 keeps only task/state path defaults. | `deterministic_subset` | unit + integration |
| REQ-task-file | Loads restricted `dodo.py` with top-level `task_<name>()` functions returning exactly one static literal task dictionary. | `prd.md#5-restricted-task-file-format` | `DOIT-BEH-003`, `DOIT-BEH-004`; source task files use Python task creators returning task dictionaries. V1 statically restricts this. | `deterministic_subset` | unit |
| REQ-task-schema | Task dictionaries support `actions`, `file_dep`, `targets`, `task_dep`, `clean`, `uptodate`, `doc`, and `verbosity`; unsupported fields, invalid names, duplicate names, and invalid paths are errors. | `prd.md#5-restricted-task-file-format` | `DOIT-BEH-004`; source task model exposes these fields. V1 excludes dynamic/subtask/value features. | `deterministic_subset` | unit |
| REQ-action-dsl | Safe action DSL supports `write`, `append`, `copy`, `delete`, and `fail` with deterministic order, path rules, and failure stop semantics. | `prd.md#6-safe-action-dsl` | `DOIT-BEH-004`; source supports action-bearing task dictionaries, but V1 intentionally translates shell/Python action execution to safe deterministic public actions. | `deterministic_subset` | unit + integration |
| REQ-state | Uses public `.minidoit.db.json` state with deterministic content signatures, persisted success state, public schema, and optional `--db-file`. | `prd.md#7-task-freshness-and-state`; `public_api_contract.md#state-file` | `DOIT-BEH-006`, `DOIT-BEH-007`; source persists dependency state and uses file dependency checks. V1 uses one JSON backend and content signatures. | `deterministic_subset` | unit + integration |
| REQ-run | `run` executes selected/default tasks with dependencies, skips up-to-date tasks, saves state only after success, and stops dependents after failure. | `prd.md#run`; `public_api_contract.md#run` | `DOIT-BEH-002`, `DOIT-BEH-005`, `DOIT-BEH-008`; source run/default/dependency/failure behavior with safe action execution. | `deterministic_subset` | integration |
| REQ-list | `list` derives task records and optional status from task/state, with deterministic JSON report support. | `prd.md#list`; `public_api_contract.md#list---json`; `public_api_contract.md#list` | `DOIT-BEH-009`, `DOIT-BEH-017`; source list/status behavior plus JSON interface translation. | `interface_translation` | unit + integration |
| REQ-info | `info` reports one task, dependencies, targets, clean policy, status, and stable reason keys as JSON. | `prd.md#info`; `public_api_contract.md#info-task---json`; `public_api_contract.md#info` | `DOIT-BEH-010`, `DOIT-BEH-017`; source info/reasons behavior, translated to stable JSON keys. | `interface_translation` | unit + integration |
| REQ-clean | `clean` removes targets/clean paths or runs safe clean actions; `clean --forget` also removes state for cleaned tasks; no recursive clean in v1. | `prd.md#clean`; `public_api_contract.md#clean` | `DOIT-BEH-011`; source clean removes artifacts and can forget state. V1 excludes recursive/subtask behavior. | `deterministic_subset` | integration |
| REQ-forget | `forget TASK...` removes selected task state; `forget --all` removes all state; it does not remove target files. | `prd.md#forget`; `public_api_contract.md#forget` | `DOIT-BEH-012`; source forget removes dependency DB entries; v1 applies this to JSON state. | `deterministic_subset` | integration |
| REQ-dumpdb | `dumpdb` is state-only and reports normalized state; `dumpdb --json` returns valid public JSON even if task file is absent. | `prd.md#dumpdb`; `public_api_contract.md#dumpdb---json`; `public_api_contract.md#dumpdb` | `DOIT-BEH-013`, `DOIT-BEH-017`; source dumpdb exposes DB state; V1 normalizes JSON output. | `interface_translation` | unit + integration |
| REQ-status-values | Public status/reason vocabulary uses stable strings: `run`, `up_to_date`, `error`, `executed`, `skipped`, `failed`, `success`, and declared reason keys. | `prd.md#9-json-status-values`; `public_api_contract.md#public-status-and-reason-values` | `DOIT-BEH-009`, `DOIT-BEH-010`, `DOIT-BEH-016`; source has status/reason concepts but exact text/symbols are translated. | `interface_translation` | unit + integration |
| REQ-error-atomic | Pre-execution failures write no targets/state; task execution failures do not save false success for failed task and do not run dependents. | `prd.md#10-error-behavior`; `public_api_contract.md#error-contract` | `DOIT-BEH-008`, `DOIT-BEH-016`, `DOIT-BEH-019`; source return-code/failure/state behavior. | `deterministic_subset` | integration |
| REQ-global-invariants | Task file, state file, target files, JSON reports, clean/forget effects, reruns, edits, and failures remain mutually consistent across processes. | `prd.md#11-global-invariants` | `DOIT-BEH-005` through `DOIT-BEH-013`; source behavior is stateful across commands and translated to public JSON reports/state. | `deterministic_subset` | integration |
| REQ-nongoals | Excludes full Python execution, shell/Python actions, dynamic generation, subtasks/groups/private tasks, params/value passing, parallelism, plugins, strace, ignore/reset-dep, non-JSON DB backends, and legacy INI. | `prd.md#12-non-goals` | `DOIT-BEH-014`, `DOIT-BEH-018`, `DOIT-EXC-001` through `DOIT-EXC-005`; explicit v1 exclusions. | `excluded` | fairness guard |

## Requirement To Evidence Coverage

| Requirement ID | Evidence rows |
| --- | --- |
| REQ-package | DOIT-BEH-001 |
| REQ-runtime-env | DOIT-BEH-001 plus E2E deterministic environment adaptation |
| REQ-cli | DOIT-BEH-001, DOIT-BEH-002, DOIT-BEH-016 |
| REQ-config | DOIT-BEH-015 |
| REQ-task-file | DOIT-BEH-003, DOIT-BEH-004 |
| REQ-task-schema | DOIT-BEH-004 |
| REQ-action-dsl | DOIT-BEH-004 plus deterministic safe-action adaptation |
| REQ-state | DOIT-BEH-006, DOIT-BEH-007, DOIT-BEH-019 |
| REQ-run | DOIT-BEH-002, DOIT-BEH-005, DOIT-BEH-008 |
| REQ-list | DOIT-BEH-009, DOIT-BEH-017 |
| REQ-info | DOIT-BEH-010, DOIT-BEH-017 |
| REQ-clean | DOIT-BEH-011 |
| REQ-forget | DOIT-BEH-012 |
| REQ-dumpdb | DOIT-BEH-013, DOIT-BEH-017 |
| REQ-status-values | DOIT-BEH-009, DOIT-BEH-010, DOIT-BEH-016, DOIT-BEH-017 |
| REQ-error-atomic | DOIT-BEH-008, DOIT-BEH-016, DOIT-BEH-019 |
| REQ-global-invariants | DOIT-BEH-005, DOIT-BEH-006, DOIT-BEH-007, DOIT-BEH-009, DOIT-BEH-010, DOIT-BEH-011, DOIT-BEH-012, DOIT-BEH-013 |
| REQ-nongoals | DOIT-BEH-014, DOIT-BEH-018, DOIT-EXC-001, DOIT-EXC-002, DOIT-EXC-003, DOIT-EXC-004, DOIT-EXC-005 |

## Planned Contract Coverage

These are future oracle categories, not selected tests:

- package installs with editable install in Python `>=3.10`;
- `import minidoit` works and exposes `__version__`;
- `minidoit --help`, `minidoit --version`, and `python -m minidoit --help` work;
- default command dispatches to `run`;
- invalid command/config/task inputs exit non-zero with stderr.

Mapped requirements: REQ-package, REQ-runtime-env, REQ-cli, REQ-config,
REQ-error-atomic.

## Planned Unit Coverage

These are future local-behavior test focuses, not selected tests:

- restricted `dodo.py` parser accepts one literal task dict and rejects dynamic constructs;
- task schema validation, duplicate names, invalid names, unsupported fields, and invalid paths;
- safe action DSL parsing and per-action file effects;
- content signature calculation and JSON state load/save;
- `list --json`, `info --json`, and `dumpdb --json` report shapes;
- config parsing and CLI override.

Mapped requirements: REQ-config, REQ-task-file, REQ-task-schema,
REQ-action-dsl, REQ-state, REQ-list, REQ-info, REQ-dumpdb,
REQ-status-values.

## Planned Integration Coverage

These are future cross-feature workflows, not selected tests:

| Integration dimension | Crossed requirements | Candidate workflow |
| --- | --- | --- |
| `cross_feature_dataflow` | REQ-task-file, REQ-run, REQ-list, REQ-info, REQ-dumpdb | one task file drives run output, target files, list status, info reasons, and dumpdb state |
| `state_accumulation` | REQ-run, REQ-state, REQ-list, REQ-info | first run writes state; second run skips; later reports agree |
| `global_invariant` | REQ-global-invariants, REQ-clean, REQ-forget, REQ-dumpdb | target files, state, clean/forget, and reports stay consistent |
| `error_atomicity` | REQ-action-dsl, REQ-run, REQ-error-atomic, REQ-state | failed action prevents false success and dependent tasks |
| `boundary_crossing` | REQ-config, REQ-task-file, REQ-state, REQ-cli | config paths, task file paths, generated files, and JSON state interact |
| `operation_order_sensitivity` | REQ-run, REQ-clean, REQ-forget, REQ-state | run -> rerun, edit dependency -> run, clean -> run, forget -> run |

## Fairness Notes

- Candidate-facing packet does not include upstream source paths, test names,
  hidden oracle details, scorer logic, or reference implementation hints.
- Future oracle tests must use only public CLI, public package import, declared
  task/config/state files, stdout, stderr, exit codes, and generated files.
- Upstream tests that import source internals must be translated into public
  behavior tests or excluded.
- Exact human-readable wording is not a scoring surface unless a future public
  contract explicitly defines it.
- The public JSON state file is a scoring surface only for fields declared in
  `public_api_contract.md`.
- A behavior excluded in REQ-nongoals must not appear in the hidden oracle.

## Next Step

After this map passes review, the next skill step is oracle construction:

- create `scoring_manifest.json`;
- create filtered contract/unit/integration tests under the private oracle tree;
- create environment contract and `run_eval.sh`;
- validate the selected oracle against an implementation before any candidate
  evaluation.
