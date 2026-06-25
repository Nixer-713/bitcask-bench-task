# Mini Jupytext Paired-Notebook CLI PRD

## Goal

Build `minijupy.py`, a local paired-notebook command-line tool inspired by
`mwouts/jupytext`. The program converts between a small public notebook JSON
model and `py:percent` scripts, maintains pairing metadata, synchronizes paired
files from a deterministic authoritative source, and reports paired-path,
roundtrip, and sync status.

This task is designed around the distinction between local feature correctness
and system correctness. Each conversion or report should work on its own, but
the product is only complete if the same notebook model stays consistent across
both representations, across pairing config, and across `sync`/`status`, because
the two paired files and their reports must always agree.

The benchmark focuses on observable behavior. It does not require the real
Jupytext package, Jupyter, notebook execution, full nbformat parity, Markdown /
MyST / Quarto / Rmd formats, non-Python languages, server/ContentsManager
integration, metadata-filter grammar, or any private internal structure.

## Invocation

The implementation language is Python 3.11. Place `minijupy.py` at the root of
your solution directory. All commands run as:

```console
python minijupy.py COMMAND [OPTIONS]
```

Paths are interpreted relative to the current working directory unless absolute.
Successful commands print one compact JSON value followed by a newline, except
where a command's only effect is writing files (those print a compact JSON
result object describing what was written). Failed commands exit non-zero, print
a useful stderr message, and must not partially write or corrupt any file.

Supported commands:

```console
python minijupy.py inspect   --input FILE [--config CONFIG]
python minijupy.py to-text   --input NOTEBOOK.ipynb --output NOTEBOOK.py
python minijupy.py to-ipynb  --input NOTEBOOK.py     --output NOTEBOOK.ipynb
python minijupy.py pair      --input NOTEBOOK.ipynb --formats ipynb,py:percent [--config CONFIG]
python minijupy.py sync      --input FILE [--config CONFIG] [--source ipynb|text]
python minijupy.py status    --input FILE [--config CONFIG]
```

`FILE` may be either representation (`.ipynb` or `.py`) unless a command
restricts it. `--input` for `to-text` and `pair` must be `.ipynb`; for
`to-ipynb` must be `.py`.

## Notebook JSON Model

The public notebook model is an nbformat-like JSON object:

```json
{
  "metadata": {},
  "cells": []
}
```

Each cell is:

```json
{
  "id": "c1",
  "cell_type": "code",
  "source": "print(1)",
  "metadata": {},
  "execution_count": null,
  "outputs": []
}
```

Rules:

- `cell_type` is one of `code`, `markdown`, `raw`.
- `source` is a single string. Multi-line source uses `\n`; there is no trailing
  newline normalization beyond what the format rules below define.
- `id` is a stable public string cell identifier. If an input `.ipynb` or
  percent-script cell has no `id`, assign `c1`, `c2`, ... in cell order. Ids
  must be unique within a notebook; duplicate ids in an input `.ipynb` or
  percent script are an error.
- `execution_count` and `outputs` are only meaningful for `code` cells. For
  `markdown` and `raw` cells `execution_count` is `null` and `outputs` is `[]`.
- Supported notebook `metadata` keys preserved by this task are
  `metadata.minijupy` (see Version Marker) and `metadata.kernelspec`. Other
  notebook metadata keys are ignored and must not be emitted.
- Supported cell `metadata` keys preserved by this task are `tags` (array of
  strings) and `name` (string). Other cell metadata keys are ignored and must
  not be emitted.

The normalized notebook model is the canonical object compared by `status` and
roundtrip checks. Two notebooks are model-equal when their `metadata.minijupy`,
`metadata.kernelspec`, and ordered `cells` (comparing `cell_type`, `source`,
cell `metadata.tags`, cell `metadata.name`, and—only for matched code cells—
`execution_count` and `outputs`) are equal. Cell `id` is used for matching, not
for equality.

## Percent Script Format

A `py:percent` script encodes the notebook as Python text.

### Header

If the notebook has a `metadata.minijupy` object, the script begins with a
header block delimited by a line exactly `# ---` and a closing line exactly
`# ---`. Header body lines are exact `# key: value` pairs for the supported
notebook metadata, serialized as compact JSON values:

```python
# ---
# minijupy: {"formats":"ipynb,py:percent","version":1}
# kernelspec: {"language":"python"}
# ---
```

The `minijupy` header key maps to `metadata.minijupy`. The `kernelspec` header
key maps to `metadata.kernelspec`. A notebook with no supported notebook
metadata has no header. Unsupported header keys are ignored and may be reported
as public parse warnings by `inspect`; malformed JSON in a supported header key
is an error.

### Cell Markers

Each cell starts at column 0 with a marker line:

- code: `# %%`
- markdown: `# %% [markdown]`
- raw: `# %% [raw]`

A marker may be followed by one space and a compact JSON object carrying public
cell marker fields, for example
`# %% {"id":"c1","tags":["keep"],"name":"load"}`. Supported marker fields are
`id`, `tags`, and `name`. `id` is the public cell identifier and is not cell
metadata. `tags` and `name` map to cell `metadata.tags` and `metadata.name`.
`to-text` must write `id` for every cell. `to-ipynb` must read marker `id`
when present and assign `c1`, `c2`, ... only for cells without marker ids.
Unsupported marker fields are ignored and may be reported as public parse
warnings by `inspect`; malformed marker JSON is an error.

Cell body rules:

- `code` cell body is the raw `source` lines.
- `markdown` and `raw` cell bodies are the `source` lines each prefixed with
  `# ` (a markdown/raw line that is empty is written as `#`). On parse, the
  leading `# ` / `#` prefix is removed to reconstruct `source`.
- A blank line separates a cell body from the next marker. Reconstruction must
  not introduce or drop interior blank lines of `source`.

`execution_count` and `outputs` are never written to the percent script. They
exist only in `.ipynb`.

## Version Marker

`metadata.minijupy` carries the deterministic freshness signal that replaces
wall-clock modification times:

```json
{"formats": "ipynb,py:percent", "version": 1}
```

- `formats` records the pairing format list.
- `version` is a non-negative integer. Both paired files carry their own
  `version`. A successful `pair` or `sync` write sets both files to the same
  `version`. An edit a user makes to one representation is expected to bump that
  file's `version`; the tool never inspects mtimes.

The benchmark sets `version` values explicitly in inputs to make the
authoritative source deterministic. The tool must never read the filesystem
clock.

## Config Format

The optional config path defaults to `minijupy.toml` in the input file's
directory. If `--config CONFIG` is supplied, use that file. A missing config
file is allowed and means defaults. The config base directory is the parent
directory of the config file when that file exists, and otherwise the current
working directory. Directory mappings below are resolved relative to this config
base directory. The config is a small `key = value` file, one pair per line;
blank lines and lines beginning with `#` are ignored.
Supported keys:

- `formats`: default pairing formats string, default `"ipynb,py:percent"`.
- `notebook_dir`: directory prefix for the `.ipynb` side of a directory pairing,
  default `""`.
- `script_dir`: directory prefix for the `.py` side of a directory pairing,
  default `""`.

When both `notebook_dir` and `script_dir` are non-empty, paired paths are
derived by swapping the directory prefix (see Paired Paths). Unsupported config
keys are ignored. Invalid supported values fail non-zero and write nothing.

## Conversion

### `to-text`

Read the input `.ipynb`, normalize it to the notebook model, and write a
`py:percent` script to `--output`. Strip `execution_count` and `outputs`. Print
a compact JSON result `{"written": "<output path>", "cells": <n>}`.

### `to-ipynb`

Read the input `.py` percent script, parse it to the notebook model, and write a
normalized `.ipynb` to `--output`. Code cells get `execution_count: null` and
`outputs: []`. Print `{"written": "<output path>", "cells": <n>}`.

Conversion must be roundtrip-preserving for everything the percent format can
represent: cell order, cell type, source, cell `tags`, cell `name`, and notebook
`metadata.minijupy` / `metadata.kernelspec`. `.ipynb` outputs and execution
counts are not representable in text and are therefore not preserved through a
text roundtrip; they are preserved only through `sync` (below).

## Paired Paths

Given an input file and the effective `formats`, the paired counterpart path is
derived deterministically:

- Same-directory pairing (default): the counterpart shares the stem and
  directory, swapping extension `.ipynb` <-> `.py`. `a/b/notebook.ipynb` pairs
  with `a/b/notebook.py`.
- Directory-mapping pairing: when `notebook_dir` and `script_dir` are set, the
  `.ipynb` side lives under `notebook_dir/` and the `.py` side under
  `script_dir/`, with the same relative stem path. With `notebook_dir = "nb"`
  and `script_dir = "scripts"`, `nb/sub/x.ipynb` pairs with
  `scripts/sub/x.py`.

For directory-mapping pairing, `notebook_dir` and `script_dir` are interpreted
relative to the config base directory. If an `.ipynb` input is not under
`notebook_dir`, or a `.py` input is not under `script_dir`, the command fails
non-zero and writes nothing. There is no fallback to same-directory pairing when
both directory prefixes are configured.

`inspect` and `status` report both paired paths regardless of which side was
supplied as `--input`.

## `pair`

Set pairing metadata on the input `.ipynb` notebook and create or update the
paired percent-script counterpart. `pair` accepts only `.ipynb` input; `.py`
input fails non-zero and writes nothing. Behavior:

- Ensure `metadata.minijupy.formats` equals the requested `--formats`.
- Compute the counterpart path from config and formats.
- Convert the input's current model into the counterpart representation and
  write it, setting both files' `metadata.minijupy.version` to the input's
  current `version` (or `0` if the input had no version).
- Print `{"paired_paths": ["<ipynb path>", "<py path>"], "version": <n>}`.

`pair` must not strip information the target representation can hold. Writing the
`.ipynb` side preserves any existing outputs already present in that file for
cells whose `id` still matches.

## `sync`

Synchronize the pair from the authoritative source. Source selection is
deterministic:

1. If `--source ipynb|text` is given, that representation is authoritative.
2. Otherwise the representation with the strictly greater
   `metadata.minijupy.version` is authoritative.
3. If both versions are equal and no `--source` is given, the pair is already in
   sync: write nothing and report `synced: true` with no changes.

Sync algorithm when a source is authoritative:

- Rebuild the other representation from the source model.
- When writing the `.ipynb` side, preserve `execution_count` and `outputs` from
  the existing `.ipynb` for each cell whose `id` matches a source cell; cells
  with no matching id get `execution_count: null` and `outputs: []`. If the
  source has no stable ids, fall back to positional matching and state nothing
  further is preserved beyond position.
- Set both files' `version` to the authoritative `version`.
- Print a compact JSON object with one schema for every sync outcome:
  `{"source": "ipynb|text|none", "wrote": ["<path>", ...], "version": <n>, "synced": true}`.
  When versions are equal and no `--source` is supplied, print
  `{"source": "none", "wrote": [], "version": <n>, "synced": true}`.

The authoritative source's inputs always win; the non-authoritative side's
inputs are overwritten. Only `.ipynb` outputs/execution counts survive, and only
for matching cells.

## `inspect`

Parse the input (without writing files) and print:

```json
{
  "input": "<path>",
  "format": "ipynb|text",
  "paired_paths": ["<ipynb path>", "<py path>"],
  "version": 0,
  "formats": "ipynb,py:percent",
  "cells": [],
  "warnings": []
}
```

`cells` contains the normalized cell model objects (without `outputs` bodies:
each cell reports `id`, `cell_type`, `source`, `metadata`, `execution_count`,
and `has_outputs` boolean). `warnings` lists deterministic public parse warnings
such as an unsupported notebook metadata key being dropped.

## `status`

Parse both representations (the input and its computed counterpart) without
writing files and print:

```json
{
  "paired_paths": ["<ipynb path>", "<py path>"],
  "source": "ipynb|text|none",
  "would_write": [],
  "roundtrip_ok": true,
  "differences": [],
  "missing": [],
  "errors": []
}
```

- `source` is the representation `sync` would treat as authoritative, or `none`
  when versions are equal.
- `would_write` lists the counterpart paths `sync` would rewrite (empty when in
  sync).
- `roundtrip_ok` is true when the two representations are model-equal for
  everything the text format can represent. This comparison ignores
  `execution_count` and `outputs`, because percent text cannot represent them.
  Output and execution-count preservation is evaluated through `sync`, not
  through `status.roundtrip_ok`.
- `differences` lists deterministic difference reasons (for example
  `cell-source`, `cell-order`, `cell-tags`, `metadata`).
- `missing` lists paired paths that do not exist on disk.
- `status` must never write any file.

## Error Behavior

These fail non-zero and write no files:

- unsupported command or missing required arguments
- input file does not exist
- `to-text` input is not `.ipynb`, or `to-ipynb` input is not `.py`
- `pair` input is not `.ipynb`
- malformed `.ipynb` JSON
- malformed percent script (bad header block, unparseable marker, malformed cell
  metadata JSON)
- duplicate cell `id` in an input `.ipynb` or percent script
- unsupported `formats` value (anything other than `ipynb,py:percent` in this
  mini task)
- invalid config value
- invalid `--source` value
- directory-mapping config is active and the input path does not fall under the
  expected side's configured directory prefix

If a `to-*`, `pair`, or `sync` command fails after starting, it must leave all
existing paired files byte-unchanged and must not create partial outputs.

## Global Invariants

- The same parsed notebook model must drive text conversion, `.ipynb`
  conversion, pairing metadata, sync result, and status report.
- Cell order, cell type, source, `tags`, and `name` are preserved across every
  conversion the percent format can represent.
- `execution_count` and `outputs` live only in `.ipynb`, are stripped from text,
  and are preserved across `sync` only for cells whose identity matches.
- Paired paths are a pure function of input path, `formats`, and config, and are
  reported identically by `inspect` and `status` regardless of which side is
  the input.
- Sync source selection is fully determined by `--source` or by integer
  `version`, never by wall-clock time.
- `status.would_write` is empty exactly when `sync` would write nothing, and
  `status.roundtrip_ok` agrees with an actual `to-text`/`to-ipynb` roundtrip.
- A failed command leaves every existing file unchanged with no partial output.
- Re-running a conversion or sync on already-synced inputs is idempotent and
  produces byte-identical outputs.

## Non-Goals

- No real Jupyter, kernel, or notebook execution.
- No full nbformat parity, no notebook outputs beyond opaque preservation.
- No Markdown, MyST, Quarto, Rmd, or pandoc formats; percent only.
- No non-Python language comment conventions.
- No wall-clock mtime, autosave, or ContentsManager/server behavior.
- No metadata-filter grammar; only the small fixed metadata subset above.
- No pipe/execute/external-command integration.
- No dependency on Jupytext internals, module names, or rendering order.

## Evaluation Style

Hidden tests are split into two scores.

- Unit tests exercise one feature module at a time: percent parsing, percent
  writing, `.ipynb` normalization, paired-path derivation, version-marker
  parsing, cell metadata/tag preservation, output strip/preserve policy, and
  per-command error behavior. When a test needs prior state it sets it up
  through the same public CLI commands or input files a user would use.
- System tests exercise interactions across at least two modules and carry a
  `system_dimension` label. Candidate dimensions include
  `roundtrip_consistency`, `sync_conflict_resolution`, `metadata_fanout`,
  `multi_file_pairing`, `status_report_consistency`, `output_preservation`, and
  `error_atomicity`.

The benchmark observes only public behavior: stdout JSON, stderr, exit codes,
and the contents of the `.ipynb` / `.py` / report files defined here. It never
inspects private implementation details, internal data structures, or file
modification times.
