# MiniJupy PRD

## 1. Goal

Build `minijupy.py`, a deterministic paired-notebook command line tool inspired
by Jupytext. The tool works with `.ipynb` notebooks and `py:percent` scripts.
It converts between the two representations, creates paired files, reports pair
status, checks roundtrip consistency, synchronizes pairs, preserves notebook
outputs when text is the selected source, and prevents partial writes on
failure.

The task intentionally focuses on public paired-notebook behavior. It does not
ask for Jupytext internals, full Jupyter compatibility, or real filesystem
mtime behavior.

## 2. Command Surface

Run the program as:

```bash
python minijupy.py COMMAND [OPTIONS]
```

Supported commands:

- `inspect --input FILE [--config CONFIG]`
- `to-text --input NOTEBOOK.ipynb --output SCRIPT.py [--config CONFIG]`
- `to-ipynb --input SCRIPT.py --output NOTEBOOK.ipynb [--config CONFIG]`
- `pair --input FILE [--config CONFIG]`
- `status --input FILE [--config CONFIG]`
- `status --all --config CONFIG`
- `check --input FILE [--config CONFIG]`
- `check --all --config CONFIG`
- `sync --input FILE [--config CONFIG] [--source ipynb|text]`
- `sync --all --config CONFIG [--source ipynb|text]`

All successful commands print one JSON object to stdout and exit with code `0`.
Failed commands print a diagnostic message to stderr, write no partial output,
and exit with a nonzero code.

## 3. Files And Config

### 3.1 Supported Files

MiniJupy supports only:

- `.ipynb` JSON notebooks.
- `.py` scripts in the `py:percent` format.
- `minijupy.toml` config files.
- `.minijupy-state.json` state files.

### 3.2 Config Format

The config file is a TOML-like text file with exactly these keys:

```toml
formats = "ipynb,py:percent"
notebook_dir = "notebooks"
script_dir = "scripts"
```

Rules:

- `formats` is optional. When present, it must be exactly
  `"ipynb,py:percent"` or `"py:percent,ipynb"`.
- `notebook_dir` and `script_dir` are optional.
- If both directories are present, `.ipynb` files live under `notebook_dir`
  and `.py` files live under `script_dir`.
- If neither directory is present, pairs live in the same directory.
- Supplying only one of `notebook_dir` or `script_dir` is an invalid config.
- Paths are relative to the config file directory.
- `--all` requires `--config`.

The config file directory is the project root for state and `--all`.
If no `--config` is supplied, the project root is the current working directory.

## 4. Normalized Notebook Model

MiniJupy reads notebooks into this public model:

```json
{
  "nbformat": 4,
  "nbformat_minor": 5,
  "metadata": {
    "kernelspec": {},
    "language_info": {},
    "minijupy": {
      "formats": "ipynb,py:percent",
      "version": 1
    }
  },
  "cells": [
    {
      "id": "c1",
      "cell_type": "code",
      "source": "x = 1\n",
      "metadata": {
        "tags": ["parameters"],
        "name": "setup"
      },
      "execution_count": 3,
      "outputs": []
    }
  ]
}
```

Normalization rules:

- `nbformat` must be `4`.
- Missing `nbformat_minor` is normalized to `5`.
- Missing top-level `metadata` is normalized to `{}`.
- Cell order is preserved.
- Supported `cell_type` values are `code`, `markdown`, and `raw`.
- A missing cell `id` is assigned deterministically as `c1`, `c2`, ... by
  cell order.
- Duplicate cell ids are invalid.
- Missing cell `metadata` is normalized to `{}`.
- Cell metadata preserves only:
  - `tags`: array of strings.
  - `name`: string.
- Other cell metadata is ignored.
- Code cells may have `execution_count` and `outputs`.
- Markdown and raw cells ignore `execution_count` and `outputs`.
- Missing `source` is treated as an empty string.
- Source may be a string or an array of strings. Arrays are joined in order.
- Missing `metadata.minijupy.version` is treated as version `1`.
- Missing `metadata.minijupy.formats` is allowed until a file is paired.

The normalized model is the basis for conversion, status, check, sync, hashes,
and output preservation.

## 5. Percent Script Format

MiniJupy supports a deterministic subset of `py:percent`.

### 5.1 Header

A percent script may begin with a YAML-like commented header:

```python
# ---
# minijupy:
#   formats: ipynb,py:percent
#   version: 2
# kernelspec:
#   name: python3
# ---
```

Supported header keys:

- `minijupy.formats`
- `minijupy.version`
- `kernelspec.name`

Unknown header keys are ignored.

If the header is absent:

- `minijupy.version` defaults to `1`.
- `minijupy.formats` is absent until pairing.

### 5.2 Cell Markers

Cells start with `# %%` markers.

Supported marker forms:

```python
# %%
# %% [markdown]
# %% [raw]
# %% {"id": "cell-a", "tags": ["tag1"], "name": "setup"}
# %% [markdown] {"id": "intro", "tags": ["docs"]}
```

Rules:

- No bracket means `code`.
- `[markdown]` means `markdown`.
- `[md]` is accepted as `markdown`.
- `[raw]` means `raw`.
- The optional JSON object may contain only `id`, `tags`, and `name`.
- Malformed marker JSON is an error.
- Duplicate marker cell ids are an error.
- Text before the first marker is ignored if it is only header or blank lines.
- Non-header, nonblank text before the first marker starts an implicit code
  cell.
- Code and raw cell bodies are stored exactly as text after the marker.
- Markdown cell body lines may start with `# `; when parsed, one leading
  `# ` is removed from each markdown body line if present.

### 5.3 Percent Writer

When writing `py:percent`:

- Always write a header with `minijupy.formats`, `minijupy.version`, and
  `kernelspec.name` when present in the normalized notebook.
- Write cells in order.
- Code cells use `# %%`.
- Markdown cells use `# %% [markdown]`.
- Raw cells use `# %% [raw]`.
- Include marker JSON when the cell has `id`, `tags`, or `name`.
- Text representation never writes `execution_count` or `outputs`.

## 6. Pair Path Rules

A pair always consists of one `.ipynb` file and one `.py` file.

Same-directory pairing:

- `analysis.ipynb` pairs with `analysis.py`.
- `analysis.py` pairs with `analysis.ipynb`.

Directory-mapped pairing with config:

- With `notebook_dir = "notebooks"` and `script_dir = "scripts"`,
  `notebooks/demo.ipynb` pairs with `scripts/demo.py`.
- Nested relative paths are preserved:
  `notebooks/reports/demo.ipynb` pairs with `scripts/reports/demo.py`.
- A file outside both configured directories is a path mismatch error.
- If two files would map to the same counterpart, that is a duplicate mapping
  error.

The same path rules must be used by `pair`, `status`, `check`, and `sync`.

## 7. State File

MiniJupy uses a public state file named `.minijupy-state.json`.

Location:

- If `--config CONFIG` is supplied, the state file is in the same directory as
  `CONFIG`.
- Otherwise, it is in the current working directory.

State shape:

```json
{
  "pairs": {
    "notebooks/demo.ipynb": {
      "ipynb": "notebooks/demo.ipynb",
      "text": "scripts/demo.py",
      "last_synced": {
        "ipynb_version": 2,
        "text_version": 2,
        "ipynb_hash": "stable-token",
        "text_hash": "stable-token"
      }
    }
  }
}
```

Rules:

- Pair keys are normalized relative `.ipynb` paths from the project root.
- `ipynb` and `text` paths are normalized relative paths from the project root.
- `last_synced.ipynb_version` and `last_synced.text_version` are the public
  versions observed at the last successful pair/sync.
- Hash values are stable equality tokens derived from the normalized public
  model. The exact algorithm is implementation-defined. Freshness, conflict,
  and source-selection decisions are driven by public versions, not by the
  literal hash strings stored in the state file. Implementations must tolerate
  existing arbitrary hash strings in `.minijupy-state.json`; a command must not
  fail solely because an existing hash token does not match its own hash
  algorithm.
- Successful `pair`, `sync`, and `sync --all` update the state file.
- `inspect`, `status`, and `check` do not write the state file.

## 8. Version Rules

The public version is an integer.

For `.ipynb`:

- Version is read from `metadata.minijupy.version`.
- Missing version means `1`.
- A non-integer or negative version is invalid.

For `.py`:

- Version is read from header key `minijupy.version`.
- Missing version means `1`.
- A non-integer or negative version is invalid.

Mutation rules:

- `to-text` writes the same version as the source `.ipynb`.
- `to-ipynb` writes the same version as the source `.py`.
- `pair` initializes state using the current versions in both files. If it
  creates a missing counterpart, the new counterpart uses the source version.
- `sync` writes the selected source version to the updated counterpart and then
  records both versions as last synced.
- MiniJupy does not auto-increment versions. Users express edits by changing
  the public version in the edited file.

## 9. Command Behavior

### 9.1 `inspect`

`inspect` reads one `.ipynb` or `.py` file and prints:

```json
{
  "ok": true,
  "command": "inspect",
  "path": "notebooks/demo.ipynb",
  "format": "ipynb",
  "version": 1,
  "notebook": {}
}
```

`notebook` is the normalized notebook model. The command writes no files.

### 9.2 `to-text`

`to-text` converts one `.ipynb` file into one `py:percent` file.

Rules:

- Input must be `.ipynb`.
- Output must end with `.py`.
- Outputs and execution counts are not written to the text file.
- Cell ids, tags, names, cell types, source, supported metadata, formats, and
  version are preserved.
- The command does not update `.minijupy-state.json`.

### 9.3 `to-ipynb`

`to-ipynb` converts one `py:percent` file into one `.ipynb` file.

Rules:

- Input must be `.py`.
- Output must end with `.ipynb`.
- The output notebook is normalized.
- Cells created from text have no outputs and `execution_count: null`.
- Cell ids, tags, names, cell types, source, supported metadata, formats, and
  version are preserved.
- The command does not update `.minijupy-state.json`.

### 9.4 `pair`

`pair` creates or updates a pair.

Rules:

- Input may be either side of the pair.
- The counterpart path is derived from config/path rules.
- If the counterpart is missing, it is created.
- Both files are written with `minijupy.formats = "ipynb,py:percent"`.
- The state file is created or updated.
- The state entry records both paths, current public versions, and stable hash
  tokens.
- If both files exist, `pair` must not discard `.ipynb` outputs.
- `pair` fails on malformed files, invalid config, path mismatch, duplicate
  mapping, or invalid versions.

### 9.5 `status`

`status` is read-only. It reports pair state, selected source, conflicts,
missing counterparts, planned writes, and summary counts.

For one file, use `status --input FILE`.
For all pairs, use `status --all --config CONFIG`.

The command prints this shape:

```json
{
  "ok": true,
  "command": "status",
  "root": ".",
  "pairs": [
    {
      "ipynb": "notebooks/demo.ipynb",
      "text": "scripts/demo.py",
      "exists": {"ipynb": true, "text": true},
      "versions": {
        "ipynb": 2,
        "text": 3,
        "last_ipynb": 2,
        "last_text": 2
      },
      "source": "text",
      "conflict": false,
      "missing": [],
      "planned_writes": ["notebooks/demo.ipynb", ".minijupy-state.json"],
      "roundtrip_ok": true,
      "differences": [],
      "errors": []
    }
  ],
  "summary": {
    "pairs": 1,
    "conflicts": 0,
    "missing": 0,
    "planned_writes": 2,
    "errors": 0
  }
}
```

Rules:

- `source` is `"ipynb"`, `"text"`, or `"none"`.
- `source` is `"none"` when both sides match the last synced state.
- `source` is also `"none"` when `conflict` is `true`, because no automatic
  source can be selected safely.
- `planned_writes` lists files that `sync` would write for the same input.
- The state file counts as a planned write when sync would update it.
- Missing counterpart files are reported in `missing`.
- Invalid files or configs appear in `errors`; severe parse/config errors may
  also make the command exit nonzero.
- `status` writes no files.

### 9.6 `check`

`check` is read-only. It uses the same output schema as `status`, with
`command: "check"`.

Additional rules:

- `roundtrip_ok` reports whether `.ipynb -> py:percent -> .ipynb` or
  `py:percent -> .ipynb -> py:percent` preserves all representable public
  fields and whether the state file is consistent with the public file
  versions.
- `differences` lists public mismatch categories such as `cell_count`,
  `cell_type`, `source`, `id`, `tags`, `name`, `version`, `formats`, or
  `outputs`.
- If `.minijupy-state.json` records last synced versions greater than the
  current public versions of the paired files, `check` must report
  `roundtrip_ok: false` and include `state` in `differences`.
- `check` never writes files.

### 9.7 `sync`

`sync` updates one pair.

Source selection:

- If `--source ipynb` is supplied, `.ipynb` is the selected source.
- If `--source text` is supplied, `.py` is the selected source.
- Without `--source`, MiniJupy compares current versions to
  `.minijupy-state.json`.
- If only `.ipynb` changed since last sync, source is `"ipynb"`.
- If only `.py` changed since last sync, source is `"text"`.
- If neither side changed, source is `"none"` and sync writes nothing.
- If both sides changed, sync fails as conflict and writes nothing.

When source is `.ipynb`:

- Text counterpart is regenerated from `.ipynb`.
- Outputs remain in `.ipynb`.
- State is updated.

When source is text:

- `.ipynb` inputs are updated from text.
- Matching `.ipynb` outputs and execution counts are preserved according to the
  output preservation rules.
- Text may be normalized if needed.
- State is updated.

The command prints the same pair object as `status`, plus actual writes in
`planned_writes`.

### 9.8 `sync --all`

`sync --all --config CONFIG` applies sync to every pair reachable from the
config root.

Rules:

- It first discovers all `.ipynb` and `.py` files under the configured
  directories that are part of valid pairs.
- It computes every pair's status and complete write plan before writing.
- It is all-or-nothing.
- If any pair has malformed input, invalid config, duplicate mapping, path
  mismatch, invalid version, or unresolved conflict, the command exits nonzero
  and writes no files.
- If validation succeeds, all planned pair files and the state file are written.
- `status --all` must predict the same pair set and planned writes that
  `sync --all` would perform.

## 10. Conflict Rules

A pair is in conflict when:

- Both `.ipynb` and text counterparts exist.
- A state entry exists for the pair.
- Current `.ipynb` version is greater than `last_synced.ipynb_version`.
- Current text version is greater than `last_synced.text_version`.

Conflict behavior:

- `status` and `check` report `conflict: true`.
- `sync` without `--source` fails and writes nothing.
- `sync --source ipynb` resolves by using `.ipynb`.
- `sync --source text` resolves by using text.
- Missing counterpart is not a conflict.
- If no state entry exists, `status` reports source based on the existing side
  and `sync` may create the missing counterpart; if both sides exist without
  state, `sync` fails unless `--source` is supplied or `pair` is run first.

## 11. Missing Counterpart Rules

If one side of a pair is missing:

- `status` reports the missing side.
- `check` reports `roundtrip_ok: false` until the missing side is recreated.
- `sync` creates the missing counterpart from the existing side.
- `pair` also creates the missing counterpart and initializes state.
- Missing counterpart creation must preserve `.ipynb` outputs when the existing
  side is `.ipynb`.
- Missing counterpart creation from text produces an `.ipynb` with no outputs.

If both sides are missing, the command fails.

## 12. Output Preservation Rules

When text is selected as source and an `.ipynb` counterpart exists, MiniJupy
preserves outputs and execution counts from the existing `.ipynb`.

Matching order:

1. Match by identical public cell `id`.
2. If no id match exists, match the first unused output cell with the same
   `cell_type` and same normalized source hash.
3. If no source-hash match exists, match by same position when cell types match.
4. If none match, the new input cell receives no outputs and
   `execution_count: null`.

Rules:

- Only code cells can receive outputs and execution counts.
- Markdown and raw cells never receive outputs.
- An output cell can be used at most once.
- Unmatched old outputs are dropped.
- Text conversion never writes outputs into `.py`.

## 13. Error Handling And Atomicity

Invalid conditions include:

- Malformed JSON notebook.
- Unsupported notebook `nbformat`.
- Unsupported cell type.
- Duplicate cell ids.
- Malformed percent marker JSON.
- Invalid version.
- Invalid config.
- Path mismatch.
- Duplicate paired paths.
- Conflict without explicit `--source`.
- `--all` without `--config`.
- Unsupported command or option combination.

Atomicity rules:

- A failed command must not leave new output files.
- A failed command must not modify existing `.ipynb`, `.py`, config, or state
  files.
- `sync --all` must not partially update one pair when another pair fails.
- `inspect`, `status`, and `check` are read-only.
- Temporary files, if used, must not remain after failure.

## 14. Non-Goals

MiniJupy does not need to implement:

- Real filesystem modification-time logic.
- Jupytext private APIs, module names, or exact serialization.
- Full nbformat validation.
- Markdown, MyST, Quarto, Rmd, light, nomarker, sphinx, spin, marimo, or
  non-Python formats.
- Full metadata filter grammar.
- Jupyter server, ContentsManager, collaboration, autosave, or browser reload
  behavior.
- Notebook execution, kernels beyond preserving `kernelspec.name`, nbconvert,
  papermill, pipes, black, or external tools.
- Git or pre-commit index behavior.
- Rich MIME rendering fidelity, image processing, or binary media handling.
- Background watchers or automatic sync daemons.

## 15. Global Invariants

- The same normalized notebook model drives inspect, conversion, pair, status,
  check, sync, state hashes, and output preservation.
- The same pair path rules apply to pair, status, check, and sync.
- `status` predicts `sync` writes for the same input state.
- `check` roundtrip results are consistent with actual conversion behavior.
- Successful pair/sync updates `.minijupy-state.json` consistently with the
  files it writes.
- Failed commands leave all public artifacts unchanged.
