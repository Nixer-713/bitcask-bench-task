# Jupytext Source Grounding

## Canonical Source

- Repository: `mwouts/jupytext`
- URL: https://github.com/mwouts/jupytext
- Checked revision: `40f3c5fd625f6b7c851bf3c632cd2f7f7e35c4f4`
- Local analysis checkout: `/tmp/jupytext-source`

The local checkout path is analysis context only. Evidence below uses
repository-relative paths.

## Source Evidence Paths

- `README.md`
- `website/src/content/docs/using/cli.md`
- `website/src/content/docs/using/paired-notebooks.md`
- `website/src/content/docs/using/config.md`
- `website/src/content/docs/formats/scripts.md`
- `website/src/content/docs/formats/markdown.md`
- `src/jupytext/cli.py`
- `src/jupytext/jupytext.py`
- `src/jupytext/paired_paths.py`
- `src/jupytext/pairs.py`
- `src/jupytext/sync_pairs.py`
- `src/jupytext/cell_reader.py`
- `src/jupytext/cell_to_text.py`
- `src/jupytext/cell_metadata.py`
- `src/jupytext/config.py`
- `src/jupytext/formats.py`
- `tests/functional/cli/test_cli.py`
- `tests/functional/cli/test_source_is_newer.py`
- `tests/functional/cli/test_synchronous_changes.py`
- `tests/functional/others/test_cell_tags_are_preserved.py`
- `tests/functional/others/test_cell_metadata.py`
- `tests/functional/round_trip/test_mirror.py`
- `tests/functional/simple_notebooks/test_ipynb_to_py.py`
- `tests/unit/test_paired_paths.py`
- `tests/unit/test_formats.py`

## Source Capability Map

| Capability | Source signal | Benchmark relevance |
| --- | --- | --- |
| Notebook parsing | `src/jupytext/jupytext.py` reads `.ipynb` and text notebooks into notebook objects; README describes `.ipynb` as one paired representation | Mini task can define a small public notebook JSON model with cells, metadata, outputs, and execution counts |
| Text notebook parsing | `website/src/content/docs/formats/scripts.md` documents `py:percent`; `website/src/content/docs/formats/markdown.md` documents Markdown code-cell forms | Percent script is the best first target; Markdown can be deferred unless needed for more heterogeneity |
| Conversion `.ipynb -> text` | `website/src/content/docs/using/cli.md` documents `jupytext --to py:percent notebook.ipynb`; `tests/functional/cli/test_cli.py` covers conversions | Unit cases can check cell markers, markdown/code/raw cells, metadata, and output stripping policy |
| Conversion `text -> .ipynb` | CLI docs show `--to notebook notebook.py`; roundtrip tests cover text back to notebook | Unit cases can parse percent script into normalized notebook JSON |
| Pairing config and paired paths | README and config docs show `formats = "ipynb,py:percent"` and `--set-formats`; `src/jupytext/paired_paths.py` and `tests/unit/test_paired_paths.py` cover paired path derivation | System cases can require config-derived alternate paths and consistent manifests/reports |
| Sync/newest-source decision | README and paired notebook docs state inputs are loaded from the most recent paired file; `src/jupytext/pairs.py` implements latest input/output selection | Real timestamps are risky; mini task should use deterministic public version markers or explicit source priority |
| Output preservation policy | README says text notebooks store inputs and optionally metadata; paired notebooks reload outputs from `.ipynb`; `src/jupytext/sync_pairs.py` combines inputs with outputs | System cases can check text edits update inputs while `.ipynb` outputs remain attached to matching cells |
| Metadata and tags | CLI docs describe metadata filters; `tests/functional/others/test_cell_tags_are_preserved.py` shows tags roundtrip in main formats | Mini task can keep a small public metadata subset: notebook metadata, cell tags, and selected cell metadata |
| Cell type preservation | Percent docs define code, markdown, and raw markers; source read/write modules distinguish cell types | Unit cases can isolate cell type parsing; system cases can require cell type consistency across roundtrip/sync/status |
| Status/check reporting | CLI docs expose `--test`, `--test-strict`, `--paired-paths`, and `--check-source-is-newer`; CLI source has corresponding parser options | Mini task can provide deterministic `status`/`check` commands rather than relying on wall-clock mtime |
| Error behavior / atomicity | CLI tests cover invalid options, non-notebook paths, synchronous edits, and source-newer checks; sync tests assert no counterpart creation on concurrent edit failure | Mini task should require failed conversion/sync/check to leave all public files unchanged |

## Candidate Benchmark Shape

Likely program: `minijupy.py`

Possible public commands:

- `inspect --input NOTEBOOK_OR_TEXT [--config CONFIG]`
  - Print normalized notebook model: cells, metadata, paired formats, paired paths,
    version markers, and public validation warnings.
- `to-text --input NOTEBOOK.ipynb --output NOTEBOOK.py [--format py:percent]`
  - Convert the public notebook JSON model to a percent script.
- `to-ipynb --input NOTEBOOK.py --output NOTEBOOK.ipynb`
  - Convert percent script back to normalized notebook JSON.
- `pair --input NOTEBOOK.ipynb --formats ipynb,py:percent`
  - Write/update pairing metadata and create paired text output.
- `sync --input NOTEBOOK_OR_TEXT [--config CONFIG]`
  - Determine the authoritative input representation and update paired files.
- `status --input NOTEBOOK_OR_TEXT [--config CONFIG]`
  - Print public JSON describing paired paths, freshness/source choice,
    roundtrip status, pending writes, and mismatch reasons.

Public outputs and observable files:

- normalized JSON stdout for `inspect` and `status`
- generated `.ipynb` JSON files
- generated `.py` percent-script files
- optional project-level JSON report/manifest if the PRD needs a global invariant
- exit code and stderr for invalid input, conflicts, and atomicity failures

The strongest shape is a deterministic paired-notebook CLI where the same
notebook model drives text conversion, JSON conversion, pairing metadata,
sync result, status report, and error behavior.

## PRD Boundary Proposal

| Source behavior | Keep / simplify / exclude | Proposed boundary |
| --- | --- | --- |
| `.ipynb` notebook model | Keep simplified | Support nbformat-like JSON with `metadata`, `cells`, `cell_type`, `source`, `metadata`, `execution_count`, and `outputs` |
| `py:percent` scripts | Keep | Define a small percent format: `# %%`, `# %% [markdown]`, `# %% [raw]`, optional JSON metadata after marker |
| Markdown notebook formats | Defer or simplify | Prefer excluding in v1 to avoid repeating Marmite; optionally add only if source-grounding shows percent-only is too narrow |
| Full language support | Exclude | Python percent scripts only; no Julia/R/MATLAB language-specific comments |
| `--to` conversion | Keep adapted | Use explicit commands `to-text` and `to-ipynb` with deterministic output paths |
| `--set-formats` pairing | Keep adapted | Support `ipynb,py:percent` and maybe directory-prefix pairing from `jupytext.toml` subset |
| Paired path prefixes/suffixes | Simplify | Support same-directory pair first; consider one public config mapping `notebooks/ -> scripts/` only if needed for system pressure |
| `--sync` newest-source by mtime | Simplify | Avoid real timestamps; define public integer `jupytext_version_marker` or `x-minijupy-version` in both representations |
| Output preservation | Keep adapted | Text source updates inputs; `.ipynb` remains output source when present; cell outputs preserve by cell id or position as PRD defines |
| Metadata filters | Simplify | Preserve only notebook metadata keys under `jupytext`, plus cell `tags` and maybe `name`; exclude full filter grammar |
| Execution count and outputs | Decide before PRD | Likely preserve in `.ipynb`, strip from text, and preserve across sync from `.ipynb` when cell identity matches |
| Roundtrip test | Keep adapted | `status` or `check` can compare normalized notebook models after conversion |
| Pipe/execute/check external command | Exclude | External commands and notebook execution introduce dependency and environment noise |
| Jupyter ContentsManager | Exclude | Server integration and autosave conflict UI are out of scope |
| Concurrent edit detection | Simplify | Use deterministic pre/post version markers rather than monkeypatch/timestamps |
| Full Jupytext format parity | Exclude | No exact Jupytext internals, full Markdown, MyST, Quarto, Rmd, pandoc, marimo, or metadata filter grammar |

## Resolved Boundary Decisions

These decisions are intended to keep the mini task source-grounded,
deterministic, and scoreable before `requirement_map.md` or `rubric.json` are
drafted.

- Format scope: v1 uses only Python `py:percent` scripts plus `.ipynb`.
  Markdown, MyST, Quarto, Rmd, pandoc, marimo, and non-Python comment
  conventions are excluded.
- Freshness: real mtimes are excluded. Sync uses public integer
  `metadata.minijupy.version` markers, with `--source ipynb|text` as an
  explicit override.
- Header keys: percent scripts use exact `minijupy` and `kernelspec` header
  keys, each serialized as compact JSON.
- Cell identity: percent markers may include top-level `id`, `tags`, and
  `name`; `id` is a public cell identifier, not cell metadata.
- Metadata scope: preserve only `metadata.minijupy`, `metadata.kernelspec`,
  cell `tags`, and cell `name`.
- Output policy: percent text strips `execution_count` and `outputs`; sync
  preserves `.ipynb` execution counts and outputs for matching cells.
- Pair input: `pair` accepts `.ipynb` input only and writes/updates the
  percent-script counterpart.
- Directory mapping: `notebook_dir` and `script_dir` are relative to the config
  base directory. Inputs outside the configured side's prefix fail non-zero and
  write nothing.
- Status semantics: `status.roundtrip_ok` ignores `execution_count` and
  `outputs`; output preservation is a `sync` invariant.

## Likely Unit Modules

- CLI argument validation and JSON stdout/stderr behavior.
- Minimal `.ipynb` parsing and normalization.
- Percent script parsing: marker splitting, cell type extraction, metadata
  extraction, and source reconstruction.
- Percent script writing: code/markdown/raw markers and comment stripping.
- Pairing metadata parsing from notebook metadata and config.
- Paired path derivation for same-directory `ipynb,py:percent`.
- Cell metadata/tag preservation.
- Execution count/output strip-or-preserve policy.
- Status report for clean, stale text, stale ipynb, and missing counterpart.
- Error handling for malformed JSON, malformed percent metadata, duplicate cell
  ids, and unsupported formats.

## Likely System Dimensions

| Dimension | Crossed modules | Why it pressures composition |
| --- | --- | --- |
| `roundtrip_consistency` | `.ipynb` parser -> percent writer -> percent parser -> normalized notebook comparison | One-way conversions can pass while losing metadata, cell type, order, or source details |
| `sync_conflict_resolution` | paired path config -> freshness/version decision -> input merge -> both file writes -> status | Requires the same source choice to drive writes and reporting |
| `metadata_fanout` | notebook/cell metadata -> text markers -> rebuilt JSON -> inspect/status | Metadata must survive several representations without leaking unsupported fields |
| `multi_file_pairing` | config -> paired paths -> conversion -> manifest/status across multiple notebooks | Candidates often hard-code same-directory pairs and fail project-level mappings |
| `status_report_consistency` | parse both representations -> compare normalized models -> report pending updates -> no-write status | Status can drift from actual conversion/sync behavior |
| `output_preservation` | text input cells -> `.ipynb` output cells -> sync merge -> rebuilt notebook | Preserving outputs while replacing inputs is a real paired-notebook invariant |
| `error_atomicity` | validation -> conversion/sync write plan -> file writes -> rollback/no partial outputs | Failures must not leave half-updated pairs or misleading status |

## Review Points Before Requirement Map

- Confirm that percent-only scope is enough to differentiate this task from the
  previous Marmite static-site task.
- Confirm that public version markers are acceptable as a deterministic
  adaptation of Jupytext's mtime-based newest-source behavior.
- Confirm that `id` in percent marker JSON is fair and visible enough for output
  preservation tests.
- Confirm that directory-prefix mismatch should fail rather than falling back
  to same-directory pairing.
- Confirm that `status.roundtrip_ok` ignoring outputs/execution counts is
  explicit enough to avoid hidden rubric assumptions.

## Initial Judgment

`mwouts/jupytext` is a strong candidate for the next task. It has public docs,
source, and tests around conversion, pairing, sync, roundtrip, metadata, tags,
paired paths, source freshness, and error handling. The likely mini-task can be
made source-grounded without requiring full Jupytext parity.

The main risk is scope creep. The next step after PRD boundary cleanup should
be `requirement_map.md`, followed by `rubric.json`; validation assets should
remain off `main`.
