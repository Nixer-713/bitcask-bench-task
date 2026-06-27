# Jupytext Source Grounding For 002

## Canonical Source

- Repository: `mwouts/jupytext`
- URL: `https://github.com/mwouts/jupytext`
- Checked revision: `40f3c5fd625f6b7c851bf3c632cd2f7f7e35c4f4`
- Local analysis checkout: `/tmp/jupytext-source`

The local checkout path is analysis context only. Evidence below cites
repository-relative source paths.

## Source Evidence Paths

- `website/src/content/docs/using/cli.md`
- `website/src/content/docs/using/paired-notebooks.md`
- `website/src/content/docs/using/config.md`
- `website/src/content/docs/formats/scripts.md`
- `website/src/content/docs/reference/faq.md`
- `src/jupytext/cli.py`
- `src/jupytext/paired_paths.py`
- `src/jupytext/pairs.py`
- `src/jupytext/sync_pairs.py`
- `src/jupytext/combine.py`
- `src/jupytext/cell_reader.py`
- `src/jupytext/cell_to_text.py`
- `src/jupytext/cell_metadata.py`
- `src/jupytext/config.py`
- `src/jupytext/formats.py`
- `tests/unit/test_paired_paths.py`
- `tests/functional/cli/test_source_is_newer.py`
- `tests/functional/cli/test_synchronous_changes.py`
- `tests/functional/others/test_cell_tags_are_preserved.py`
- `tests/functional/round_trip/test_mirror.py`
- `tests/external/pre_commit/test_pre_commit_1_sync.py`
- `tests/external/pre_commit/test_pre_commit_mode.py`
- `tests/external/pre_commit/test_pre_commit_scripts.py`

## Why 002 Exists

`jupytext-realrepo-001` was source-grounded and reference-satisfiable, but
validation showed no positive unit/system gap: reference and three candidate
agents all passed 34/34. The likely reason is that the mini-task collapsed into
one canonical normalized notebook model plus serializers. That is good
engineering, but weak benchmark pressure.

`jupytext-realrepo-002` should keep the same source project but re-ground the
task around public paired-notebook state flow:

```text
paired files + config + prior sync state
-> status/check/conflict report
-> sync/update decision
-> output preservation
-> atomic file changes
```

The goal is not to force failure. The goal is to make system cases arise from
real Jupytext public behavior where locally correct conversion, pairing, or
status logic can still leave global state inconsistent.

## Public Behavior Inventory

### CLI Conversion And Pairing

Jupytext exposes CLI conversion between notebook formats. The public CLI docs
show `--to py`, `--to py:percent`, `--to notebook`, explicit `--output`, and
stdin/stdout conversion examples (`website/src/content/docs/using/cli.md`,
lines 8-26).

The CLI parser exposes `--to`, `--output`, and `--update`. `--update` is
documented in code as preserving output cells when writing to an existing
`.ipynb` destination (`src/jupytext/cli.py`, lines 109-151).

Pairing is public through `--set-formats`, which turns a notebook into one or
more alternative representations and triggers creation/update of paired files
(`src/jupytext/cli.py`, lines 153-159). The paired-notebook docs state that
pairing adds a `"jupytext": {"formats": ...}` entry to notebook metadata
(`website/src/content/docs/using/paired-notebooks.md`, lines 19-27).

### Sync And Freshness

The public CLI has `--sync`, which updates paired representations; the docs say
it updates whichever of `.ipynb` / text is outdated
(`website/src/content/docs/using/cli.md`, lines 28-32). The CLI help states
that input cells are taken from the last-modified file and outputs from the
`.ipynb` file if present (`src/jupytext/cli.py`, lines 163-170).

The paired-notebook docs describe the same public state flow: inputs are loaded
from the most recent file in the pair, outputs from `.ipynb`, and saving updates
all files in the pair (`website/src/content/docs/using/paired-notebooks.md`,
lines 12-15). They also describe simultaneous editing in Jupyter and a text
editor as a real user workflow with conflict/reload concerns
(`website/src/content/docs/using/paired-notebooks.md`, lines 29-41).

Tests cover source-newer checks: converting or syncing from an older source
raises errors (`tests/functional/cli/test_source_is_newer.py`, lines 12-70).
Real mtimes are unsuitable for a deterministic benchmark, but the public
behavior to adapt is source freshness, stale-source rejection, and explicit
source choice.

### Paired Path Derivation

Jupytext supports simple same-directory pairs and project-level pairing in
subfolders. Config docs show global pairing with `formats = "ipynb,py:percent"`
and subfolder pairing such as `"notebooks/" = "ipynb"` and `"scripts/" =
"py:percent"` (`website/src/content/docs/using/config.md`, lines 10-43).

`src/jupytext/paired_paths.py` implements the source path model:

- `base_path` checks extension, suffix, prefix, prefix directory, and config
  boundary before deriving a base path (`src/jupytext/paired_paths.py`, lines
  86-191).
- `full_path` reconstructs paired paths from a base path and format prefix /
  suffix (`src/jupytext/paired_paths.py`, lines 234-288).
- `paired_paths` computes all paired paths and rejects paths not covered by the
  pairing formats or duplicate paired paths (`src/jupytext/paired_paths.py`,
  lines 307-332).

Tests cover simple pairs, tree mapping, config-directory limits, suffix/prefix
errors, duplicate paths, and Windows separators (`tests/unit/test_paired_paths.py`,
lines 23-240).

### Text Notebook Format

The public percent format uses `# %%` cell markers. Docs state that cells can
have title, cell type (`markdown`, `md`, `raw`, or omitted for code), and cell
metadata (`website/src/content/docs/formats/scripts.md`, lines 8-28). The same
page gives code and markdown examples for `# %%` and `# %% [markdown]`
(`website/src/content/docs/formats/scripts.md`, lines 30-57).

The source has independent reader/writer paths:

- `src/jupytext/cell_reader.py` parses marker options, cell type, source, and
  metadata into notebook cells.
- `src/jupytext/cell_to_text.py` exports cells to text while filtering
  metadata.
- `src/jupytext/cell_metadata.py` implements metadata conversion and parsing.

Tags are explicitly expected to survive roundtrip in public formats:
`tests/functional/others/test_cell_tags_are_preserved.py`, lines 18-29.

### Output Preservation

Jupytext's docs distinguish text inputs from `.ipynb` outputs. The paired docs
say `.ipynb` contains outputs, while text is easier to edit/version
(`website/src/content/docs/using/paired-notebooks.md`, lines 8-17). The FAQ
states that paired text contains input cells and selected metadata, while
`.ipynb` restores outputs and filtered metadata when loaded.

`src/jupytext/combine.py` is the key source signal. `combine_inputs_with_outputs`
combines text/source cells from one notebook with outputs and metadata from
another (`src/jupytext/combine.py`, lines 36-116). It uses
`map_outputs_to_inputs` to match output cells to input cells with multiple
rules: cell type/source in order, unused output matching, suffix matching, then
increasing-position fallback (`src/jupytext/combine.py`, lines 119-177).

This behavior is more system-like than plain conversion: a candidate can pass
local `to-text` and `to-ipynb` tests but still lose or attach outputs to the
wrong cells during sync.

### Roundtrip And Status-Like Checks

CLI docs emphasize roundtrip stability and expose `--test` / `--test-strict`
(`website/src/content/docs/using/cli.md`, lines 86-99). The CLI parser includes
both flags (`src/jupytext/cli.py`, lines 214-223). Roundtrip tests exercise
`.ipynb -> percent -> .ipynb` and text -> `.ipynb` -> text paths
(`tests/functional/round_trip/test_mirror.py`, lines 31-85).

The mini-task should not reproduce full Jupytext `--test`, but a deterministic
`status` / `check` report is a fair adaptation of public roundtrip and
freshness checking behavior.

### Error Atomicity And Concurrent Modification

Jupytext has public tests for synchronous edits: if a paired file changes while
Jupytext is running, it raises `SynchronousModificationError` and avoids partial
counterpart creation (`tests/functional/cli/test_synchronous_changes.py`, lines
15-70). Similar tests for `--to ipynb` verify that a failed conversion leaves no
new `.ipynb` output (`tests/functional/cli/test_synchronous_changes.py`, lines
73-111).

This is a strong source-derived basis for mini-task atomicity: failed sync,
malformed input, stale-source rejection, path mismatch, or conflict detection
must not half-update paired files or reports.

## Capability Map

| Capability | Public input | Public output | Persistent state / artifacts | Downstream effects |
| --- | --- | --- | --- | --- |
| Convert to text | `.ipynb`, format/config | `py:percent` file or stdout/report | text representation | affects roundtrip, sync, status, pre-commit checks |
| Convert to ipynb | `py:percent` text | `.ipynb` file/report | notebook representation | affects output preservation and paired sync |
| Pair notebook | `.ipynb`, formats/config | paired files + metadata | `.ipynb`, text counterpart, pairing metadata | determines paired paths and future sync/status |
| Paired path resolution | input path + formats/config | paired path list or error | none, but config is read | controls all file writes and mismatch errors |
| Sync source selection | paired files + freshness signal | chosen source + writes | both paired files | drives output preservation, missing counterpart creation, status |
| Output preservation | source cells + existing `.ipynb` outputs | merged `.ipynb` | `.ipynb` outputs/execution counts | exposes wrong cell matching in system cases |
| Status/check report | paired files + config + prior state | JSON report | optional report/state if PRD defines it | predicts sync writes, conflicts, missing pairs, roundtrip ok |
| Error atomicity | malformed input/config, stale/conflict, path mismatch | nonzero/stderr/report | no partial writes | protects existing pair state |

## Four-Layer Decomposition

### A. Input Layer

- CLI arguments: conversion, pairing, sync, paired-paths/status/test-like
  commands (`src/jupytext/cli.py`, lines 109-223).
- Source files: `.ipynb` JSON and `py:percent` scripts.
- Config files: `jupytext.toml` / `pyproject.toml`; source docs define global
  and subfolder pairing (`website/src/content/docs/using/config.md`, lines
  10-43).
- Existing persisted state: paired files, pairing metadata, existing `.ipynb`
  outputs, and freshness/conflict signals.

### B. Core State / Artifact Layer

- Notebook input model: ordered cells, cell type, source, metadata, outputs.
- Pair graph: one logical notebook can have multiple paired artifact paths.
- Freshness/conflict state: real Jupytext uses mtimes; the mini-task should use
  deterministic public markers or an explicit state/check file.
- Output map: existing `.ipynb` outputs must be matched to source cells during
  sync, not blindly copied by file.

### C. Derived View Layer

- Percent script representation.
- Normalized `.ipynb` representation.
- Paired path list / manifest.
- Status/check report: source choice, stale/missing/conflict, roundtrip result,
  predicted writes, and difference reasons.
- Optional project-level report for `--all` if included in the PRD.

### D. Mutation / Recovery Layer

- `pair` creates or updates paired files and metadata.
- `sync` updates missing/stale counterparts and preserves outputs.
- `--source` or conflict-resolution command chooses a side when automatic sync
  is unsafe.
- Failed parse/config/path/conflict cases leave every existing artifact
  unchanged.
- Repeated sync/status after clean state is idempotent.

## Candidate Benchmark Shape For 002

Likely program name: `minijupy2.py` or `minijupy.py` if the task directory keeps
the name scoped.

Potential public commands:

- `inspect --input FILE [--config CONFIG]`
- `to-text --input NOTEBOOK.ipynb --output NOTEBOOK.py`
- `to-ipynb --input NOTEBOOK.py --output NOTEBOOK.ipynb`
- `pair --input NOTEBOOK.ipynb [--config CONFIG]`
- `status --input FILE [--config CONFIG] [--all]`
- `check --input FILE [--config CONFIG] [--all]`
- `sync --input FILE [--config CONFIG] [--source ipynb|text] [--all]`

The important difference from 001 is that `status` / `check` should be first
class, not only an explanatory wrapper around conversion. They should be
observable public outputs that predict or verify `sync` effects.

## PRD Boundary Proposal

Do not draft PRD yet. These are source-grounded boundary recommendations for
review before PRD writing.

| Source behavior | 002 decision candidate | Reason |
| --- | --- | --- |
| `.ipynb` model | Keep simplified | Needed for conversion, outputs, and status. |
| `py:percent` | Keep, percent-only | Source docs make percent public; avoids Markdown/Myst breadth. |
| `--to` conversion | Keep adapted as explicit `to-text` / `to-ipynb` | Unit-testable local modules. |
| Pairing metadata | Keep | Public docs and CLI expose formats metadata. |
| Directory pairing | Keep one deterministic subset | Source supports subfolder pairing; strong system pressure. |
| Real mtimes | Exclude | Non-deterministic; adapt to public version/hash/state markers. |
| Source freshness / stale rejection | Keep adapted | Public `--check-source-is-newer` behavior and tests support it. |
| Conflict detection | Keep adapted | Source docs discuss simultaneous edits; tests cover unsafe modification errors. |
| Output preservation | Keep and strengthen | Source combines inputs with `.ipynb` outputs; key system invariant. |
| `--test` / roundtrip | Keep adapted as `check`/`status` | Public behavior, but use deterministic JSON report. |
| `--all` project operation | Consider keeping | Source config supports project/global pairing; pre-commit docs/tests imply multi-file sync workflows. |
| Pre-commit mode | Exclude exact Git semantics | Use only as source signal for project-level sync/check, not Git index behavior. |
| Metadata filters | Exclude full grammar | Keep fixed metadata subset; full filters add noise. |
| Jupyter server / ContentsManager | Exclude | Environment-heavy; only source state concepts are reused. |
| Notebook execution / pipes | Exclude | External tools and execution are out of benchmark scope. |

## Stronger 002 System Dimensions

These dimensions should guide later PRD/rubric work.

| Dimension | Crossed modules | Why it is system-level |
| --- | --- | --- |
| `status_sync_consistency` | pair path resolution -> parse both files -> freshness/conflict decision -> status report -> sync writes | Status must predict actual sync effects. |
| `conflict_resolution` | prior sync state -> both files changed -> status/check conflict -> explicit source override -> clean state | Local conversion can pass while conflict logic fails. |
| `output_preservation_under_edit` | text edits -> source selection -> output map -> rewritten `.ipynb` -> status clean | Requires correct matching, not only serialization. |
| `multi_pair_project_flow` | config mapping -> multiple pairs -> status/check `--all` -> sync subset/all -> final report | Prevents hard-coded single-file behavior. |
| `path_mapping_invariants` | config base -> paired paths -> pair/sync/status/check | Same paths must appear across commands and errors. |
| `roundtrip_report_consistency` | to-text -> to-ipynb -> normalized comparison -> status/check differences | Report must match actual conversions. |
| `error_atomicity` | validation -> planned writes -> malformed/conflict/path error -> unchanged files | Mirrors source tests for synchronous edits and failed writes. |

## Likely Unit Modules

- CLI command validation and JSON stdout/stderr.
- `.ipynb` parser/normalizer with cell ids, metadata, outputs.
- Percent parser/writer for `# %%`, `[markdown]`, `[raw]`, tags/name/id.
- Config parser for pairing formats and directory mapping.
- Paired path derivation and mismatch errors.
- Source freshness marker parsing.
- Single-pair status report.
- Single-pair sync source selection.
- Output preservation map by id/content/position as publicly defined.
- Roundtrip check for representable fields.
- Error atomicity for malformed JSON/percent/config/path mismatch.

## Likely System Workflows

1. **Pair -> status -> sync clean loop**
   - Pair a notebook, inspect paired paths, run status, sync, then status again.
   - Checks path consistency, no-op idempotence, and report/write agreement.

2. **Text edit with output preservation**
   - Start with `.ipynb` containing outputs, edit text source, sync from text,
     verify inputs update while matching outputs remain attached.

3. **Both sides changed conflict**
   - Establish clean pair, mutate both sides with public version/hash markers,
     require status/check conflict, reject normal sync, resolve with explicit
     source, then status clean.

4. **Directory-mapped project**
   - Use config mapping `notebooks/` to `scripts/`, multiple files, one missing
     counterpart, one stale pair, one clean pair.
   - Run `status --all` and `sync --all`; report and resulting files must agree.

5. **Roundtrip report as oracle**
   - Create a script with tags/name/markdown/raw/code, convert to `.ipynb`, back
     to text, and require `check` to report no representable differences.

6. **Error atomicity across pair set**
   - One malformed pair in a project-level operation should not leave
     half-written outputs unless PRD explicitly chooses partial-success
     semantics.

## Fairness And Non-Goals

- Every future rubric case must be inferable from the PRD.
- Tests should observe only stdout JSON, stderr, exit code, and PRD-defined
  `.ipynb`, `.py`, config, status/check/state files.
- Do not inspect Jupytext internals, Python module names, private algorithms, or
  exact Jupytext serialization beyond the PRD-defined mini format.
- Do not use real file modification times.
- Do not require notebook execution, kernels, Jupyter server behavior,
  ContentsManager behavior, Git/pre-commit internals, external tools, pipes,
  full nbformat parity, Markdown/MyST/Quarto/Rmd, or metadata-filter grammar.
- Do not add hidden expected outputs only to make candidates fail.
- If a public state file is introduced, it must be fully model-visible in the
  PRD and justified as a deterministic adaptation of mtime/source freshness and
  conflict checks.

## Open Questions Before PRD

1. Should 002 introduce a public `.minijupy-state.json` file to replace real
   mtimes and record last-synced per-pair hashes/versions?
2. Should conflict be defined as "both sides changed since last sync" rather
   than "versions equal/different"?
3. Should `status --all` and `sync --all` be in v1, or should project-level flow
   wait until after single-pair PRD validation?
4. Should project-level sync be all-or-nothing, or should it allow partial
   success with an explicit report?
5. Should output preservation match by explicit cell id first, then source/type,
   then position, mirroring the source's multi-rule approach, or should the
   mini task expose a simpler id-first rule?
6. Should `check` be separate from `status`, or should one command report both
   sync freshness and roundtrip differences?

## Initial Judgment

`jupytext-realrepo-002` is viable only if it avoids repeating 001's canonical
model collapse. The strongest source-grounded direction is not "more formats";
it is deterministic paired-file state management:

```text
config + paired artifacts + prior sync state
-> status/check
-> conflict/source decision
-> sync writes
-> output preservation
-> atomicity
```

Proceed to a boundary decision note before writing PRD. Do not draft
`prd.md`, `rubric.json`, or `requirement_map.md` until the state/conflict/report
boundaries are explicitly chosen.
