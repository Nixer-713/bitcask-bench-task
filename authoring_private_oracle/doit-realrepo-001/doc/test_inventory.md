# Upstream Test Inventory: doit-realrepo-001

Status: upstream inventory plus derivability basis for the selected private
oracle. The final oracle is an adapted pytest suite under `oracle/`, with
selected coverage traced in `doc/requirement_map.md`.

## Scan Summary

| Item | Count |
| --- | ---: |
| Source test files scanned | 27 |
| Test classes scanned | approximately 165 |
| Test methods scanned | approximately 673 |
| `keep_core` families | 8 |
| `keep_integration` families | 10 |
| `keep_reasonably_implicit` families | 0 |
| `keep_regression` families | 0 |
| `needs_prd_clarification` families | 0 |
| `exclude_internal` families | 5 |
| `exclude_not_inferable` families | 3 |
| `exclude_conflicts_with_prd` families | 21 |
| `exclude_flaky` families | 0 |
| `exclude_env_dependent` families | 1 |
| `exclude_duplicate` families | 0 |
| Selected oracle tests | 27 |

Source checkout:

- Repository: `pydoit/doit`
- Revision: `1f9cbbce78a93f96a35abf2db5425361e2abf142`

Layer labels follow `benchmark-task-builder/references/test-suite-filtering.md`:
`contract`, `unit`, `integration`, `regression`, and `excluded`.

Decision labels use the required filtering vocabulary:
`keep_core`, `keep_integration`, `keep_reasonably_implicit`,
`keep_regression`, `needs_prd_clarification`, `exclude_internal`,
`exclude_not_inferable`, `exclude_conflicts_with_prd`, `exclude_flaky`,
`exclude_env_dependent`, and `exclude_duplicate`.

## Inventory Table

| Test path | Test name/pattern | Layer | Behavior asserted | PRD support | Source evidence | Decision | Reason | Reviewer notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `tests/test___main__.py` | module execution smoke | contract | `python -m doit` can execute a command. | Public API contract supports `minidoit` and `python -m minidoit`. | `pyproject.toml`; `doit/__main__.py`; `doc/cmd-run.rst` | `keep_core` | Package/CLI contract is public and E2E-critical. | Convert to `minidoit`, not source package name. |
| `tests/test_doit_cmd.py` | default command and command dispatch | contract | Empty CLI defaults to `run`; named subcommands dispatch correctly. | Boundary keeps `run` as central command and includes selected subcommands. | `doc/cmd-run.rst`; `doit/__main__.py`; `doit/cmd_run.py` | `keep_core` | Public CLI behavior. | Avoid private `DoitMain` mocking in final oracle. |
| `tests/test_doit_cmd.py` | version/help output | contract | CLI exposes version/help text. | Public API contract includes minimal help/version behavior. | `doc/cmd-run.rst`; `tests/test_doit_cmd.py` | `keep_core` | Useful package polish selected as public contract behavior. | Assert non-exact help/version only. |
| `tests/test_doit_cmd.py` | command-line vars and loader options | excluded | `x=1` vars, `-k`, loader option placement. | Boundary excludes broad loader behavior and command-line vars. | `tests/test_doit_cmd.py`; `doc/tasks.rst` | `exclude_conflicts_with_prd` | Would expand beyond restricted task/file model. | Do not include in v1 oracle. |
| `tests/test_doit_cmd.py` | config/plugin command loading | excluded | INI/TOML plugin commands and custom command execution. | Boundary excludes plugins and legacy INI. | `doc/configuration.rst`; `tests/test_doit_cmd.py` | `exclude_conflicts_with_prd` | Plugin command loading is out of v1. | Keep only small `pyproject.toml` config if PRD includes it. |
| `tests/test_api.py` | `doit.api.run` and `run_tasks` | excluded | Python API can run tasks from in-memory loaders. | E2E candidate contract is CLI/package, not source Python API parity. | `tests/test_api.py` | `exclude_not_inferable` | Public-ish API exists upstream, but not in v1 boundary. | Reconsider only if public API contract includes it. |
| `tests/test_cmd_run.py` | default run order | integration | Run executes task graph in dependency order and reports executed tasks. | Boundary keeps run, task dependencies, and operation order. | `README.rst`; `doc/cmd-run.rst`; `tests/test_cmd_run.py`; `tests/test_runner.py` | `keep_integration` | Crosses task loading, dependency graph, execution report, and state. | Re-express through restricted `dodo.py` and safe DSL. |
| `tests/test_cmd_run.py` | selected task run | integration | Selecting a task runs only selected task plus required behavior. | Boundary includes selected tasks but not `single` mode. | `doc/cmd-run.rst`; `tests/test_cmd_run.py` | `keep_integration` | Public command selection drives execution graph. | Define selected-task dependency semantics in PRD. |
| `tests/test_cmd_run.py` | `single` mode and positional params | excluded | `single=True` ignores task dependencies; task params pass through. | Boundary excludes value passing/params and does not include `single`. | `tests/test_cmd_run.py`; `doc/cmd-run.rst` | `exclude_conflicts_with_prd` | Not in v1 command scope. | Avoid hidden tests for source-only options. |
| `tests/test_cmd_run.py` | parallel/multiprocessing/thread fallback | excluded | Multiprocess/thread execution and fallback warnings. | Boundary excludes parallel execution. | `README.rst`; `doit/cmd_run.py`; `tests/test_cmd_run.py` | `exclude_conflicts_with_prd` | Environment-sensitive and outside v1. | No parallel oracle. |
| `tests/test_cmd_run.py` | custom/plugin reporters and outfile | excluded | Reporter plugins and output redirection. | Boundary excludes custom reporters; output files not in v1 scope. | `doit/cmd_run.py`; `tests/test_cmd_run.py` | `exclude_conflicts_with_prd` | Reporter plugin behavior is not candidate-visible v1. | JSON report modes are separate interface translations. |
| `tests/test_cmd_list.py` | list names/docs/dependencies | unit | List shows task names, docs, and dependency references. | Boundary keeps `list`; JSON mode planned for stable scoring. | `doc/cmd-other.rst`; `tests/test_cmd_list.py` | `keep_core` | Public derived view from task graph. | Prefer `list --json` in oracle to avoid exact text coupling. |
| `tests/test_cmd_list.py` | list status from dependency DB | integration | Status output reflects DB and task dependency state. | Boundary keeps status and persistent state. | `doc/cmd-other.rst`; `tests/test_cmd_list.py`; `tests/test_dependency.py` | `keep_integration` | Crosses task graph, persisted state, and derived list view. | PRD must define final status values. |
| `tests/test_cmd_list.py` | private tasks, subtasks, grouping, filters | excluded | Private tasks hidden unless requested; subtask filters expand groups. | PRD excludes private tasks, subtasks, and groups. | `doc/cmd-other.rst`; `tests/test_cmd_list.py` | `exclude_conflicts_with_prd` | Source supports it, but v1 deliberately excludes it. | Do not include in hidden oracle. |
| `tests/test_cmd_list.py` | custom templates and unicode names | excluded | Text template formatting and unicode task names. | Not core to boundary; exact text format is not planned. | `tests/test_cmd_list.py` | `exclude_not_inferable` | Could be source-public but not needed for E2E signal. | Unicode may be reintroduced if PRD wants broad text support. |
| `tests/test_cmd_info.py` | info metadata/deps/targets/status | unit | Info exposes task doc, file deps, metadata, and status. | Boundary keeps `info` and planned JSON mode. | `doc/cmd-other.rst`; `tests/test_cmd_info.py` | `keep_core` | Public inspection command. | Exclude source-only fields like `getargs` unless PRD adds them. |
| `tests/test_cmd_info.py` | reasons task would run | integration | Info reports changed/missing deps, missing targets, and uptodate reasons. | Boundary keeps dependency reasons as a derived view. | `doc/cmd-other.rst`; `doc/dependencies.rst`; `tests/test_cmd_info.py` | `keep_integration` | Crosses DB/filesystem state and info report. | PRD must define reason keys or text. |
| `tests/test_cmd_clean.py` | clean selected/all and target removal | integration | Clean removes generated targets or executes clean behavior. | Boundary keeps `clean`; safe DSL can express generated targets. | `doc/cmd-other.rst`; `tests/test_cmd_clean.py` | `keep_integration` | Mutates filesystem artifacts and affects later run/info. | Final oracle should test public files, not mocked clean callbacks. |
| `tests/test_cmd_clean.py` | clean with dependency recursion | excluded | Cleaning a task may also clean task dependencies. | PRD excludes dependency-recursive clean. | `doc/cmd-other.rst`; `tests/test_cmd_clean.py` | `exclude_conflicts_with_prd` | Fair only if PRD includes it; v1 does not. | Do not include in hidden oracle. |
| `tests/test_cmd_clean.py` | clean with forget | integration | Clean can remove task DB state as part of cleanup. | Boundary includes `clean --forget`. | `doc/cmd-other.rst`; `tests/test_cmd_clean.py`; `tests/test_cmd_forget.py` | `keep_integration` | Crosses cleanup, DB mutation, and future up-to-date state. | Re-express with public JSON DB/dumpdb. |
| `tests/test_cmd_forget.py` | forget selected/all | integration | Forget removes successful-run state for selected tasks or all tasks. | Boundary keeps `forget [TASK...] [--all]`. | `doc/cmd-other.rst`; `tests/test_cmd_forget.py` | `keep_integration` | Persistent state mutation affects later run/list/info. | Use public `dumpdb --json` to assert state. |
| `tests/test_cmd_forget.py` | forget groups/subtasks/dependencies | excluded | Forget group and dependency behavior. | PRD excludes groups, subtasks, and dependency-recursive forget. | `tests/test_cmd_forget.py`; `tests/test_cmd_list.py` | `exclude_conflicts_with_prd` | Source-derived but out of v1 scope. | Do not include in hidden oracle. |
| `tests/test_cmd_dumpdb.py` | dump persisted DB | unit | DumpDB prints stored dependency data. | Boundary keeps `dumpdb` with JSON interface translation. | `doc/cmd-other.rst`; `tests/test_cmd_dumpdb.py` | `keep_core` | Public state inspection. | Avoid dbm-specific representation. |
| `tests/test_dependency.py` | JSON DB save/load/remove/dump | unit | Dependency state can be persisted, reloaded, removed, and dumped. | Boundary uses public JSON state file. | `doc/cmd-run.rst`; `doit/dependency.py`; `tests/test_dependency.py` | `keep_core` | State persistence is central. | Keep through public CLI/state, not private `_get/_set`. |
| `tests/test_dependency.py` | file content checker behavior | unit | File content changes make tasks not up-to-date. | Boundary uses deterministic content signatures. | `doc/dependencies.rst`; `tests/test_dependency.py` | `keep_core` | Directly supports deterministic adaptation. | Do not require timestamp-specific logic. |
| `tests/test_dependency.py` | timestamp/custom checkers and all DB backends | excluded | TimestampChecker, custom checker, dbm/sqlite backend matrix. | Boundary excludes mtimes, custom checkers, and non-selected DB backends. | `doc/cmd-run.rst`; `tests/test_dependency.py` | `exclude_conflicts_with_prd` | Contradicts deterministic JSON-only v1. | Keep source evidence only. |
| `tests/test_dependency.py` | missing file dep, missing target, `uptodate` status | integration | Status changes based on file deps, targets, and uptodate. | Boundary keeps these status rules. | `doc/dependencies.rst`; `tests/test_dependency.py`; `tests/test_cmd_info.py` | `keep_integration` | Crosses filesystem, DB, and status reports. | Translate to public status/reason JSON. |
| `tests/test_dependency.py` | result values/get values | excluded | Task values/results are persisted and queried. | Boundary excludes value passing and result dependency. | `doc/dependencies.rst`; `tests/test_dependency.py` | `exclude_conflicts_with_prd` | Out of v1. | No hidden result/value tests. |
| `tests/test_runner.py` | up-to-date skip and failed dependency | integration | Runner skips up-to-date tasks and fails on missing dependencies. | Boundary keeps up-to-date and failure semantics. | `doit/runner.py`; `tests/test_runner.py`; `doc/dependencies.rst` | `keep_integration` | System state controls execution. | Re-express through CLI, not Runner internals. |
| `tests/test_runner.py` | failure stops later tasks and no false success | integration | Failed task prevents later tasks and does not save success. | Boundary keeps task failure behavior. | `doit/runner.py`; `tests/test_runner.py`; `doc/cmd-run.rst` | `keep_integration` | Core error atomicity signal. | Use safe DSL `fail MESSAGE`. |
| `tests/test_runner.py` | `continue`, teardown, getargs, result, multiprocessing | excluded | Advanced runner controls and private reporter lifecycle. | Boundary excludes value passing, teardown, parallel, and private internals. | `tests/test_runner.py` | `exclude_conflicts_with_prd` | Outside v1 and mostly internal. | Do not keep. |
| `tests/test_loader.py` | task function discovery and literal task dicts | unit | Loader discovers `task_*` and task dictionaries. | Boundary keeps restricted `dodo.py`. | `doc/tasks.rst`; `tests/test_loader.py`; `doit/task.py` | `keep_core` | Public task definition shape. | Convert from executing Python to static parse semantics. |
| `tests/test_loader.py` | delayed tasks, decorators, generators, dynamic generation | excluded | Dynamic task creation and create_after behavior. | Boundary excludes dynamic generation. | `tests/test_loader.py`; `doc/tasks.rst` | `exclude_conflicts_with_prd` | Contradicts restricted loader. | No hidden dynamic tests. |
| `tests/test_loader.py` | `DOIT_CONFIG` dict in dodo | excluded | Source dodo can carry config in module globals. | Boundary prefers pyproject subset, not arbitrary dodo globals. | `tests/test_loader.py`; `doc/configuration.rst` | `exclude_conflicts_with_prd` | Would require executing Python/globals. | Use pyproject if config is included. |
| `tests/test_task.py` | task dict validation and supported fields | unit | Invalid/missing fields fail; supported fields initialize task metadata. | PRD defines public restricted-dodo schema and unsupported-field errors. | `doc/tasks.rst`; `doit/task.py`; `tests/test_task.py` | `keep_core` | Rephrased as public restricted-dodo validation, not internal `Task`. | Selected unit oracle covers schema validation. |
| `tests/test_task.py` | params, getargs, value_savers, result_dep, pickle | excluded | Advanced task internals and Python object lifecycle. | Boundary excludes value passing/results and private object APIs. | `tests/test_task.py` | `exclude_conflicts_with_prd` | Out of v1. | Do not keep. |
| `tests/test_action.py` | shell command actions, Python actions, IO capture | excluded | Full source action system. | Boundary replaces actions with safe DSL. | `doc/tasks.rst`; `tests/test_action.py` | `exclude_conflicts_with_prd` | Contradicts action model. | Source intent informs action ordering/failure only. |
| `tests/test_cmdparse.py` | internal command option parser | excluded | Private parser defaults, option objects, help formatting. | Public CLI behavior is defined by PRD/API contracts, not parser internals. | `tests/test_cmdparse.py` | `exclude_internal` | Private implementation detail. | Do not keep directly. |
| `tests/test_cmd_base.py` | command base, loader internals, iterators | excluded | Private command/loader classes and iteration helpers. | Boundary avoids private source APIs. | `tests/test_cmd_base.py` | `exclude_internal` | Internal structure. | Re-express only public load/list/run behavior if needed. |
| `tests/test_control.py` | dispatcher internals | excluded | ExecNode/dispatcher/private scheduling internals. | Boundary tests public run behavior only. | `tests/test_control.py` | `exclude_internal` | Private algorithm/layout. | Do not keep. |
| `tests/test_reporter.py` | reporter classes and exact text formatting | excluded | Console/executed-only/zero/error/json reporter internals. | Boundary excludes custom reporters and allows new JSON modes. | `doit/cmd_run.py`; `tests/test_reporter.py` | `exclude_conflicts_with_prd` | Reporter internals and exact output are not v1 public contract. | Keep public report concepts only. |
| `tests/test_plugin.py` | plugin entrypoints and dictionaries | excluded | Plugin loading and plugin dict behavior. | Boundary excludes plugins. | `tests/test_plugin.py` | `exclude_conflicts_with_prd` | Out of v1. | Do not keep. |
| `tests/test_cmd_completion.py` | bash/zsh completion | excluded | Completion script generation and shell-specific quoting. | Boundary excludes tab completion. | `tests/test_cmd_completion.py` | `exclude_conflicts_with_prd` | Shell/environment dependent and out of v1. | Do not keep. |
| `tests/test_cmd_strace.py` | strace dependency discovery | excluded | Platform-specific strace behavior. | Boundary excludes strace. | `doc/cmd-other.rst`; `tests/test_cmd_strace.py` | `exclude_env_dependent` | Requires OS tool and source feature excluded. | Do not keep. |
| `tests/test_cmd_resetdep.py` | reset dependency command | excluded | Recompute dependencies without execution. | Boundary excludes `reset-dep`. | `doc/cmd-other.rst`; `tests/test_cmd_resetdep.py` | `exclude_conflicts_with_prd` | Out of v1 scope. | Could be v2 hardening if needed. |
| `tests/test_cmd_ignore.py` | ignore command/state | excluded | Ignore tasks in dependency manager. | Boundary excludes `ignore`. | `tests/test_cmd_ignore.py` | `exclude_conflicts_with_prd` | Not selected command. | Do not keep. |
| `tests/test_cmd_help.py` | help formatting and command docs | excluded | Help text specifics. | Boundary has not committed help text. | `tests/test_cmd_help.py` | `exclude_not_inferable` | Exact help formatting would be hidden/low-signal. | Minimal help can be contract if PRD states it. |
| `tests/test_exceptions.py` | exception classes and formatting | excluded | Private exception class behavior. | PRD/API contracts define public errors, not class internals. | `tests/test_exceptions.py` | `exclude_internal` | Private API. | Re-express exit code/stderr only. |
| `tests/test_tools.py` | helper tools: run_once/config_changed/timeout/interactive | excluded | Source helper APIs and runtime tools. | Boundary excludes broad tool helpers. | `doc/dependencies.rst`; `tests/test_tools.py` | `exclude_conflicts_with_prd` | Out of v1. | Some concepts overlap with uptodate but are not selected. |
| `tests/test___init__.py` | initial working directory helper | excluded | Source package init helper. | Not candidate-facing. | `tests/test___init__.py` | `exclude_internal` | Private utility behavior. | Do not keep. |

## Selected Keep Set

The strongest keep candidates are command/state workflows, not private class
tests:

- contract: package install and CLI invocation
- unit: restricted task loading, task schema validation, safe actions, JSON
  state, list/info/dumpdb local behavior
- integration: run/order/dependency state, status reports, clean/forget flows,
  file dependency changes, missing target behavior, and failure atomicity

## Resolved Oracle Construction Decisions

- PRD defines the restricted `dodo.py` literal grammar.
- PRD defines the safe action DSL exactly.
- Public API contract defines JSON schemas for `list --json`, `info --json`,
  and `dumpdb --json`.
- Private tasks, subtasks, groups, recursive clean, and dependency-recursive
  forget are excluded from v1.
- `pyproject.toml` config is included only for `[tool.minidoit]` `task_file`
  and `db_file`.
- PRD/API define status values and reason keys so tests do not rely on source
  text formatting.
