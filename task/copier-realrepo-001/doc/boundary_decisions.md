# Copier Boundary Decisions

## Goal

Create a deterministic mini Copier task that preserves public template
generation/update behavior while avoiding full Copier/Jinja/VCS reimplementation.

## Decisions

| Area | Decision | Classification |
| --- | --- | --- |
| Program surface | Implement one Python CLI, `minicopier.py`, with `copy`, `recopy`, `update`, and `check-update`. | `interface_translation` |
| Template source | Support local filesystem template directories and local Git template repositories. | `direct_copy` |
| Remote templates | Exclude network/remote templates. | `excluded` |
| Git refs | Use real local Git refs/tags for `--vcs-ref`; latest tag selection uses deterministic semver-like tag ordering. | `deterministic_subset` |
| Config file | Support `copier.yml` / `copier.yaml` with a fixed key subset. | `deterministic_subset` |
| Jinja rendering | Support simple `{{ variable }}` substitution in text files and path segments. | `deterministic_subset` |
| Full Jinja2 | Exclude filters, loops, macros, inheritance, extensions, tests, whitespace control, and sandbox behavior. | `excluded` |
| Answers precedence | Preserve public precedence: previous/default answers, data file, and CLI `--data` where applicable. | `direct_copy` |
| Answers file | Generate configured answers file and record `_src_path`, `_commit`, and non-secret answers. | `direct_copy` |
| Secret questions | Let secret values render files but omit them from answers file. | `direct_copy` |
| Exclude/skip | Support glob-style exclude and skip-if-exists patterns from config and CLI. | `deterministic_subset` |
| Pretend mode | Report planned writes and write no destination artifacts. | `interface_translation` |
| Recopy | Re-render from stored template source/ref and answers, discarding local file evolution. | `direct_copy` |
| Update | Use deterministic old-render/current/new-render comparison; exact Copier diff algorithm is excluded. | `deterministic_subset` |
| Conflict style | Support `inline` and `rej` as public conflict outputs. | `deterministic_subset` |
| Check update | Print a stable JSON object for scoring when `--json` is used. | `interface_translation` |
| Tasks/migrations | Support safe deterministic actions only: `write FILE TEXT` and `append FILE TEXT`; require `--trust`; `--skip-tasks` skips tasks. | `deterministic_subset` |
| Shell tasks | Exclude arbitrary shell/process execution. | `excluded` |
| Subdirectory | Support `_subdirectory` selecting a sub-tree of the template. | `deterministic_subset` |
| Cleanup/atomicity | Failed commands leave existing destination artifacts unchanged and do not leave partial new files. | `deterministic_subset` |
| Symlinks/binary/permissions | Exclude symlinks, binary data, executable bits, and platform-specific filesystem metadata. | `excluded` |

## Public State Model

MiniCopier's public state consists of:

- the template repository path and selected ref;
- the `copier.yml` settings and question defaults;
- the resolved answers map;
- generated project files;
- the answers file;
- local project edits;
- task/migration safe-action effects.

The same state must drive rendered files, rendered paths, answers file content,
check-update reports, recopy/update behavior, conflicts, and no-write behavior.

## Fairness Boundary

The mini-task is consistent with Copier's public behavior, documentation
semantics, and test intent. It is not a reimplementation of Copier source code.
Deterministic adaptations are allowed only because they are public in the PRD
and traced in `requirement_map.md`.
