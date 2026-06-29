# PRD Boundary Lock: doit-realrepo-001

Status: final pre-PRD boundary lock. This document resolves the open questions
from `test_inventory.md` and `test_derivability_review.md` so the next step can
draft the candidate-facing packet without new scope decisions.

No PRD, public candidate packet, oracle tests, scorer, reference implementation,
or validation assets are created in this step.

## Locked V1 Scope

`doit-realrepo-001` remains an `e2e_full_project_task` in which candidates build
an installable Python package named `minidoit`.

V1 measures the public task-automation lifecycle:

- load a restricted `dodo.py`;
- run tasks with dependencies, file dependencies, targets, and safe actions;
- persist deterministic state in `.minidoit.db.json`;
- inspect the same state through `list`, `info`, and `dumpdb`;
- mutate state/artifacts through `clean` and `forget`;
- preserve clear failure and no-false-success behavior.

## Final Decisions From Test Inventory

| Area | Decision | Reason |
| --- | --- | --- |
| Help/version | Include minimal `--help` and `--version` contract checks. | E2E package polish; source has public CLI help/version behavior. |
| Private tasks | Exclude v1 private-task semantics. | Low integration value relative to added scope; hidden tests must not require `_task` behavior. |
| Subtasks/groups | Exclude v1 subtasks and group task expansion. | Source behavior relies on dynamic/generator features outside restricted loader. |
| Recursive clean | Exclude dependency-recursive clean in v1. | Keep clean focused on selected/default tasks and generated targets. |
| Dependency-recursive forget | Exclude v1 recursive forget. | Keep forget focused on selected/all task state. |
| Config | Include a minimal `pyproject.toml` subset. | Source docs support config; DB/task file defaults strengthen cross-boundary behavior. |
| Status values | Use stable JSON strings, not source symbols. | Prevent exact text coupling while preserving public status semantics. |
| Info reasons | Use stable JSON reason keys. | Preserve source intent without depending on exact human-readable phrases. |
| DumpDB shape | Use normalized JSON report. | Public state view without exposing source DB backend layouts. |

## Candidate-Facing Package Contract Defaults

The future public packet should require:

- package name: `minidoit`;
- import path: `minidoit`;
- console script: `minidoit`;
- module execution: `python -m minidoit`;
- install command: `${PYTHON_BIN:-python3} -m pip install -e .`;
- supported Python: `>=3.10`;
- no required network, external services, credentials, or platform-specific
  tools.

## Restricted `dodo.py` Grammar

The PRD should define a static subset of Python task files. Hidden tests may
create user-facing `dodo.py` inputs within this subset.

Allowed structure:

- top-level `def task_<name>():` functions;
- each supported function returns one task dictionary;
- all return values must be Python literals;
- comments and docstrings may appear but are not semantically required.

Allowed task dictionary fields:

- `actions`: required list of safe action strings;
- `file_dep`: optional list of paths;
- `targets`: optional list of paths;
- `task_dep`: optional list of task names;
- `clean`: optional boolean, list of paths, or list of safe action strings;
- `uptodate`: optional boolean or list of booleans;
- `doc`: optional string;
- `verbosity`: optional integer accepted but not required to change behavior.

Task names:

- default task name is the function name after `task_`;
- task names must be non-empty ASCII identifiers using letters, digits, `_`,
  and `-`;
- `=` is invalid in task names;
- duplicate task names are invalid.

Explicitly excluded from task files:

- imports, decorators, loops, conditionals, generators, comprehensions, function
  calls, class definitions, list-returned multiple tasks, and runtime mutation;
- `basename`, `name`, `params`, `pos_arg`, `getargs`, `setup`, `teardown`,
  `calc_dep`, `value_savers`, `meta`, subtasks, and delayed loaders;
- Python callable actions and shell command actions.

## Safe Action DSL

The PRD should expose these action forms exactly:

- `write PATH TEXT`
- `append PATH TEXT`
- `copy SRC DST`
- `delete PATH`
- `fail MESSAGE`

Parsing rules:

- action keyword is the first whitespace-delimited token;
- path arguments are relative paths using `/`;
- path arguments may not be absolute and may not contain `..`;
- remaining text after required path arguments is the text/message payload;
- text payloads are UTF-8 strings written exactly as provided, with a trailing
  newline only when present in the payload.

Execution rules:

- actions run in declared order;
- `write` creates parent directories as needed;
- `append` creates the file if missing;
- `copy` copies text bytes from source to destination and creates destination
  parents as needed;
- `delete` removes a file if it exists and succeeds when already absent;
- `fail` fails the current task with the given message;
- failed task execution stops later actions in that task and dependent tasks.

## Dependency and State Semantics

The PRD should define deterministic content-signature behavior:

- signatures are based on file content, not mtime;
- missing `file_dep` is a pre-task dependency error for the task;
- missing target makes a previously successful task not up-to-date;
- a changed `file_dep` makes the task not up-to-date;
- `uptodate=False` forces rerun;
- `uptodate=True` does not override changed file dependencies or missing
  targets.

State file:

- default path: `.minidoit.db.json`;
- optional CLI override: `--db-file FILE`;
- state records only public task status data needed for `run`, `list`,
  `info`, `forget`, and `dumpdb`;
- the state schema is public for v1;
- hidden tests may inspect state through `dumpdb --json` and may directly read
  `.minidoit.db.json` for fields declared in the PRD.

## Commands To Specify In PRD

Required:

- `minidoit [run] [TASK ...] [--file FILE] [--db-file FILE]`
- `minidoit list [--json] [--status] [--file FILE] [--db-file FILE]`
- `minidoit info TASK [--json] [--file FILE] [--db-file FILE]`
- `minidoit clean [TASK ...] [--forget] [--file FILE] [--db-file FILE]`
- `minidoit forget [TASK ...] [--all] [--file FILE] [--db-file FILE]`
- `minidoit dumpdb [--json] [--db-file FILE]`
- `minidoit --help`
- `minidoit --version`
- `python -m minidoit ...`

Excluded command options:

- `--single`, `--continue`, `--parallel`, custom reporter flags, outfile
  routing, task params, command-line variables, `reset-dep`, `ignore`,
  `strace`, tab completion, plugin commands, and legacy INI config.

## JSON Report Semantics

Use these stable public strings:

- task status: `run`, `up_to_date`, `error`;
- run event status: `executed`, `skipped`, `failed`;
- reason keys:
  - `no_success_state`
  - `changed_file_dep`
  - `missing_file_dep`
  - `missing_target`
  - `uptodate_false`
  - `task_failed`
  - `invalid_task`
  - `invalid_state`

Expected report concepts:

- `list --json`: array of tasks with name, doc, status when requested, file
  dependencies, targets, and task dependencies.
- `info --json`: one task object with name, doc, status, reasons, file
  dependencies, targets, task dependencies, and clean policy.
- `dumpdb --json`: normalized state with task entries and saved dependency
  signatures/status.

Exact key names should be fixed in the PRD and public API contract.

## Config Subset

The PRD should include only this `pyproject.toml` subset:

```toml
[tool.minidoit]
task_file = "dodo.py"
db_file = ".minidoit.db.json"
```

Rules:

- CLI flags override config values.
- Config paths are resolved relative to the config file directory.
- Malformed TOML or unsupported config keys cause pre-execution failure with no
  target or state writes.
- Legacy `doit.cfg` and plugin command config remain excluded.

## Clean and Forget Final Semantics

Clean:

- with no task names, clean all tasks defined in the loaded `dodo.py`;
- with task names, clean only those tasks;
- no dependency-recursive clean in v1;
- if `clean=True`, remove declared targets;
- if `clean` is a list of paths, remove those files;
- if `clean` is a list of safe action strings, execute those safe clean
  actions;
- `clean --forget` also removes state entries for cleaned tasks.

Forget:

- with task names, remove state entries only for those task names;
- with `--all`, remove all task state;
- no group/subtask/dependency-recursive forget in v1;
- forgetting a missing task is a public command error.

## Failure Boundaries

Pre-execution failures write no targets and do not modify state:

- missing task file;
- malformed restricted `dodo.py`;
- unsupported task field/action syntax;
- duplicate task name;
- invalid selected task name;
- malformed config;
- unsupported config key;
- corrupted state file.

Task execution failures:

- do not save success state for the failed task;
- do not run dependent tasks;
- may leave files already written by earlier actions in the failed task;
- may preserve prior successful task state for tasks completed before the
  failure.

## Oracle Direction After PRD

Future oracle tests should be built from public behavior translations:

- contract tests for install, CLI, help/version, and module invocation;
- unit tests for restricted parser, safe action DSL, state file behavior, and
  JSON reports;
- integration tests for run/list/info/dumpdb consistency, run/rerun freshness,
  clean/forget workflows, config path overrides, and failure atomicity.

Do not copy upstream tests that import `doit.*` internals, assert exact source
text formatting, require shell/Python actions, or exercise excluded commands.

## Resolved Items From Prior Docs

The following prior open items are resolved:

- private task names: excluded;
- subtasks/groups: excluded;
- recursive clean: excluded;
- dependency-recursive forget: excluded;
- `pyproject.toml`: included only for `task_file` and `db_file`;
- status values: stable JSON strings;
- info reasons: stable JSON reason keys;
- `dumpdb`: normalized JSON report;
- task schema: restricted literal task dictionary subset.
- list-returned multiple tasks: excluded.

The next skill step is to draft the candidate-facing packet:

- `public_candidate_packet/doit-realrepo-001/prd.md`
- `public_candidate_packet/doit-realrepo-001/public_api_contract.md`
- `public_candidate_packet/doit-realrepo-001/packaging_contract.md`
