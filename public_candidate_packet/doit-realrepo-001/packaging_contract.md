# MiniDoit Packaging Contract

The submission must be a complete installable Python project.

## Python Version

Supported runtime:

```text
Python >= 3.10
```

## Installation

The evaluator will install the project from its root with:

```bash
${PYTHON_BIN:-python3} -m pip install -e .
```

The install must succeed in a clean local environment without network access
beyond packages already declared by the submitted project and available in the
environment.

## Required Project Files

At minimum, include:

```text
pyproject.toml
src/minidoit/__init__.py
src/minidoit/__main__.py
src/minidoit/cli.py
```

Additional modules may be added under `src/minidoit/`.

## Package Metadata

`pyproject.toml` must define:

- project name: `minidoit`
- Python requirement compatible with `>=3.10`
- console script:

```toml
[project.scripts]
minidoit = "minidoit.cli:main"
```

`minidoit.__version__` must exist and be a string.

## Runtime Constraints

The package must:

- run on a local filesystem;
- avoid network access;
- avoid external services, credentials, daemons, GUI tools, and platform-specific
  binaries;
- avoid relying on file modification times for task freshness;
- write only within the current workspace or paths explicitly provided by the
  user and accepted by the PRD path rules.

## Dependencies

Prefer the Python standard library. Third-party dependencies are allowed only if
declared in `pyproject.toml` and compatible with the offline evaluation
environment. Do not require optional system packages.

## Entrypoint Requirements

Both forms must work after installation:

```bash
minidoit --help
python -m minidoit --help
```

The CLI must also work when invoked from arbitrary working directories that
contain valid task/config files.

## Candidate Workspace Assumptions

During evaluation, commands run inside isolated temporary workspaces. The
workspace may contain:

- a `dodo.py` file;
- a `pyproject.toml` config file;
- source files used as task dependencies;
- existing target files;
- an existing `.minidoit.db.json` state file.

The implementation must not assume any repository-specific files outside the
submitted package and the current workspace.
