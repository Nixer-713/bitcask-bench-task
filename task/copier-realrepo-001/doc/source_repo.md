# Copier Source Grounding

## Canonical Source

- Repository: `copier-org/copier`
- URL: `https://github.com/copier-org/copier`
- Checked revision: `454ec4244132bce478e60c4707ee418312ca8922`
- Local analysis checkout: `/tmp/copier-source`

The local checkout path is analysis context only. Evidence below cites
repository-relative source paths.

## Source Evidence Paths

- `README.md`
- `docs/generating.md`
- `docs/updating.md`
- `docs/creating.md`
- `docs/configuring.md`
- `copier/_cli.py`
- `copier/_main.py`
- `copier/_template.py`
- `copier/_subproject.py`
- `copier/_user_data.py`
- `tests/test_copy.py`
- `tests/test_config.py`
- `tests/test_recopy.py`
- `tests/test_updatediff.py`
- `tests/test_answersfile.py`
- `tests/test_exclude.py`
- `tests/test_tasks.py`
- `tests/test_migrations.py`
- `tests/test_check_update.py`
- `tests/test_cleanup.py`
- `tests/test_cli.py`
- `tests/test_subdirectory.py`

## Selection Gate

| Question | Assessment |
| --- | --- |
| Observable public behavior? | Yes. Copier exposes `copy`, `recopy`, `update`, `check-update`, answers files, generated files, stdout/stderr, and config. |
| Persistent state or artifacts? | Yes. Generated project files and `.copier-answers.yml` drive later update/recopy/check-update behavior. |
| One state drives multiple public outputs? | Yes. Template config + answers + template ref drive rendered files, answers file, update decisions, conflicts, tasks, and reports. |
| 5-8 system workflows plausible? | Yes. Copy/update/recopy/check-update/exclude/skip/tasks/secret answers/subdirectory all cross multiple capabilities. |
| Source evidence available? | Yes. Docs, CLI source, core source, and tests cover the public workflow. |
| Mini product feasible? | Yes, with deterministic subset of Jinja, safe task actions, and local Git only. |
| External dependency risk? | Low if remote templates, real shell tasks, symlinks, binary media, and full Jinja are excluded. |

## Public Behavior Inventory

Copier is a project generator and updater. Public docs describe generating a
project from a template (`README.md`, `docs/generating.md`), creating templates
with `copier.yml`, questions, template helpers, and rendered paths
(`docs/creating.md`, `docs/configuring.md`), and updating an existing project
from a later template version (`docs/updating.md`).

The CLI documents four main public command surfaces: default copier behavior,
`copy`, `update`, and `check-update` (`copier/_cli.py`). The CLI exposes options
for answers files, `--data`, `--data-file`, `--exclude`, `--skip`,
`--vcs-ref`, `--pretend`, `--trust`, `--skip-tasks`, `--defaults`,
`--overwrite`, update conflict style, and JSON check-update output
(`copier/_cli.py`).

The main workflow state is represented in `Worker` and related methods:
rendering context, answers to remember, task execution, path rendering,
exclude/skip matching, template rendering, and copy/update/recopy entry points
(`copier/_main.py`). Template config exposes answers file, exclude,
migrations, skip-if-exists, tasks, subdirectory, and related config properties
(`copier/_template.py`). Subproject state loads previous answers, template
source, and previous commit (`copier/_subproject.py`). User data implements
answers precedence, prompting/default parsing, validation, and answers file
loading (`copier/_user_data.py`).

Tests cover copy/render, exclude/skip, pretend, answers file storage, secret
answers, recopy, update diff/conflicts, migrations, tasks, check-update,
cleanup, data-file precedence, and subdirectory workflows.

## Source Evidence Matrix

| Behavior ID | Public behavior | Source evidence path | Evidence type | Adaptation type | PRD location | Rubric cases |
| --- | --- | --- | --- | --- | --- | --- |
| `BEH-copy-render` | Copy renders template files and paths from answers | `README.md`, `docs/generating.md`, `docs/creating.md`, `tests/test_copy.py`, `copier/_main.py` | docs + tests + source | `direct_copy` | `prd.md#copy` | `CPU001`, `CPU004`, `CPU005`, `CPS001` |
| `BEH-config-questions` | `copier.yml` defines settings and questions/default answers | `docs/configuring.md`, `copier/_template.py`, `copier/_user_data.py`, `tests/test_config.py` | docs + source + tests | `deterministic_subset` | `prd.md#template-config` | `CPU001`, `CPU002` |
| `BEH-data-precedence` | CLI/data-file/default/previous answers feed rendering | `docs/configuring.md`, `copier/_cli.py`, `copier/_user_data.py`, `tests/test_cli.py` | docs + source + tests | `direct_copy` | `prd.md#answers` | `CPU002`, `CPS005` |
| `BEH-answers-file` | Answers file records source, commit, and non-secret answers | `docs/configuring.md`, `copier/_main.py`, `copier/_subproject.py`, `tests/test_answersfile.py` | docs + source + tests | `direct_copy` | `prd.md#answers-file` | `CPU003`, `CPS001`, `CPS009` |
| `BEH-exclude-skip` | Exclude and skip patterns affect rendered files | `docs/configuring.md`, `copier/_template.py`, `copier/_main.py`, `tests/test_copy.py`, `tests/test_exclude.py` | docs + source + tests | `direct_copy` | `prd.md#exclude-and-skip` | `CPU006`, `CPU007`, `CPS006` |
| `BEH-pretend` | Pretend mode reports without writing project artifacts | `docs/configuring.md`, `copier/_main.py`, `tests/test_copy.py`, `tests/test_output.py`, `tests/test_tasks.py` | docs + source + tests | `interface_translation` | `prd.md#pretend` | `CPU008`, `CPS006` |
| `BEH-local-git-ref` | Local Git refs/tags select template version | `docs/generating.md`, `docs/configuring.md`, `copier/_cli.py`, `copier/_main.py`, `tests/test_copy.py` | docs + source + tests | `deterministic_subset` | `prd.md#local-git` | `CPU009`, `CPS002` |
| `BEH-check-update` | Check whether project can update to newer template version | `docs/updating.md`, `copier/_cli.py`, `copier/_main.py`, `tests/test_check_update.py` | docs + source + tests | `interface_translation` | `prd.md#check-update` | `CPU010`, `CPS001` |
| `BEH-tasks-migrations` | Unsafe template tasks/migrations require trust and can mutate files | `docs/configuring.md`, `copier/_template.py`, `copier/_main.py`, `tests/test_tasks.py`, `tests/test_migrations.py` | docs + source + tests | `deterministic_subset` | `prd.md#tasks-and-migrations` | `CPU011`, `CPS007` |
| `BEH-update` | Update uses old template, new template, answers, local edits, and conflict handling | `docs/updating.md`, `copier/_main.py`, `tests/test_updatediff.py` | docs + source + tests | `deterministic_subset` | `prd.md#update` | `CPS002`, `CPS003`, `CPS008`, `CPS010` |
| `BEH-recopy` | Recopy discards local evolution and re-renders from stored template state | `docs/generating.md`, `copier/_main.py`, `tests/test_recopy.py` | docs + source + tests | `direct_copy` | `prd.md#recopy` | `CPS004`, `CPS005` |
| `BEH-subdirectory` | Template subdirectory limits the rendered source tree | `docs/configuring.md`, `copier/_main.py`, `tests/test_subdirectory.py` | docs + source + tests | `deterministic_subset` | `prd.md#subdirectory` | `CPU012`, `CPS008` |
| `BEH-cleanup-atomicity` | Failed copy/update protects existing or partially created state | `copier/_main.py`, `tests/test_cleanup.py`, `tests/test_updatediff.py` | source + tests | `deterministic_subset` | `prd.md#error-handling` | `CPU013`, `CPU014`, `CPS010` |
| `BEH-excluded` | Full Jinja, remote VCS, shell tasks, symlinks, binary files, and exact merge internals are out of scope | `docs/configuring.md`, `tests/test_symlinks.py`, `tests/test_vcs.py` | docs + tests | `excluded` | `prd.md#non-goals` | none |

## Capability Map

| Capability | Public input | Public output | Persistent state/artifacts | Downstream effects | Evidence |
| --- | --- | --- | --- | --- | --- |
| Config parsing | `copier.yml` | Parsed settings/questions or error | none | Drives rendering, answers, tasks, update | `docs/configuring.md`, `copier/_template.py` |
| Answer resolution | defaults, data file, CLI data, last answers | Render context | `.copier-answers.yml` | Drives rendered content, future recopy/update | `copier/_user_data.py`, `tests/test_cli.py` |
| Template rendering | template tree + answers | generated files and paths | destination files | Feeds answers, update, conflicts, checks | `docs/creating.md`, `tests/test_copy.py` |
| Answers file | rendered answers template | YAML answers file | `.copier-answers.yml` or configured path | Enables update/recopy/check-update | `docs/configuring.md`, `tests/test_answersfile.py` |
| Exclude/skip | config and CLI patterns | omitted or preserved files | destination files | Affects copy/update/recopy output set | `tests/test_copy.py`, `tests/test_exclude.py` |
| Local Git ref selection | local template repo + ref/tag | selected template tree | `_commit` in answers | Drives update/check-update | `tests/test_copy.py`, `docs/configuring.md` |
| Recopy | existing project + answers | regenerated project files | destination files + answers | Discards local evolution | `tests/test_recopy.py` |
| Update | old ref + new ref + local state | updated files or conflicts | destination files + answers | Checks merge/conflict behavior | `docs/updating.md`, `tests/test_updatediff.py` |
| Check-update | project answers + template repo | stdout or JSON report | none | Predicts update availability | `tests/test_check_update.py` |
| Tasks/migrations | config actions + trust flag | mutated project files or error | destination files | Unsafe feature gate | `tests/test_tasks.py`, `tests/test_migrations.py` |
| Atomicity | malformed config/template/update conflict | error and unchanged state | protected destination | Prevents partial writes | `tests/test_cleanup.py`, `tests/test_updatediff.py` |

## State And Artifact Model

- Input layer: CLI args, template path, local Git refs, `copier.yml`, data files,
  existing destination files, existing answers file.
- Core state layer: parsed template config, selected template ref, resolved
  answer map, rendered old tree, rendered new tree, destination tree.
- Derived view layer: generated files, answers file, check-update JSON, conflict
  markers/reject files, task/migration logs through deterministic safe actions.
- Mutation/recovery layer: copy, recopy, update, task/migration actions,
  conflict resolution, pretend/no-write, malformed config no-write.

The key system pressure is one template/answer/ref state driving multiple
public artifacts: rendered files, rendered paths, answers file, check-update,
update decisions, task/migration side effects, and atomicity.

## Boundary Proposal

| Source behavior | Mini-task decision | Rationale |
| --- | --- | --- |
| Local `copy` from a template | Keep | Core public Copier behavior. |
| Simple `copier.yml` questions and defaults | Keep simplified | Needed for answer/render state without full prompt engine. |
| File and path templating | Keep simplified | Core public behavior; use `{{ name }}` substitution only. |
| Answers file with `_src_path` and `_commit` | Keep | Required for update/recopy/check-update. |
| Secret questions | Keep | Public answers-file invariant. |
| Exclude and skip | Keep simplified | Public config/CLI behavior; strong state output pressure. |
| Local Git template refs/tags | Keep | User selected real Git scope. |
| Remote templates | Exclude | Network-dependent and not needed for benchmark. |
| `update` | Keep deterministic subset | Core Copier differentiator; exact merge algorithm excluded. |
| `recopy` | Keep | Public mutation workflow and contrast with update. |
| `check-update` | Keep with stable JSON | Public behavior; JSON is scoring adaptation. |
| Tasks/migrations | Keep safe subset | Source requires trust; mini-task avoids shell execution. |
| Full Jinja2, extensions, filters | Exclude | Would measure template engine breadth rather than system composition. |
| Symlinks, binary files, permissions | Exclude | Platform-heavy and non-essential. |
| Exact Copier internals | Exclude | Benchmark tests public behavior only. |

## Initial Judgment

`copier-realrepo-001` is a strong candidate source task. It naturally combines
configuration, rendering, persisted answers, local Git template refs, update
state, conflicts, unsafe actions, reports, and atomicity. This should provide
more system-level pressure than single-state parser or KV tasks while remaining
grounded in public Copier behavior.
