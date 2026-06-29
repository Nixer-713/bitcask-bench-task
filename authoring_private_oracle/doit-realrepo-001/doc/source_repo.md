# pydoit/doit Source Grounding

Status: source-grounding only. No PRD, public API contract, packaging contract,
oracle, scorer, reference implementation, or candidate validation has been
created in this step.

## Canonical Source

| Field | Value |
| --- | --- |
| Repository | pydoit/doit |
| URL | https://github.com/pydoit/doit |
| Checked revision | `1f9cbbce78a93f96a35abf2db5425361e2abf142` |
| Intended task id | `doit-realrepo-001` |
| Intended task mode | `e2e_full_project_task` |
| Local analysis checkout | Local throwaway checkout used for analysis; not part of committed evidence |

The local checkout path is analysis context only. Evidence citations below use
repository-relative paths.

## Repository Fit

`doit` is a Python automation tool whose public behavior centers on a
`dodo.py` task definition file. One source state drives multiple public
behaviors: task listing, task execution, dependency checks, target files,
persistent dependency state, task info/reasons, cleanup, forgetting state, and
database dumps. This is a strong fit for an E2E full-project benchmark because
candidate implementations must keep CLI reports, generated files, task graph
execution, and persisted state mutually consistent.

Observed package signals:

- `pyproject.toml` declares package name `doit`, Python `>=3.10`, and console
  script `doit = "doit.__main__:main"`.
- Source directories include `doit/`, `tests/`, and `doc/`.
- The source tree contains representative docs for commands, dependencies,
  configuration, and task definitions, plus broad command/dependency tests.

## Source Evidence Paths

Primary public docs:

- `README.rst`
- `doc/tasks.rst`
- `doc/cmd-run.rst`
- `doc/cmd-other.rst`
- `doc/dependencies.rst`
- `doc/configuration.rst`

Primary implementation evidence:

- `pyproject.toml`
- `doit/__main__.py`
- `doit/cmd_run.py`
- `doit/cmd_list.py`
- `doit/cmd_info.py`
- `doit/cmd_clean.py`
- `doit/cmd_forget.py`
- `doit/cmd_dumpdb.py`
- `doit/dependency.py`
- `doit/runner.py`
- `doit/task.py`

Representative tests:

- `tests/test_cmd_run.py`
- `tests/test_dependency.py`
- `tests/test_cmd_clean.py`
- `tests/test_cmd_list.py`
- `tests/test_cmd_info.py`
- `tests/test_cmd_forget.py`
- `tests/test_cmd_dumpdb.py`
- `tests/test_runner.py`

## Public Source Signals

### Package and CLI

- `pyproject.toml` exposes the console command as `doit =
  "doit.__main__:main"`.
- `doit/__main__.py` delegates command-line arguments to `DoitMain().run(...)`.
- `doc/cmd-run.rst` states that `$ doit` defaults to the `run` command and
  that `-f` selects an alternate dodo file.

### Task Definition Model

- `README.rst` and `doc/tasks.rst` show that tasks are defined in Python files
  named `dodo.py`, normally through `task_*` functions returning dictionaries.
- Task dictionaries expose public task fields such as `actions`, `targets`,
  `file_dep`, `task_dep`, `clean`, `uptodate`, and metadata.
- `doit/task.py` validates task dictionary attributes and stores task state
  such as actions, targets, dependencies, clean actions, and metadata.

### Run, Dependencies, and Persistent State

- `README.rst` describes the central behavior: "Define tasks in Python. Run
  only what changed." It highlights file dependency tracking, result caching,
  and skipping up-to-date tasks.
- `doc/dependencies.rst` defines up-to-date behavior through `file_dep`,
  `targets`, and `uptodate` values. Missing targets and changed dependencies
  make a task not up-to-date.
- `doc/cmd-run.rst` describes persistent dependency state stored in a DB file,
  with default `.doit.db` and documented database backends.
- `doit/runner.py` shows the public run flow: select tasks, skip up-to-date
  tasks, execute actions, save success, and remove success state on failures.

### Introspection and State Mutation Commands

- `doc/cmd-other.rst` documents `list`, including task names, docs, dependency
  display, private task handling, subtasks, and status display.
- `doc/cmd-other.rst` documents `info`, including task metadata, file
  dependencies, targets, status, and reasons a task is not up-to-date.
- `doc/cmd-other.rst` documents `clean`, including target removal through
  `clean=True`, custom clean actions, dry-run, recursive dependency cleanup,
  and optional forget behavior.
- `doc/cmd-other.rst` documents `forget`, which removes successful-run state
  from the dependency DB so tasks can be forced to rerun.
- `doc/cmd-other.rst` documents `dumpdb`, which prints a readable form of the
  internal dependency database.
- `doc/cmd-other.rst` documents `reset-dep`, which recomputes dependency
  metadata without running actions.

### Configuration

- `doc/configuration.rst` documents configuration from `pyproject.toml` under
  `[tool.doit]`, command-specific config under `[tool.doit.commands.<cmd>]`,
  and per-task config under `[tool.doit.tasks.<task>]`.
- Legacy `doit.cfg` INI configuration is also documented, but may be excluded
  or made a later extension to reduce E2E scope.

### Error and Atomicity Signals

- `doc/cmd-run.rst` documents return codes for success, task failure, task
  error, and pre-execution error.
- `doit/runner.py` removes saved success state on task failure before
  reporting failure.
- `tests/test_dependency.py` covers corrupted dependency DB behavior.
- Command tests cover forget/clean/list/info state transitions and can seed an
  oracle inventory after boundary decisions are made.

## Initial Source-Derived Benchmark Shape

Likely candidate-facing package: `minidoit` or `taskflow_doit`.

Likely candidate-visible CLI:

- `run`
- `list`
- `info`
- `clean`
- `forget`
- `dumpdb`

Possible later commands if boundary decisions keep them:

- `reset-dep`
- `status` as an interface translation for stable JSON scoring

Likely public inputs:

- A constrained Python `dodo.py` file containing task dictionaries.
- CLI command and options.
- Optional `pyproject.toml` configuration subset.
- Existing target files and dependency database state.

Likely public outputs:

- Generated target files.
- Command stdout/stderr and exit codes.
- A persistent dependency/cache database file.
- JSON-compatible dump/status output for stable scoring.

## Source-Derived Capability Modules

| Capability | Public input | Public output | Persistent state/artifacts | Downstream effects |
| --- | --- | --- | --- | --- |
| Load task definitions | `dodo.py`, selected file path | task graph or load error | none | drives every command |
| List tasks | task definitions, list options | task names/docs/status | reads DB when status requested | exposes load and DB state |
| Run tasks | selected tasks, actions, deps | report, exit code, target files | updates dependency DB | affects future run/list/info/dumpdb |
| Up-to-date detection | file deps, targets, uptodate, DB | skipped/executed decision | reads DB and filesystem | controls operation order sensitivity |
| Info/reasons | task name, DB/filesystem | task metadata and status reasons | reads DB | exposes why run would execute |
| Clean | selected tasks, clean config | removed targets/clean report | may update or preserve DB | changes future run/info state |
| Forget | selected tasks/all | report | removes DB entries | forces future rerun |
| Dump DB | dependency DB | readable DB output | reads DB | oracle for persisted state consistency |
| Config | `pyproject.toml` subset | option values/effective behavior | none | affects DB path, command behavior |
| Failure handling | invalid dodo/action/config/DB | non-zero exit/stderr | no corrupt success state | protects prior state |

## Adaptation Boundary Draft

These are source-grounding observations, not final PRD decisions.

Likely keep as source-derived:

- Python task file loading from `dodo.py` or selected path.
- Task dictionaries with `actions`, `targets`, `file_dep`, `task_dep`, `clean`,
  `uptodate`, `doc`, and private task naming.
- `run`, `list`, `info`, `clean`, `forget`, and `dumpdb` behavior.
- Persistent dependency state and up-to-date decisions.
- Return-code distinction between success and user/task errors.

Likely simplify as deterministic mini-task adaptation:

- Limit action forms to deterministic shell-like actions such as writing,
  appending, copying, and failing, or to a small safe Python-callable subset.
- Use JSON DB for dependency state rather than supporting dbm/sqlite backends.
- Add JSON report modes for `list`, `info`, or `dumpdb` if needed for stable
  scoring.
- Limit `uptodate` to booleans and simple file/target checks unless tests
  require more.
- Limit config to `pyproject.toml` `[tool.doit]` and command sections.

Likely exclude unless later justified:

- Plugin architecture, custom reporters, tab completion, and loader plugins.
- Parallel execution/multiprocessing and delayed task creation.
- `strace` and platform-specific dependency discovery.
- Full shell portability and complex subprocess environment semantics.
- All database backends except one deterministic state file.
- Complete compatibility with every `doit` parameter, checker, or task loader.

## Open Boundary Questions Before PRD

1. Should the E2E task expose the CLI as `minidoit` or require `python -m
   minidoit`?
2. What exact constrained action language should replace arbitrary shell/Python
   execution while preserving public task semantics?
3. Should task files be real Python `dodo.py` modules, a restricted Python
   subset, or a TOML/JSON interface translation? Real Python is more
   source-faithful but harder to sandbox.
4. Which dependency checks are in v1: file content hash, mtime, target
   existence, `uptodate` booleans, or saved values?
5. Should `dumpdb` expose exact persistent state or a normalized JSON view?
6. Should `clean --forget` and dependency-recursive clean be included in v1?
7. Should `reset-dep` be included or excluded to keep v1 focused?
8. What upstream tests can be filtered into contract/unit/integration oracle
   without importing private implementation assumptions?

## Source-Grounding Conclusion

`pydoit/doit` passes the initial source selection gate. It has public docs,
tests, CLI behavior, persistent state, filesystem artifacts, and natural
operation-order workflows. The next step should be boundary decisions and test
inventory, not PRD drafting.
