# Test Derivability Review: doit-realrepo-001

Status: final fairness and derivability review for the selected hidden oracle.
It records which upstream test intentions became fair oracle behavior after
public PRD/API/packaging contracts were drafted.

## Review Inputs

- `doc/source_repo.md`
- `doc/source_evidence_matrix.md`
- `doc/behavior_inventory.md`
- `doc/boundary_decisions.md`
- Upstream test tree at `pydoit/doit`
- Source revision `1f9cbbce78a93f96a35abf2db5425361e2abf142`

## Derivability Standard Applied

A hidden test is fair only if it satisfies one of these:

- explicitly inferable from the candidate-facing PRD/API/packaging contract;
- reasonably implicit from declared artifact shape and global invariants;
- public source regression that the PRD explicitly includes.

This review is stricter than "source has a test." A source test that targets
private classes, private reporters, exact text, non-selected features, or
environment-specific behavior is excluded or converted into a public behavior
test only after PRD clarification.

## Keepable Public Behavior Families

| Family | Selected layer | Source basis | Derivability verdict | Public requirement support |
| --- | --- | --- | --- | --- |
| Package and CLI invocation | `contract` | `pyproject.toml`, `doit/__main__.py`, `tests/test___main__.py` | explicitly inferable if PRD defines package/CLI | package name, console script, module invocation |
| Default `run` command | `contract` | `doc/cmd-run.rst`, `tests/test_doit_cmd.py` | explicitly inferable | empty command defaults to `run` |
| Restricted task discovery | `unit` | `doc/tasks.rst`, `tests/test_loader.py`, `tests/test_task.py` | explicitly inferable after PRD grammar | static `task_<name>()` and literal task dict schema |
| Safe action execution | `unit` | `doc/tasks.rst`, `tests/test_action.py`, `tests/test_runner.py` | deterministic adaptation | public action DSL and failure semantics |
| Task dependency order | `integration` | `README.rst`, `tests/test_cmd_run.py`, `tests/test_runner.py` | explicitly inferable | selected task and dependency execution semantics |
| File dependency and target freshness | `integration` | `doc/dependencies.rst`, `tests/test_dependency.py`, `tests/test_cmd_info.py` | explicitly inferable | content signatures, missing targets, changed deps |
| Persistent state | `integration` | `doc/cmd-run.rst`, `doit/dependency.py`, `tests/test_dependency.py` | explicitly inferable after adaptation | public `.minidoit.db.json` state semantics |
| List derived view | `unit` or `integration` | `doc/cmd-other.rst`, `tests/test_cmd_list.py` | explicitly inferable if JSON schema defined | `list --json`, optional status |
| Info derived view | `unit` or `integration` | `doc/cmd-other.rst`, `tests/test_cmd_info.py` | explicitly inferable if JSON schema defined | `info --json` task fields, status, reasons |
| Clean mutation workflow | `integration` | `doc/cmd-other.rst`, `tests/test_cmd_clean.py` | explicitly inferable | target removal, clean action subset, optional forget |
| Forget mutation workflow | `integration` | `doc/cmd-other.rst`, `tests/test_cmd_forget.py` | explicitly inferable | selected/all state removal semantics |
| DumpDB state view | `unit` or `integration` | `doc/cmd-other.rst`, `tests/test_cmd_dumpdb.py` | interface translation | `dumpdb --json` public schema |
| Failure atomicity | `integration` | `doc/cmd-run.rst`, `doit/runner.py`, `tests/test_runner.py` | explicitly inferable | pre-execution vs task execution failure boundary |

## Gray Areas Resolved By PRD Boundary

| Area | Why useful | Final fairness decision | PRD decision |
| --- | --- | --- | --- |
| Private tasks | Source list command hides `_task` by default. | Excluded from v1. | Do not include in hidden oracle. |
| Subtasks and groups | Source supports group/subtask list/forget/clean behavior. | Excluded from v1. | Do not include in hidden oracle. |
| Recursive clean | Source clean can clean dependencies. | PRD excludes dependency-recursive clean. | Exclude from v1 hidden oracle. |
| Dependency-recursive forget | Source supports selected/dependency forget variants. | Recursive behavior excluded from v1. | Keep selected/all only. |
| `pyproject.toml` config | Source docs support TOML config. | Included as deterministic subset. | Include only `task_file` and `db_file`. |
| Help/version | Source has tests and docs. | Included as non-exact contract behavior. | Include minimal non-exact help/version. |
| Status symbols | Source uses `R`, `U`, `I`, `E` in list status. | Translated to stable JSON strings. | Use `run`, `up_to_date`, and `error`. |
| Info reason text | Source tests exact human-readable text. | Exact phrasing would be overconstrained. | Use JSON reason keys and membership checks. |

## Exclusion Rationale

The following upstream areas should not enter the v1 oracle unless the boundary
is deliberately revised:

- Full shell command actions and Python callable actions: replaced by safe DSL.
- Multiprocessing, thread runners, parallel execution: excluded for environment
  stability and scope.
- Reporter classes and exact console formatting: private/source-specific; JSON
  reports should be public interface translations.
- Plugin loading, custom commands, loader plugins, and tab completion: outside
  v1 and not core to task graph/state behavior.
- `strace`: OS/tool dependent and explicitly excluded.
- `reset-dep`, `ignore`, value passing, result dependencies, `getargs`,
  `value_savers`, teardown, and delayed task generation: source-valid but
  outside locked v1 scope.
- DB backend matrix and timestamp checker: v1 uses a deterministic public JSON
  state file and content signatures.
- Internal classes such as `Task`, `Runner`, `TaskDispatcher`, parser option
  objects, exception classes, and dependency managers: useful as source
  evidence but not direct candidate-facing oracle.

## Fair Oracle Construction Applied

Oracle tests are built from the keepable behavior families using public commands
and files only:

- install candidate package in an isolated workspace;
- create restricted `dodo.py` files as public user input;
- run `minidoit` commands;
- inspect stdout/stderr/exit code;
- inspect declared target files and `.minidoit.db.json` only through public
  schema or `dumpdb --json`;
- avoid importing candidate private modules except the public CLI/module entry
  point required by the packaging contract.

Do not copy upstream tests verbatim when they import `doit.*` internals or
assert exact source output. Convert their public intent into candidate-facing
  contract/unit/integration tests after PRD support exists.

## Selected Integration Dimensions

| Dimension | Candidate workflows |
| --- | --- |
| `cross_feature_dataflow` | restricted dodo task graph drives run/list/info/dumpdb |
| `state_accumulation` | first run updates state; later run/list/info observe up-to-date |
| `global_invariant` | target files, state file, list status, info reasons, and dumpdb agree |
| `error_atomicity` | failed task or malformed input does not save false success state |
| `boundary_crossing` | Python-like task file, safe action DSL, filesystem targets, JSON DB, CLI reports |
| `operation_order_sensitivity` | run -> run, run -> clean, run -> forget, file edit -> run |

## Final Decision

The source/test evidence supports the selected E2E oracle. The hidden oracle was
built from public behavior translations rather than source-internal unit tests,
and every selected test is traced in `doc/requirement_map.md`.
