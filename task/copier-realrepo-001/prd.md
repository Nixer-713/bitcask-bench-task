# MiniCopier PRD

## Overview

Build `minicopier.py`, a deterministic project-template generator inspired by
Copier. The program copies a local template into a destination project, records
answers for future operations, checks whether a newer local Git template ref is
available, updates existing projects, recopies projects from stored answers, and
protects destination files on failures.

The task focuses on public template, answer, generated-file, local Git, update,
and conflict behavior. It does not require Copier internals, full Jinja2, remote
repositories, shell execution, symlinks, binary files, or exact merge parity.

Run commands as:

```bash
python minicopier.py COMMAND [OPTIONS]
```

Successful commands exit `0` and print one JSON object to stdout. Failed
commands exit nonzero, print a diagnostic to stderr, and leave public artifacts
unchanged unless the command explicitly reports a safe conflict output.

## Commands

Supported commands:

```text
copy TEMPLATE DEST [--answers-file FILE] [--data KEY=VALUE ...]
                   [--data-file FILE] [--defaults]
                   [--overwrite] [--exclude PATTERN ...] [--skip PATTERN ...]
                   [--vcs-ref REF] [--pretend] [--trust] [--skip-tasks]

recopy DEST [--answers-file FILE] [--data KEY=VALUE ...] [--overwrite]
            [--skip-answered] [--exclude PATTERN ...] [--skip PATTERN ...]
            [--pretend]

update DEST [--answers-file FILE] [--vcs-ref REF] [--data KEY=VALUE ...]
            [--overwrite] [--skip-answered] [--exclude PATTERN ...]
            [--skip PATTERN ...] [--conflict inline|rej] [--pretend]
            [--trust] [--skip-tasks]

check-update DEST [--answers-file FILE] [--json]
```

Only local template directories and local Git repositories are supported.
Network template sources are invalid.

## Template Config

A template may contain `copier.yml` or `copier.yaml` at its root. If both exist,
`copier.yml` wins.

Supported settings:

- `_answers_file`: relative destination path for the answers file. Default:
  `.copier-answers.yml`.
- `_templates_suffix`: suffix removed from rendered template files. Default:
  `.jinja`.
- `_exclude`: list of glob patterns excluded from rendering.
- `_skip_if_exists`: list of glob patterns not overwritten when the destination
  path already exists.
- `_subdirectory`: template subdirectory to render.
- `_tasks`: list of safe actions to run after copy/update/recopy.
- `_migrations`: list of safe migration actions to run during update.
- `_secret_questions`: list of question names omitted from answers file.

Other top-level keys are questions. A question may be:

```yaml
project_name: Demo

author:
  default: Ada
  secret: true
  when: "{{ project_name }}"
```

Rules:

- A scalar question value is its default.
- A mapping question may use `default`, `secret`, and `when`.
- A question with `when` rendering to an empty string, `false`, `False`, `0`, or
  `no` is skipped and not stored in the answers file.
- Unknown underscore settings are ignored.
- Malformed YAML or invalid setting types are errors.

## Answers

Answers are resolved in this order:

For `copy`:

1. Defaults from `copier.yml`.
2. Values from `--data-file`.
3. Values from repeated `--data KEY=VALUE`.

For `recopy` and `update`:

1. Defaults from `copier.yml`.
2. Existing answers from the destination answers file.
3. Values from `--data-file`, when the command supports it.
4. Values from repeated `--data KEY=VALUE`.

Later sources override earlier sources. Values are strings unless the YAML data
file provides booleans, numbers, lists, or mappings.

The answers file path is selected in this order:

1. `--answers-file FILE`, when supplied.
2. `_answers_file` from `copier.yml`, when supplied during copy.
3. `.copier-answers.yml`.

For recopy, update, and check-update, `--answers-file` is required when the
project uses a non-default answers file path.

The answers file is YAML-like text containing:

- `_src_path`: local template path used for copy.
- `_commit`: selected Git ref name or commit token for Git templates.
- non-secret, non-skipped answers.

Secret answers may be used for rendering but must not appear in the answers
file. The answers file itself is always overwritten by successful copy, recopy,
and update.

For non-Git filesystem templates, `_commit` is omitted.

## Local Git Refs

If `TEMPLATE` is a Git repository:

- `--vcs-ref REF` selects that local ref, branch, tag, or commit.
- Without `--vcs-ref`, the newest semver-like tag is selected. A tag may start
  with `v`; `v2.0.0` and `2.0.0` compare as version `2.0.0`.
- If no semver-like tag exists, use `HEAD`.
- The selected ref is recorded in `_commit` using the ref name when a tag/ref is
  explicitly selected, otherwise the selected tag name or `HEAD`.

MiniCopier may use the local `git` executable to read files at refs. Remote Git
URLs are unsupported.

## Rendering

Rendering applies to text files and path segments.

Rules:

- A file ending with `_templates_suffix` is rendered and written without that
  suffix.
- Non-template text files are copied as-is.
- Path segments may contain `{{ variable }}` and are rendered before writing.
- If a rendered path segment is empty, that file or directory is skipped.
- File content supports only simple `{{ variable }}` substitution.
- Missing variables render as an empty string.
- Template config files (`copier.yml`, `copier.yaml`) are not rendered into the
  destination unless explicitly included through a different rendered path.
- Files matching exclude patterns are not written.
- Destination paths matching skip patterns are not overwritten if they already
  exist.
- `--overwrite` allows overwriting ordinary rendered files, except skip patterns
  still protect existing destination files.

## Exclude And Skip

Exclude patterns come from `_exclude` plus repeated `--exclude`. Skip patterns
come from `_skip_if_exists` plus repeated `--skip`.

Patterns are matched against destination-relative POSIX paths. `*` and `?` use
standard glob behavior. A pattern ending in `/` matches that directory and its
contents.

Exclude prevents a template item from being written. Skip-if-exists preserves an
existing destination file but allows creating it when missing.

## Pretend

`--pretend` computes the operation and prints JSON with `"pretend": true`,
planned writes, skipped paths, and excluded paths, but writes no files, answers
file, task effects, migrations, conflict markers, or reject files.

## Copy

`copy TEMPLATE DEST` renders a new or existing destination.

Rules:

- Destination is created if missing.
- If destination exists, files may be overwritten only with `--overwrite`, unless
  they match skip patterns.
- Answers are resolved from defaults, data file, and CLI data.
- Successful copy writes generated files and the answers file.
- If `_tasks` are present, the command fails unless `--trust` or `--skip-tasks`
  is supplied.
- With `--skip-tasks`, tasks are ignored.

The stdout JSON includes:

```json
{
  "ok": true,
  "command": "copy",
  "operation": "copy",
  "answers_file": ".copier-answers.yml",
  "commit": "v1.0.0",
  "written": ["README.md"],
  "skipped": [],
  "excluded": []
}
```

## Recopy

`recopy DEST` re-renders the project using `_src_path`, `_commit`, and prior
answers from the destination answers file.

Rules:

- Local project edits to rendered files are discarded when the file is rendered
  again.
- `--data` overrides previous answers.
- With `--skip-answered`, existing answers are reused unless overridden by
  `--data`.
- `--pretend` reports planned writes without changing files.
- Recopy fails if the answers file is missing or lacks `_src_path`.

## Check Update

`check-update DEST --json` reads the destination answers file and compares
stored `_commit` to the newest semver-like tag in `_src_path`.

The command writes no files and prints:

```json
{
  "ok": true,
  "command": "check-update",
  "current": "v1.0.0",
  "latest": "v2.0.0",
  "update_available": true
}
```

If no update is available, `update_available` is `false`.

## Update

`update DEST` updates an existing project.

Inputs:

- destination answers file;
- stored `_src_path` and `_commit`;
- old template tree at stored `_commit`;
- new template tree at `--vcs-ref` or newest semver-like tag;
- previous answers merged with `--data`.

For each rendered destination file:

- If current destination content equals the old rendered content, write the new
  rendered content.
- If current destination content equals the new rendered content, leave it
  unchanged.
- If current content differs from both old and new rendered content, the file is
  in conflict.

Conflict behavior:

- With `--conflict inline`, write the file with conflict markers containing
  `<<<<<<< local`, `=======`, and `>>>>>>> template`.
- With `--conflict rej`, leave the current file unchanged and write a sibling
  reject file named `<path>.rej` containing the new rendered content.
- If any conflict occurs, stdout JSON reports `conflicts`.

Successful update writes the answers file with the selected new `_commit`.
An update that writes public conflict artifacts is still a successful update:
it exits `0`, reports `conflicts`, and advances the answers file to the
selected new `_commit`.
`--pretend` reports planned writes and conflicts without writing anything.

If `_migrations` are present, update fails unless `--trust` is supplied. If
`--skip-tasks` is supplied, `_tasks` are skipped but migrations still require
`--trust`.

## Tasks And Migrations

MiniCopier supports only deterministic safe actions:

```yaml
_tasks:
  - write log.txt copied
  - append log.txt updated

_migrations:
  - version: v2.0.0
    before:
      - append migrate.log before-v2
    after:
      - append migrate.log after-v2
```

Rules:

- `write FILE TEXT` writes `TEXT` to `FILE`.
- `append FILE TEXT` appends `TEXT` and a trailing newline to `FILE`.
- Paths are destination-relative.
- Tasks run after successful copy, recopy, or update unless `--skip-tasks`.
- Migration `before` actions run before update writes.
- Migration `after` actions run after update writes.
- Tasks and migrations require `--trust`.
- Shell commands, environment access, pipes, and arbitrary process execution are
  unsupported.

## Subdirectory

If `_subdirectory` is set, only that template subdirectory is rendered. The
answers file and template config are still resolved from the template root.

## Error Handling And Atomicity

Invalid conditions include:

- unsupported command or option;
- missing template or destination answers file;
- malformed YAML config or data file;
- unsupported local Git ref;
- remote template source;
- unsafe tasks or migrations without `--trust`;
- attempts to overwrite existing files without `--overwrite`;
- safe action path outside destination.

Atomicity rules:

- Failed copy into a newly created destination removes files it created.
- Failed copy into an existing destination leaves existing files unchanged.
- Failed recopy/update leaves existing files, answers file, reject files, and
  task/migration effects unchanged.
- `check-update` never writes files.
- `--pretend` never writes files.

## Non-Goals

MiniCopier does not implement:

- remote Git or network templates;
- full Jinja2 syntax, loops, filters, macros, imports, inheritance, extensions,
  tests, or sandbox behavior;
- interactive prompts;
- real Copier internals, class names, or exact merge algorithm;
- arbitrary shell tasks, external process execution, or environment access;
- symlinks, binary files, executable bits, permissions, or platform-specific
  filesystem metadata;
- pre-commit integration, Git worktree dirty checks, or Git index behavior;
- Unicode normalization edge cases;
- multiple template application to the same project.

## Global Invariants

- The same resolved answers drive rendered contents, rendered paths, answers
  file, task/migration actions, recopy, update, and check-update.
- The same exclude/skip rules apply across copy, recopy, update, and pretend.
- The answers file is the source of truth for recopy, update, and check-update.
- `check-update` predicts whether update has a newer local template ref.
- Failed commands and pretend commands do not partially mutate public artifacts.
