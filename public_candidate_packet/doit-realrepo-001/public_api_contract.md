# MiniDoit Public API Contract

This file defines the public interfaces that an implementation must provide.
Internal module structure beyond these public entrypoints is up to the
implementer.

## Package

Name: `minidoit`

Required imports:

```python
import minidoit
```

Required package attributes:

- `__version__`: string

## CLI Entrypoints

### Console Script

Name: `minidoit`

Signature:

```bash
minidoit [GLOBAL_OPTIONS] [COMMAND] [COMMAND_OPTIONS] [TASK ...]
```

Global options:

- `--file FILE`
- `--db-file FILE`
- `--help`
- `--version`

`--file` and `--db-file` must be accepted before or after the command name, but
before task names. `dumpdb` accepts `--db-file` but does not accept or require
`--file`.

Supported commands:

- `run`
- `list`
- `info`
- `clean`
- `forget`
- `dumpdb`

No command is equivalent to `run`.

### Module Execution

Signature:

```bash
python -m minidoit [GLOBAL_OPTIONS] [COMMAND] [COMMAND_OPTIONS] [TASK ...]
```

Behavior must match the console script.

## Exit Codes

- `0`: command completed successfully.
- non-zero: command failed due to invalid input, invalid state, or task
  execution failure.

Implementations may choose specific non-zero numeric codes, but they must be
consistent and must write a useful error message to stderr for failures.

## Public Files

### Task File

Default: `dodo.py`

Override:

```bash
--file FILE
```

The supported task grammar is defined in `prd.md`.

### State File

Default: `.minidoit.db.json`

Override:

```bash
--db-file FILE
```

The state file is public JSON. It must be deterministic and may be inspected by
users.

Required top-level state shape:

```json
{
  "version": 1,
  "tasks": {
    "task_name": {
      "status": "success",
      "file_dep": {
        "path": "content_signature"
      },
      "targets": ["path"],
      "last_result": "success"
    }
  }
}
```

Additional fields are allowed when they do not change the required behavior.

State value vocabulary:

- task report status values are `run`, `up_to_date`, and `error`;
- run event values are `executed`, `skipped`, and `failed`;
- persisted state result value is `success`.

State path rules:

- state file parent directories are created as needed after a successful
  command that writes state;
- state updates must be valid JSON;
- corrupted JSON state is a pre-execution error.

## JSON Report Schemas

All JSON reports must be written to stdout and must be parseable as UTF-8 JSON.
They must not include non-deterministic timestamps or absolute paths unless an
input path was absolute, which is otherwise invalid for task file paths.

### `list --json`

Shape:

```json
{
  "tasks": [
    {
      "name": "build",
      "doc": "optional text",
      "file_dep": ["src.txt"],
      "targets": ["out.txt"],
      "task_dep": ["prepare"],
      "status": "run"
    }
  ]
}
```

Rules:

- `status` is included when `--status` is present; it may also be included
  without `--status`;
- task order must be deterministic by task name.

### `info TASK --json`

Shape:

```json
{
  "name": "build",
  "doc": "optional text",
  "file_dep": ["src.txt"],
  "targets": ["out.txt"],
  "task_dep": ["prepare"],
  "clean": true,
  "status": "run",
  "reasons": ["no_success_state"]
}
```

Rules:

- `reasons` contains stable reason keys from `prd.md`;
- unknown task names are errors.

### `dumpdb --json`

Shape:

```json
{
  "version": 1,
  "tasks": {
    "build": {
      "status": "success",
      "file_dep": {
        "src.txt": "content_signature"
      },
      "targets": ["out.txt"],
      "last_result": "success"
    }
  }
}
```

Rules:

- output represents the public state file;
- command behavior is independent of `dodo.py`;
- when the state file does not exist, output an empty valid state object with
  `version` and `tasks`.

## Command Details

### `run`

Accepted forms:

```bash
minidoit
minidoit run
minidoit run TASK ...
```

Output:

- human-readable stdout describing executed/skipped/failed tasks;
- stderr for errors.

Side effects:

- may create/update target files;
- may create/update the state file after successful task runs.

### `list`

Accepted forms:

```bash
minidoit list
minidoit list --status
minidoit list --json
minidoit list --json --status
```

Side effects: none.

### `info`

Accepted forms:

```bash
minidoit info TASK
minidoit info TASK --json
```

Side effects: none.

### `clean`

Accepted forms:

```bash
minidoit clean
minidoit clean TASK ...
minidoit clean --forget
minidoit clean TASK ... --forget
```

Side effects:

- removes target files or clean paths;
- runs safe clean actions when configured;
- removes state entries for cleaned tasks only when `--forget` is present.

### `forget`

Accepted forms:

```bash
minidoit forget TASK ...
minidoit forget --all
```

Side effects:

- updates the state file;
- does not remove target files.

### `dumpdb`

Accepted forms:

```bash
minidoit dumpdb
minidoit dumpdb --json
```

Side effects: none.

## Public Status and Reason Values

Task status values:

- `run`
- `up_to_date`
- `error`

Run event values:

- `executed`
- `skipped`
- `failed`

Persisted state result values:

- `success`

Reason keys:

- `no_success_state`
- `changed_file_dep`
- `missing_file_dep`
- `missing_target`
- `uptodate_false`
- `task_failed`
- `invalid_task`
- `invalid_state`

## Error Contract

Errors must:

- exit non-zero;
- write a message to stderr;
- not produce malformed JSON on stdout for JSON commands;
- avoid target/state writes for pre-execution failures;
- avoid saving success state for failed tasks.

Exact error wording is not part of the public contract.
