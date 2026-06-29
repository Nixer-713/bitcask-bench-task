# MiniDoit PRD

## 1. Overview

Build `minidoit`, an installable Python task automation package. It reads a
restricted `dodo.py` task file, executes file-producing tasks, tracks whether
tasks are up-to-date, and exposes the same task state through command-line
reports and a persistent JSON state file.

The product is intended for small local automation workflows: generated files,
source file dependencies, task dependencies, cleanup, and state inspection. It
must be deterministic and safe to run in isolated evaluation workspaces.

The implementation must be a complete Python package, not a single script.

## 2. Artifact Shape

The submitted project must include a normal editable-install Python package:

```text
pyproject.toml
src/minidoit/__init__.py
src/minidoit/__main__.py
src/minidoit/cli.py
src/minidoit/...
```

The internal module split is up to you, but the package must install, import,
and expose the command-line behavior described here.

## 3. CLI Surface

The package must provide both:

```bash
minidoit ...
python -m minidoit ...
```

Supported commands:

```bash
minidoit [--file FILE] [--db-file FILE] [run] [TASK ...]
minidoit [--file FILE] [--db-file FILE] list [--json] [--status]
minidoit [--file FILE] [--db-file FILE] info TASK [--json]
minidoit [--file FILE] [--db-file FILE] clean [TASK ...] [--forget]
minidoit [--file FILE] [--db-file FILE] forget [TASK ...] [--all]
minidoit [--db-file FILE] dumpdb [--json]
minidoit --help
minidoit --version
```

If no command is provided, `run` is the default command.

`--file` and `--db-file` are global options. They must work before or after the
command name, but before task names. For example, `minidoit --file alt.py run`
and `minidoit run --file alt.py` are both valid. `dumpdb` uses only the state
file and does not load or require a task file.

Default paths:

- task file: `dodo.py`
- state file: `.minidoit.db.json`

`--file FILE` selects a different task file. `--db-file FILE` selects a
different state file. Command-line paths override config values.

## 4. Configuration

If a `pyproject.toml` file exists in the current working directory, support this
subset:

```toml
[tool.minidoit]
task_file = "dodo.py"
db_file = ".minidoit.db.json"
```

Rules:

- config paths are resolved relative to the `pyproject.toml` directory;
- CLI flags override config values;
- unknown keys under `[tool.minidoit]` are errors;
- malformed TOML is an error;
- no legacy INI config or plugin command config is required.

## 5. Restricted Task File Format

`minidoit` loads tasks from a restricted Python-looking `dodo.py` file.

Allowed structure:

- top-level functions named `task_<name>()`;
- each task function returns exactly one task dictionary;
- all return values must be static Python literals;
- comments and docstrings may appear.

Not allowed:

- imports;
- decorators;
- loops, conditionals, comprehensions, generators, classes, and runtime
  mutation;
- function calls inside returned task dictionaries;
- returning multiple task dictionaries;
- dynamic task generation;
- arbitrary Python callable actions;
- shell command actions.

Task names:

- default task name is the function name after `task_`;
- names must contain only ASCII letters, digits, `_`, and `-`;
- names must not be empty and must not contain `=`;
- duplicate task names are errors.

Allowed task dictionary fields:

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `actions` | list of safe action strings | yes | actions executed in order |
| `file_dep` | list of relative paths | no | source files that affect freshness |
| `targets` | list of relative paths | no | files expected after successful run |
| `task_dep` | list of task names | no | tasks that must run or be up-to-date first |
| `clean` | bool, list of paths, or list of safe action strings | no | cleanup behavior |
| `uptodate` | bool or list of bools | no | `False` forces rerun; `True` does not override file/target checks |
| `doc` | string | no | task description shown in reports |
| `verbosity` | integer | no | accepted for compatibility; no required behavior change |

Unsupported fields are errors.

All paths in `file_dep`, `targets`, and path-based `clean` entries must be
relative workspace paths using `/`. Absolute paths and paths containing `..`
are invalid.

## 6. Safe Action DSL

Task `actions` and safe clean actions use this DSL:

```text
write PATH TEXT
append PATH TEXT
copy SRC DST
delete PATH
fail MESSAGE
```

Parsing rules:

- the action keyword is the first whitespace-delimited token;
- path arguments are relative paths using `/`;
- absolute paths and paths containing `..` are invalid;
- remaining text after required path arguments is the text or failure message;
- text is UTF-8 and is written exactly as provided.

Execution rules:

- actions run in declared order;
- `write` creates parent directories and replaces the file content;
- `append` creates parent directories and appends to the file, creating it if
  missing;
- `copy` creates destination parents and copies the source file content;
- `delete` removes a file if present and succeeds when the file is absent;
- `fail` fails the current task with the given message;
- if an action fails, later actions in that task do not run.

## 7. Task Freshness and State

`minidoit` must track task state in a public JSON state file. The default state
file is `.minidoit.db.json`.

State must be deterministic across processes. File freshness uses file content
signatures, not modification times.

A task is up-to-date only when all are true:

- the state file records a prior successful run for the task;
- all declared `file_dep` files exist and have unchanged content signatures;
- all declared `targets` exist;
- `uptodate` does not force rerun;
- required task dependencies are up-to-date or have completed successfully in
  the same run.

Freshness rules:

- missing `file_dep` is an error for the task;
- missing target makes a task not up-to-date;
- changed file dependency makes a task not up-to-date;
- `uptodate=False` forces rerun;
- `uptodate=True` does not override changed file dependencies or missing
  targets.

The state file schema is public. It must be JSON and must contain enough task
entries to support `run`, `list`, `info`, `forget`, and `dumpdb`. The exact
schema is specified in the public API contract.

## 8. Command Behavior

### `run`

Runs selected tasks. With no task names, runs all tasks in deterministic task
name order after respecting dependencies. With task names, runs those tasks and
their task dependencies.

For each task:

- run dependencies first;
- skip the task if it is up-to-date;
- execute actions in order if it must run;
- save successful state only after all actions succeed;
- do not run dependent tasks if a dependency fails.

Human stdout may be concise, but it must distinguish executed, skipped, and
failed tasks.

### `list`

Lists tasks from the task file. With `--status`, include each task status.

`list --json` must print JSON with task objects containing task name, doc,
dependencies, targets, and status when requested.

### `info`

Shows one task. It must include task name, doc, file dependencies, targets, task
dependencies, clean policy, current status, and reasons that explain why the
task would run or why it is up-to-date.

`info TASK --json` must print this information as JSON.

### `clean`

With no task names, clean all tasks. With task names, clean only those tasks.
V1 does not clean task dependencies recursively.

Clean behavior:

- `clean=True`: remove declared targets;
- `clean` as a list of paths: remove those files;
- `clean` as a list of safe action strings: execute those safe actions.

`clean --forget` also removes state entries for cleaned tasks.

### `forget`

Removes saved state without changing target files.

- `forget TASK ...`: remove state entries for exactly those tasks;
- `forget --all`: remove all task state;
- forgetting an unknown task is an error.

### `dumpdb`

Prints a normalized view of the JSON state. `dumpdb` is state-only: it does not
load `dodo.py`, does not validate task definitions, and does not require the
task file to exist. `dumpdb --json` must print the public state object as JSON.

## 9. JSON Status Values

Use these stable strings:

- task status: `run`, `up_to_date`, `error`;
- run event status: `executed`, `skipped`, `failed`.
- persisted state task result: `success`.

Reason keys:

- `no_success_state`
- `changed_file_dep`
- `missing_file_dep`
- `missing_target`
- `uptodate_false`
- `task_failed`
- `invalid_task`
- `invalid_state`

Reports may include additional explanatory strings, but tests and integrations
will rely on the stable keys above.

## 10. Error Behavior

Pre-execution errors must exit non-zero, write no target files, and not update
the state file:

- missing task file;
- malformed task file;
- unsupported task field or action;
- duplicate task name;
- invalid selected task;
- malformed config;
- unsupported config key;
- corrupted state file;
- invalid path escaping the workspace.

Task execution failures:

- exit non-zero;
- do not save success state for the failed task;
- do not run dependent tasks;
- may preserve successful state for tasks completed earlier in the same run;
- may leave files already written by earlier actions in the failed task.

## 11. Global Invariants

- The loaded task file is the source of truth for `run`, `list`, `info`,
  `clean`, and `forget`.
- The state file is the source of truth for `dumpdb`.
- State survives across separate command invocations.
- `list --status`, `info --json`, `dumpdb --json`, target files, and the state
  file must agree after runs, cleans, forgets, failures, and file edits.
- Re-running without changed inputs must skip up-to-date tasks.
- Editing a file dependency must make dependent tasks runnable again.
- Cleaning targets must make affected tasks runnable again.
- Forgetting state must make affected tasks runnable again even if files did
  not change.
- No command may depend on real file modification times.

## 12. Non-Goals

Do not implement:

- full Python task execution;
- shell command actions;
- Python callable actions;
- dynamic task generation;
- subtasks, groups, private tasks, `basename`, or explicit `name` fields;
- task parameters, positional arguments, result passing, `getargs`,
  `value_savers`, `setup`, `teardown`, or calculated dependencies;
- parallel execution;
- plugin systems, custom reporters, tab completion, `strace`, `ignore`, or
  `reset-dep`;
- dbm/sqlite/custom state backends;
- legacy INI config;
- network access, credentials, external daemons, or platform-specific tools.

## 13. Evaluation Style

Evaluation will install the submitted package and exercise only the public
behavior described in this PRD and the companion public API and packaging
contracts. It will use isolated temporary workspaces, command-line invocations,
public JSON reports, generated files, and the declared public state file.

Do not rely on access to any original implementation, private source layout, or
undocumented behavior.
