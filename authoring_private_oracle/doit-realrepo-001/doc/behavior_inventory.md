# Behavior Inventory: pydoit/doit

Status: final public behavior inventory for the completed `doit-realrepo-001`
E2E packet. This file decomposes source behavior into capabilities and state
flows used by the PRD, requirement map, and selected oracle.

## Public Capability Decomposition

| Capability | Input layer | Core state layer | Derived view layer | Mutation/recovery layer | Evidence |
| --- | --- | --- | --- | --- | --- |
| Load task file | `dodo.py`, `-f FILE` | task definitions and task graph | load errors, task names | none | `doc/tasks.rst`, `doc/cmd-run.rst`, `doit/task.py` |
| Parse task metadata | task dictionaries | actions, deps, targets, docs, metadata | list/info output | validation errors | `doc/tasks.rst`, `doit/task.py`, `tests/test_cmd_info.py` |
| Run tasks | selected tasks, filesystem, DB | dependency graph and status | run report, target files | saves/removes success state | `README.rst`, `doc/cmd-run.rst`, `doit/runner.py` |
| Resolve task dependencies | `task_dep`, `file_dep`, selected tasks | DAG order and readiness | skip/execute decisions | bad dependency failure | `doit/runner.py`, `tests/test_cmd_run.py`, `tests/test_runner.py` |
| Detect up-to-date state | file deps, targets, `uptodate`, DB | dependency signatures | status/reasons | rerun after changes | `doc/dependencies.rst`, `tests/test_cmd_info.py` |
| Persist dependency state | DB file, success records | task success and dep signatures | dumpdb/list status/info status | forget/reset/corruption recovery | `doc/cmd-run.rst`, `doit/dependency.py`, `tests/test_dependency.py` |
| List tasks | task graph, optional DB | visible/private/subtask filters | task list, docs, status | none | `doc/cmd-other.rst`, `tests/test_cmd_list.py` |
| Inspect task info | task name, task graph, DB/files | task metadata and status | info report and reasons | none | `doc/cmd-other.rst`, `tests/test_cmd_info.py` |
| Clean artifacts | selected tasks, clean option | target/clean action plan | removed files/report | optional forget state | `doc/cmd-other.rst`, `tests/test_cmd_clean.py` |
| Forget state | selected tasks/all | DB entries | command report | forces future rerun | `doc/cmd-other.rst`, `tests/test_cmd_forget.py` |
| Dump state | DB file | stored task dependency state | readable dump | none | `doc/cmd-other.rst`, `tests/test_cmd_dumpdb.py` |
| Configure behavior | `pyproject.toml`, command args | command options and DB path | changed command behavior | config errors | `doc/configuration.rst` |
| Handle failures | invalid dodo/action/config/DB | prior state and partial run state | non-zero exit/stderr | no false success state | `doc/cmd-run.rst`, `doit/runner.py`, `tests/test_dependency.py` |

Good integration cases should cross the core state, derived view, and
mutation/recovery layers. Examples: `run -> list --status -> dumpdb`,
`run -> clean -> info -> run`, and `run -> local edit -> run -> forget -> run`.

## Four-Layer Model

### Input Layer

- Task definition file, normally `dodo.py`.
- Optional alternate task file selected with `-f`.
- CLI command, selected task names, command options.
- Optional `pyproject.toml` configuration.
- Existing source files, target files, and dependency DB.

### Core State Layer

- Task graph: task names, dependencies, actions, targets, and task metadata.
- Dependency signatures and saved successful-run records.
- File dependency signatures and target existence.
- Effective command/config options.

### Derived View Layer

- `run` stdout/stderr and exit code.
- `list` names/docs/dependencies/status.
- `info` metadata, dependency status, and reasons.
- `dumpdb` persisted state view.
- Generated target files.

### Mutation/Recovery Layer

- `run` creates/updates targets and saves success state.
- Failed actions remove or avoid false success state.
- `clean` removes target files or runs clean actions.
- `forget` removes persisted state.
- Corrupted/malformed inputs fail without corrupting unrelated state.

## Selected Unit Focus Areas

These local behavior areas are represented by the selected private unit oracle.

- CLI entrypoint and command selection.
- Dodo file discovery and `-f` task file selection.
- Task dictionary parsing and validation.
- Action execution subset.
- Task dependency ordering.
- File dependency and target up-to-date checks.
- Persistent state load/save/dump.
- `list` output and status values.
- `info` reasons for rerun.
- `clean` target removal.
- `forget` selected/all behavior.
- Config parsing for DB path and command defaults.
- Failure exit codes and no false success state.

## Selected Integration Dimensions

| Dimension | Crossed modules | Why system-level |
| --- | --- | --- |
| `cross_feature_dataflow` | task loading, run, generated files, list/info/dumpdb | one task file state drives many public outputs |
| `state_accumulation` | run, DB persistence, later run/list/info | prior successful runs change future behavior |
| `global_invariant` | DB state, target files, list status, info reasons, dumpdb | every derived view must agree on task status |
| `error_atomicity` | action failure, DB writes, target files, later info/run | failures must not create false success state |
| `boundary_crossing` | Python task file, filesystem targets, DB file, CLI reports | correctness crosses language/file/state boundaries |
| `operation_order_sensitivity` | run, clean, forget, reset-like flows | command order changes expected state transitions |

## Test Inventory Basis

Potential keep families after PRD boundary decisions:

- `tests/test_cmd_run.py`: run selection, default run, dependency behavior.
- `tests/test_dependency.py`: DB state load/save/dump and corruption handling.
- `tests/test_cmd_clean.py`: clean selected/all/dependency and target behavior.
- `tests/test_cmd_list.py`: list names/docs/dependencies/status.
- `tests/test_cmd_info.py`: info status and reasons.
- `tests/test_cmd_forget.py`: forget selected/all and rerun effects.
- `tests/test_cmd_dumpdb.py`: readable persisted state view.
- `tests/test_runner.py`: up-to-date, skipped, failure, result/getargs flows.

Likely exclude or defer families:

- Reporter plugin discovery and custom reporter internals.
- Tab completion.
- Parallel execution and multiprocessing.
- Platform-specific `strace`.
- Full shell behavior and environment-sensitive subprocess tests.
- All non-selected DB backends.
- Loader/plugin APIs and internal class-level unit tests.

## Boundary Risks

1. Real Python `dodo.py` loading is source-faithful but can execute arbitrary
   code. The public packet resolves this with a constrained static
   task-definition subset.
2. Upstream tests often target internal classes. E2E oracle filtering must keep
   public behavior and exclude private implementation assumptions.
3. Doit's real feature set is broad. A valid task should select a coherent
   core workflow rather than attempt full parity.
4. Exact stdout formatting may be brittle. JSON-compatible report adapters may
   be needed as interface translations and must be public in the PRD.
5. Dependency signatures based on file content vs timestamps must be decided
   explicitly to avoid hidden mtime assumptions.
