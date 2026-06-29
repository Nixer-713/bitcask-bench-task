# Boundary Decisions: doit-realrepo-001

Status: boundary decisions only. This file locks the deterministic E2E scope
before PRD drafting and upstream test filtering. It does not define final
candidate-facing wording, hidden tests, oracle files, scoring manifests,
reference code, or validation assets.

## Decision Summary

| Topic | Decision |
| --- | --- |
| Task mode | `e2e_full_project_task` |
| Candidate package | `minidoit` |
| CLI invocation | `minidoit` and `python -m minidoit` |
| Task file | restricted `dodo.py` |
| Action model | safe deterministic action DSL |
| V1 commands | `run`, `list`, `info`, `clean`, `forget`, `dumpdb` |
| State file | public JSON state file, default `.minidoit.db.json` |
| Dependency signatures | deterministic file content signatures, not mtimes |
| Report stabilization | JSON modes allowed for `list`, `info`, and `dumpdb` |

## Source-Derived Behavior Kept

These behaviors are kept because they are directly supported by the source
repository docs, source, and tests recorded in `source_repo.md` and
`source_evidence_matrix.md`.

- Task definitions live in a Python task file named `dodo.py` by default.
- Task creators use the `task_<name>()` function convention.
- A task is represented as a dictionary with public fields such as `actions`,
  `file_dep`, `targets`, `task_dep`, `clean`, `uptodate`, and `doc`.
- `run` is the central command and executes selected tasks plus required task
  dependencies in dependency order.
- Previous successful runs affect later up-to-date decisions through persistent
  dependency state.
- File dependencies and missing targets make a task not up-to-date.
- `list` exposes available tasks and task status.
- `info` exposes task metadata, status, dependencies, targets, and reasons a
  task would run.
- `clean` removes generated targets or performs declared clean behavior.
- `forget` removes saved successful-run state.
- `dumpdb` exposes persisted dependency/cache state.
- Failed task execution returns non-zero and must not save a false successful
  state for the failed task.

## Deterministic Adaptations

These adaptations preserve source project intent while making the benchmark
safe, deterministic, and mechanically scoreable. Every adaptation must be
public in the future PRD and traced in the future requirement map.

### Restricted `dodo.py`

V1 keeps the `dodo.py` and `task_<name>()` public shape, but it does not execute
arbitrary Python during task loading.

Allowed:

- Top-level `def task_<name>():` functions.
- Return values that are static Python literals.
- A single task dictionary per task function. The final v1 lock excludes
  list-returned multiple tasks because subtasks, `name`, and `basename` are out
  of scope.
- Literal values for supported task fields.

Excluded from the restricted loader:

- Imports with side effects.
- Function calls used to construct task dictionaries.
- Loops, conditionals, dynamic task generation, generators, decorators, and
  runtime mutation.
- Python callable actions.

Rationale: real `doit` uses Python task files, but live E2E evaluation must not
depend on arbitrary source execution in hidden tests.

### Safe Action DSL

V1 replaces arbitrary shell and Python callable actions with a public safe DSL.

Supported action forms:

- `write PATH TEXT`: create or replace a file with text.
- `append PATH TEXT`: append text to a file, creating it if needed.
- `copy SRC DST`: copy a text file.
- `delete PATH`: remove a file if it exists.
- `fail MESSAGE`: fail the task with a public error message.

Action semantics:

- Actions run in declared order.
- If an action fails, later actions in the same task do not run.
- A failed task does not save successful dependency state.
- Files already written by earlier actions are not automatically rolled back.

Rationale: this keeps ordering, filesystem effects, task failure, and state
interaction while avoiding shell quoting, platform, and environment noise.

### Dependency and State Model

V1 uses deterministic content signatures instead of real file mtimes.

A task is up-to-date only when all of these are true:

- The state file records a prior successful run for the task.
- All declared `file_dep` files exist and have unchanged content signatures.
- All declared `targets` exist.
- `uptodate` does not force a rerun.
- Required task dependencies are themselves up-to-date or have just completed
  successfully in the same run.

Supported `uptodate` values:

- omitted or empty: normal dependency and target checks apply.
- `True`: does not override changed file dependencies or missing targets.
- `False`: forces the task to run.

State file:

- The public default state file is `.minidoit.db.json`.
- A future PRD may expose `--db-file FILE` as the public override.
- The state file should be treated as user-visible for `dumpdb`, but hidden
  tests must only assert fields declared public in the PRD.

Rationale: source `doit` supports multiple DB backends and dependency checkers;
v1 keeps persistent dependency semantics with one deterministic public backend.

### Stable Reports

Human-readable output may be simple and source-inspired, but stable scoring
needs public machine-readable reports.

Allowed interface translations:

- `list --json`
- `info TASK --json`
- `dumpdb --json`

These JSON modes preserve source intent by exposing the same public concepts:
task names, docs, status, dependencies, targets, reasons, and saved state.

## V1 Command Scope

### Included Commands

- `run [TASK ...]`
- `list [--json] [--status]`
- `info TASK [--json]`
- `clean [TASK ...] [--forget]`
- `forget [TASK ...] [--all]`
- `dumpdb [--json]`

### Excluded Commands and Features

Excluded from v1:

- `reset-dep`
- value passing, `getargs`, `value_savers`, and `result_dep`
- parallel execution and multiprocessing
- delayed task creation
- shell command parity
- Python callable actions
- plugin loaders, custom reporters, and tab completion
- `strace`
- dbm/sqlite/custom DB backends
- complete `doit.cfg` legacy INI behavior
- all private source module/class APIs

Exclusions are not claims about source importance. They are v1 scope controls
to preserve a coherent E2E benchmark around task graph, filesystem artifacts,
persistent state, status reports, cleanup, forgetting, and failure behavior.

## Config Boundary

V1 may include a small `pyproject.toml` subset because source docs describe
`[tool.doit]` configuration.

Likely supported public config:

- default task file path
- default DB file path
- command defaults for selected v1 commands

Excluded config:

- plugin config
- reporter config beyond public JSON flags
- per-task config unless future test inventory shows strong public need
- legacy `doit.cfg` INI syntax

## Failure and Atomicity Boundary

The future PRD and oracle should distinguish pre-execution failures from task
execution failures.

Pre-execution failures:

- malformed restricted `dodo.py`
- unsupported task field or action syntax
- invalid config
- missing selected task
- corrupted public state file

Expected behavior:

- command exits non-zero
- writes no target files
- does not update state
- reports a public error through stderr or JSON error mode if defined

Task execution failures:

- `fail MESSAGE` action
- missing input file for `copy`
- failed dependency task

Expected behavior:

- command exits non-zero
- failed task does not save successful state
- later dependent tasks do not run
- earlier successfully completed tasks may remain successful
- files written by earlier actions in the failed task are not automatically
  rolled back unless the future PRD defines a stronger transaction boundary

## Oracle Implications

The future filtered oracle should emphasize workflows where one task state
drives multiple public artifacts.

Likely contract tests:

- package installs
- `minidoit` and `python -m minidoit` work
- commands parse and return documented errors

Likely unit/local tests:

- restricted `dodo.py` parsing
- safe action DSL parsing and execution
- task dependency ordering
- file dependency and target status
- JSON state load/save/dump
- `list`, `info`, `clean`, `forget`

Likely integration/system tests:

- `run -> list --status -> info --json -> dumpdb --json`
- `run -> run again skips -> modify file_dep -> run updates`
- `run -> clean --forget -> info shows not up-to-date -> run`
- `run selected task with task_dep -> target and state invariants`
- failed dependency prevents dependent task and preserves prior success state
- malformed task/config failure leaves target and state unchanged

Do not select upstream tests that require excluded internals or behavior unless
the PRD boundary is revised first.

## Unresolved Until Test Inventory

These items should be answered while building `test_inventory.md` and
`test_derivability_review.md`:

1. Whether `clean` should support dependency-recursive behavior in v1 or only
   explicit selected tasks.
2. Whether private task names and subtasks are included in `list` behavior.
3. Whether `task_dep` should support groups/subtasks or only named tasks.
4. Whether `pyproject.toml` command defaults are required for the filtered
   upstream oracle.
5. Whether `dumpdb` should expose full state JSON or a smaller normalized
   report.
6. Whether source-style textual statuses such as `R`, `U`, and `I` are kept or
   translated to stable strings like `run`, `up_to_date`, and `ignored`.

## Next Step

Create upstream test inventory and derivability triage:

- `authoring_private_oracle/doit-realrepo-001/doc/test_inventory.md`
- `authoring_private_oracle/doit-realrepo-001/doc/test_derivability_review.md`

No public candidate packet or oracle files should be created until the test
inventory confirms that the selected boundaries can support a fair filtered
oracle.
