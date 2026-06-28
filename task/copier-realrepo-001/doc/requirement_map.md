# Copier Requirement Map

## Public Requirements

| Requirement ID | Public behavior |
| --- | --- |
| `REQ-cli` | `minicopier.py` exposes `copy`, `recopy`, `update`, and `check-update`; success prints JSON and failure is nonzero with stderr. |
| `REQ-config` | Parses `copier.yml` / `copier.yaml` with supported settings and question defaults. |
| `REQ-answers` | Resolves answers from previous answers, defaults, data file, and repeated `--data` with documented precedence. |
| `REQ-answers-file` | Writes configured answers file with `_src_path`, Git `_commit` when available, and non-secret answers; `--answers-file` locates custom answer files for later commands. |
| `REQ-render` | Renders template-suffix files, path segments, and simple `{{ variable }}` content. |
| `REQ-exclude-skip` | Applies `_exclude`, `--exclude`, `_skip_if_exists`, and `--skip` to destination-relative paths. |
| `REQ-pretend` | `--pretend` reports planned work and writes no files. |
| `REQ-local-git` | Supports local Git template refs/tags and deterministic semver-like latest tag selection. |
| `REQ-copy` | `copy` creates or updates a destination, writes rendered files and answers, and handles unsafe tasks. |
| `REQ-recopy` | `recopy` re-renders from stored template source/ref and answers, discarding local evolution. |
| `REQ-check-update` | `check-update --json` reports current/latest refs and update availability without writing files. |
| `REQ-update` | `update` compares old render, current destination, and new render to write updates or public conflicts. |
| `REQ-conflict` | Update conflict styles `inline` and `rej` have public file/report behavior. |
| `REQ-tasks-migrations` | Supports safe `write`/`append` tasks and migrations gated by `--trust`; `--skip-tasks` skips tasks. |
| `REQ-subdirectory` | `_subdirectory` limits the rendered template tree while keeping root config/answers behavior. |
| `REQ-error-atomic` | Failed commands and pretend commands leave public artifacts unchanged. |
| `REQ-invariants` | Answers, template refs, rendered files, answers file, update decisions, reports, and atomicity stay mutually consistent. |
| `REQ-non-goals` | Excludes remote templates, full Jinja2, shell execution, symlinks/binary/permissions, exact Copier internals, and Git index behavior. |

## Source Grounding Notes

| Requirement | Source-derived basis | Mini-task adaptation |
| --- | --- | --- |
| `REQ-cli` | `copier/_cli.py` documents public `copy`, `recopy`, `update`, and `check-update` command surfaces. | Stable JSON stdout is required for scoring. |
| `REQ-config` | `docs/configuring.md` and `copier/_template.py` define template config, questions, answers file, exclude, skip, tasks, migrations, and subdirectory settings. | Config grammar is a deterministic subset. |
| `REQ-answers` | `docs/configuring.md`, `copier/_cli.py`, and `copier/_user_data.py` define data, data-file, defaults, and prior answers flow. | Only non-interactive answers are required. |
| `REQ-answers-file` | `docs/configuring.md`, `copier/_main.py`, `copier/_subproject.py`, and `tests/test_answersfile.py` cover stored answers and template metadata. | YAML-like public shape is fixed. |
| `REQ-render` | `README.md`, `docs/creating.md`, `tests/test_copy.py`, and `copier/_main.py` show rendered contents and paths. | Full Jinja is reduced to simple substitution. |
| `REQ-exclude-skip` | `docs/configuring.md`, `tests/test_copy.py`, `tests/test_exclude.py`, and `_main.py` cover exclude/skip. | Glob grammar is simplified and public. |
| `REQ-pretend` | `docs/configuring.md`, `tests/test_copy.py`, `tests/test_output.py`, and `tests/test_tasks.py` cover no-write pretend behavior. | JSON planned writes are a scoring adaptation. |
| `REQ-local-git` | `docs/generating.md`, `docs/configuring.md`, `copier/_cli.py`, and `tests/test_copy.py` cover `--vcs-ref` and tag selection. | Only local Git repos are supported. |
| `REQ-copy` | Public docs and `tests/test_copy.py` cover copy behavior. | Interactive prompts are removed. |
| `REQ-recopy` | `docs/generating.md`, `copier/_main.py`, and `tests/test_recopy.py` cover recopy behavior. | Deterministic non-interactive recopy only. |
| `REQ-check-update` | `docs/updating.md`, `copier/_cli.py`, and `tests/test_check_update.py` cover update availability. | Stable JSON is required. |
| `REQ-update`, `REQ-conflict` | `docs/updating.md`, `copier/_main.py`, and `tests/test_updatediff.py` cover update and conflicts. | Exact Copier merge algorithm is replaced by a documented three-way subset. |
| `REQ-tasks-migrations` | `docs/configuring.md`, `tests/test_tasks.py`, `tests/test_migrations.py`, and `_main.py` cover unsafe feature gating. | Shell execution is replaced by safe `write`/`append` actions. |
| `REQ-subdirectory` | `docs/configuring.md`, `copier/_main.py`, and `tests/test_subdirectory.py` cover subdirectory rendering. | One path setting is supported. |
| `REQ-error-atomic` | `tests/test_cleanup.py`, `tests/test_updatediff.py`, and `_main.py` cover cleanup/no partial writes. | Atomicity is made explicit for all mini-task write commands. |

## Unit Coverage

| Case ID | Focus | Requirement refs |
| --- | --- | --- |
| `CPU001` | Parse config questions/settings | `REQ-config` |
| `CPU002` | Data precedence from defaults, data file, and `--data` | `REQ-answers`, `REQ-render` |
| `CPU003` | Answers file path and secret exclusion | `REQ-answers-file`, `REQ-answers` |
| `CPU004` | Template content rendering | `REQ-render` |
| `CPU005` | Template path rendering | `REQ-render` |
| `CPU006` | Exclude patterns | `REQ-exclude-skip` |
| `CPU007` | Skip-if-exists patterns | `REQ-exclude-skip` |
| `CPU008` | Pretend no-write report | `REQ-pretend`, `REQ-error-atomic` |
| `CPU009` | Git `--vcs-ref` selection | `REQ-local-git`, `REQ-copy` |
| `CPU010` | `check-update --json` | `REQ-check-update`, `REQ-local-git` |
| `CPU011` | Trust gate for tasks | `REQ-tasks-migrations`, `REQ-error-atomic` |
| `CPU012` | Subdirectory rendering | `REQ-subdirectory`, `REQ-render` |
| `CPU013` | Malformed config atomicity | `REQ-config`, `REQ-error-atomic` |
| `CPU014` | Overwrite protection atomicity | `REQ-copy`, `REQ-error-atomic` |
| `CPU015` | Inline conflict output | `REQ-update`, `REQ-conflict` |
| `CPU016` | Reject conflict output | `REQ-update`, `REQ-conflict` |

## System Coverage

| Case ID | System dimension | Crossed modules | Requirement refs |
| --- | --- | --- | --- |
| `CPS001` | `cross_feature_dataflow` | copy -> rendered files -> answers file -> check-update | `REQ-copy`, `REQ-render`, `REQ-answers-file`, `REQ-check-update`, `REQ-invariants` |
| `CPS002` | `state_accumulation` | copy v1 -> update v2 -> files and answers advance | `REQ-local-git`, `REQ-copy`, `REQ-update`, `REQ-answers-file` |
| `CPS003` | `operation_order_sensitivity` | copy -> local edit -> update conflict | `REQ-update`, `REQ-conflict`, `REQ-error-atomic` |
| `CPS004` | `state_accumulation` | copy -> local edit -> recopy discards local evolution | `REQ-copy`, `REQ-recopy`, `REQ-answers-file` |
| `CPS005` | `global_invariant` | data-file + data -> render -> answers -> recopy | `REQ-answers`, `REQ-render`, `REQ-recopy`, `REQ-invariants` |
| `CPS006` | `boundary_crossing` | exclude/skip/pretend across copy and update | `REQ-exclude-skip`, `REQ-pretend`, `REQ-update` |
| `CPS007` | `boundary_crossing` | tasks/migrations trust gate and skip-tasks | `REQ-tasks-migrations`, `REQ-copy`, `REQ-update` |
| `CPS008` | `boundary_crossing` | subdirectory template copy/update paths | `REQ-subdirectory`, `REQ-local-git`, `REQ-update` |
| `CPS009` | `global_invariant` | secret answers render files but are omitted from answers | `REQ-answers`, `REQ-answers-file`, `REQ-render` |
| `CPS010` | `error_atomicity` | malformed update leaves destination unchanged | `REQ-update`, `REQ-error-atomic`, `REQ-invariants` |

## Fairness Notes

- Rubric cases must be inferable from `prd.md`.
- Tests observe only stdout/stderr, exit code, generated files, answers files,
  local Git template repositories created by the scorer, and public JSON reports.
- The scorer must not inspect private implementation files or internal objects.
- No remote network templates, arbitrary shell tasks, full Jinja2, symlinks,
  binary files, exact Copier merge internals, or Git index behavior are tested.
- Real local Git repositories are in scope because PRD publicly requires them.

## Rubric Adapter Contract

The scorer for this task consumes these public adapter fields mechanically:

- `setup_files`: create text files before the case runs.
- `setup_git`: create local Git template repositories, commit each listed file
  tree, and tag commits as specified. These repositories are test inputs, not
  candidate-visible hidden state.
- `steps`: run `python minicopier.py` with the listed `args` in order.
- `steps[].expect_error`: the command must exit nonzero.
- `steps[].write_file`: mutate a public destination file between commands to
  model user edits.
- `stdout_json_contains`: parse a command stdout JSON object by step index and
  check subset containment.
- `file_contains`, `file_not_contains`, `file_exists`, `file_not_exists`: check
  public filesystem artifacts defined by the PRD.
- `file_contains_any_order`: same as `file_contains`; ordering of listed
  substrings is not significant.

The scorer must not inspect implementation internals, private files outside the
case workspace, or anything not named by PRD/rubric public behavior.
