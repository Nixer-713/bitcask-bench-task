# Test Derivability Review: doit-realrepo-001

Status: preliminary fairness and derivability review. This file does not select
or copy hidden tests. It records which upstream test intentions can become fair
oracle behavior after PRD drafting.

## Review Inputs

- `doc/source_repo.md`
- `doc/source_evidence_matrix.md`
- `doc/behavior_inventory.md`
- `doc/boundary_decisions.md`
- Upstream test tree at `pydoit/doit`
- Source revision `1f9cbbce78a93f96a35abf2db5425361e2abf142`

## Derivability Standard Applied

A future hidden test is fair only if it satisfies one of these:

- explicitly inferable from the candidate-facing PRD/API/packaging contract;
- reasonably implicit from declared artifact shape and global invariants;
- public source regression that the PRD explicitly includes.

Current review is stricter than "source has a test." A source test that targets
private classes, private reporters, exact text, non-selected features, or
environment-specific behavior is excluded or converted into a public behavior
candidate only after PRD clarification.

## Keepable Public Behavior Families

| Family | Future layer | Source basis | Derivability verdict | PRD requirement needed |
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

## Gray Areas Requiring PRD Clarification

| Area | Why useful | Why not yet fair | Recommended PRD decision |
| --- | --- | --- | --- |
| Private tasks | Source list command hides `_task` by default. | Boundary has not committed private task behavior. | Include only if needed for integration pressure; otherwise exclude. |
| Subtasks and groups | Source supports group/subtask list/forget/clean behavior. | Restricted loader currently excludes dynamic task generation. | Exclude v1 unless static list-return subtasks are explicitly defined. |
| Recursive clean | Source clean can clean dependencies. | Boundary left recursive clean unresolved. | Include a simple `clean --clean-dep` only if tests need it; otherwise selected tasks only. |
| Dependency-recursive forget | Source supports selected/dependency forget variants. | Boundary only committed selected/all forget. | Keep selected/all in v1; defer recursive forget unless PRD adds it. |
| `pyproject.toml` config | Source docs support TOML config. | Exact keys are not chosen. | Include only DB file and task file defaults for v1. |
| Help/version | Source has tests and docs. | Low system value and exact text can be brittle. | Include minimal non-exact help/version only if package contract wants it. |
| Status symbols | Source uses `R`, `U`, `I`, `E` in list status. | Boundary allows stable strings instead. | Prefer JSON strings: `run`, `up_to_date`, `ignored`, `error`. |
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

## Fair Oracle Construction Guidance

When the PRD exists, build oracle tests from the keepable behavior families
using public commands and files only:

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

## Preliminary Integration Dimensions

| Dimension | Candidate workflows |
| --- | --- |
| `cross_feature_dataflow` | restricted dodo task graph drives run/list/info/dumpdb |
| `state_accumulation` | first run updates state; later run/list/info observe up-to-date |
| `global_invariant` | target files, state file, list status, info reasons, and dumpdb agree |
| `error_atomicity` | failed task or malformed input does not save false success state |
| `boundary_crossing` | Python-like task file, safe action DSL, filesystem targets, JSON DB, CLI reports |
| `operation_order_sensitivity` | run -> run, run -> clean, run -> forget, file edit -> run |

## Recommendation

Proceed to PRD drafting only after recording the following PRD decisions:

1. Restricted `dodo.py` grammar and task schema.
2. Safe action DSL syntax and failure semantics.
3. Public JSON schemas for `list`, `info`, and `dumpdb`.
4. Status values and reason keys.
5. Config subset, if any.
6. Final decision on private tasks, subtasks/groups, and recursive clean.

The current source/test evidence supports a fair E2E task, but the hidden oracle
must be built from public behavior translations rather than source-internal
unit tests.
