# Source Evidence Matrix: pydoit/doit

Status: source-grounding matrix with public packet anchors. The `Tests` column
summarizes selected or excluded oracle families after filtering.

Adaptation types:

- `direct_copy`: source public behavior can be preserved directly.
- `deterministic_subset`: source behavior is narrowed for deterministic local
  scoring.
- `interface_translation`: source public behavior is exposed through a stable
  scoring-oriented format.
- `repo_patch_scope`: not used in this source-grounding step.
- `excluded`: behavior is intentionally out of scope unless later reintroduced.

| Behavior ID | Public behavior | Source evidence path | Evidence type | Adaptation type | PRD location | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| DOIT-BEH-001 | Package exposes a `doit` command-line entrypoint. | `pyproject.toml`; `doit/__main__.py`; `doc/cmd-run.rst` | config + source + docs | `interface_translation` | `public_candidate_packet/doit-realrepo-001/prd.md#2-artifact-shape`; `public_api_contract.md#cli-entrypoints`; `packaging_contract.md` | contract CLI smoke |
| DOIT-BEH-002 | Default command is `run`; `-f` can select a task file. | `doc/cmd-run.rst`; `tests/test_cmd_run.py` | docs + tests | `direct_copy` | `prd.md#3-cli-surface`; `prd.md#run` | run command tests |
| DOIT-BEH-003 | Tasks are defined in Python `dodo.py` task creators returning dictionaries. | `README.rst`; `doc/tasks.rst`; `doit/task.py` | docs + source | `deterministic_subset` | `prd.md#5-restricted-task-file-format` | task loading tests |
| DOIT-BEH-004 | Task dictionaries include actions, file dependencies, targets, task dependencies, clean behavior, and docs/metadata. | `doc/tasks.rst`; `doit/task.py`; `tests/test_runner.py` | docs + source + tests | `deterministic_subset` | `prd.md#5-restricted-task-file-format`; `prd.md#6-safe-action-dsl` | task model tests |
| DOIT-BEH-005 | `run` executes selected tasks and their dependencies in dependency order. | `README.rst`; `doc/cmd-run.rst`; `doit/runner.py`; `tests/test_cmd_run.py`; `tests/test_runner.py` | docs + source + tests | `direct_copy` | `prd.md#run`; `prd.md#11-global-invariants` | run/order integration |
| DOIT-BEH-006 | Up-to-date checks use dependency state, file dependencies, target existence, and `uptodate` values. | `doc/dependencies.rst`; `doit/runner.py`; `tests/test_runner.py`; `tests/test_cmd_info.py` | docs + source + tests | `deterministic_subset` | `prd.md#7-task-freshness-and-state` | dependency/status tests |
| DOIT-BEH-007 | Successful runs persist dependency state in a DB file; later runs can skip up-to-date tasks. | `README.rst`; `doc/cmd-run.rst`; `doit/dependency.py`; `tests/test_dependency.py` | docs + source + tests | `deterministic_subset` | `prd.md#7-task-freshness-and-state`; `public_api_contract.md#state-file` | state accumulation tests |
| DOIT-BEH-008 | Failed tasks return non-zero and do not leave a false successful state. | `doc/cmd-run.rst`; `doit/runner.py`; `tests/test_runner.py` | docs + source + tests | `direct_copy` | `prd.md#10-error-behavior`; `public_api_contract.md#error-contract` | failure atomicity tests |
| DOIT-BEH-009 | `list` reports available tasks, with options for docs, dependencies, status, private tasks, and subtasks. | `doc/cmd-other.rst`; `doit/cmd_list.py`; `tests/test_cmd_list.py` | docs + source + tests | `deterministic_subset` | `prd.md#list`; `public_api_contract.md#list---json` | list/status tests |
| DOIT-BEH-010 | `info` reports task metadata, dependencies, targets, status, and reasons a task is not up-to-date. | `doc/cmd-other.rst`; `doit/cmd_info.py`; `tests/test_cmd_info.py` | docs + source + tests | `interface_translation` | `prd.md#info`; `public_api_contract.md#info-task---json` | info/reasons tests |
| DOIT-BEH-011 | `clean` removes target files or runs clean actions and can clean dependency tasks. | `doc/cmd-other.rst`; `doit/cmd_clean.py`; `tests/test_cmd_clean.py` | docs + source + tests | `deterministic_subset` | `prd.md#clean`; `public_api_contract.md#clean` | clean workflow tests |
| DOIT-BEH-012 | `forget` removes saved dependency state for selected tasks or all tasks. | `doc/cmd-other.rst`; `doit/cmd_forget.py`; `tests/test_cmd_forget.py` | docs + source + tests | `direct_copy` | `prd.md#forget`; `public_api_contract.md#forget` | forget/rerun tests |
| DOIT-BEH-013 | `dumpdb` exposes readable dependency database content. | `doc/cmd-other.rst`; `doit/cmd_dumpdb.py`; `tests/test_cmd_dumpdb.py` | docs + source + tests | `interface_translation` | `prd.md#dumpdb`; `public_api_contract.md#dumpdb---json` | dumpdb invariant tests |
| DOIT-BEH-014 | `reset-dep` recomputes dependency metadata without running actions. | `doc/cmd-other.rst` | docs | `excluded` | `prd.md#12-non-goals` | optional reset-dep tests |
| DOIT-BEH-015 | Config can come from `pyproject.toml` `[tool.doit]` and command/task sections. | `doc/configuration.rst` | docs | `deterministic_subset` | `prd.md#4-configuration` | config tests |
| DOIT-BEH-016 | Return codes distinguish success, task failure, task error, and pre-execution error. | `doc/cmd-run.rst` | docs | `deterministic_subset` | `prd.md#10-error-behavior`; `public_api_contract.md#exit-codes` | CLI error tests |
| DOIT-BEH-017 | Reporters can change stdout format, including a JSON reporter in source. | `doc/cmd-run.rst`; `doit/cmd_run.py`; `tests/test_cmd_run.py` | docs + source + tests | `interface_translation` | `prd.md#9-json-status-values`; `public_api_contract.md#json-report-schemas` | stable report tests |
| DOIT-BEH-018 | Value saving, `getargs`, and task result dependency can pass values between tasks. | `doc/dependencies.rst`; `tests/test_runner.py`; `tests/test_cmd_list.py` | docs + tests | `excluded` | `prd.md#12-non-goals` | optional dataflow tests |
| DOIT-BEH-019 | Corrupted dependency DB raises a database/pre-execution error. | `doit/dependency.py`; `tests/test_dependency.py` | source + tests | `deterministic_subset` | `prd.md#10-error-behavior`; `public_api_contract.md#error-contract` | DB error tests |
| DOIT-EXC-001 | Plugin architecture, custom loaders, custom reporters, and tab completion. | `doc/cmd-run.rst`; source plugin hooks | docs + source | `excluded` | non-goal | excluded |
| DOIT-EXC-002 | Parallel execution and multiprocessing behavior. | `README.rst`; `doit/cmd_run.py` | docs + source | `excluded` | non-goal | excluded |
| DOIT-EXC-003 | `strace` platform-specific dependency discovery. | `doc/cmd-other.rst` | docs | `excluded` | non-goal | excluded |
| DOIT-EXC-004 | Full database backend matrix: dbm, sqlite3, json, and custom codecs. | `doc/cmd-run.rst`; `doit/dependency.py`; `tests/test_dependency.py` | docs + source + tests | `excluded` | non-goal | excluded from v1 |
| DOIT-EXC-005 | Exact shell execution portability and all subprocess environment behavior. | `doc/tasks.rst` | docs | `excluded` | non-goal | excluded from v1 |

## Traceability Notes

- The matrix records source behavior, adaptation class, public packet anchors,
  and selected or excluded test families.
- The concrete selected oracle is listed in
  `doc/requirement_map.md#selected-oracle-coverage`.
- Any behavior marked `deterministic_subset` must be explicitly documented in
  the PRD before tests are allowed to assert it.
- Any behavior marked `interface_translation` must be justified as preserving a
  public source intent while changing output shape for stable scoring.
