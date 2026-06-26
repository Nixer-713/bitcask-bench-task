# Mini Jupytext Requirement Map

Public packet: `prd.md`

Source grounding: `doc/source_repo.md`

Rubric: `rubric.json` (34 cases: 20 unit, 14 system)

## Public Requirements

| ID | Capability | Public basis |
| --- | --- | --- |
| `REQ-cli` | Provide supported commands, compact JSON stdout on success, non-zero failures, useful stderr, and no partial writes | Invocation, Error Behavior |
| `REQ-notebook-model` | Parse and normalize the nbformat-like JSON model, including cell ids, cell types, source, metadata, execution counts, and outputs | Notebook JSON Model |
| `REQ-percent-format` | Parse and write `py:percent` headers, cell markers, marker JSON `id`/`tags`/`name`, and code/markdown/raw bodies | Percent Script Format |
| `REQ-version-marker` | Use deterministic `metadata.minijupy.version` freshness markers and never use wall-clock mtimes | Version Marker, Global Invariants |
| `REQ-config` | Parse the `minijupy.toml` subset and define the config base directory | Config Format |
| `REQ-paired-paths` | Derive same-directory and `notebook_dir`/`script_dir` mapped paths, with mismatch failure | Paired Paths, Error Behavior |
| `REQ-to-text` | Convert `.ipynb` to percent text while stripping execution counts and outputs | Conversion, `to-text` |
| `REQ-to-ipynb` | Convert percent text to normalized `.ipynb` with empty outputs and null execution counts | Conversion, `to-ipynb` |
| `REQ-pair` | Pair `.ipynb` input only, set pairing metadata, and create/update the percent counterpart | `pair` |
| `REQ-sync` | Select source by `--source` or version, no-write on equal versions, and emit one unified sync JSON schema | `sync` |
| `REQ-output-preservation` | Preserve existing `.ipynb` execution counts and outputs during sync for matching cells | `sync`, Global Invariants |
| `REQ-inspect` | Print normalized public model, paired paths, version, formats, and warnings without writing files | `inspect` |
| `REQ-status` | Report paired paths, source, would-write paths, roundtrip status, differences, missing paths, and errors without writing | `status` |
| `REQ-error-atomic` | Fail malformed inputs/config/unsupported commands with no partial writes and no byte changes to existing paired files | Error Behavior |
| `REQ-system-invariants` | Keep notebook model, conversions, pairing, sync, status, and atomicity mutually consistent | Goal, Global Invariants |

## Source Grounding Notes

| Requirement | Source-derived basis | Mini-task adaptation | Grounding |
| --- | --- | --- | --- |
| `REQ-cli` | `README.md` and `website/src/content/docs/using/cli.md` document Jupytext CLI conversion, pairing, sync, and tests; `src/jupytext/cli.py` implements the command surface | Mini task uses explicit subcommands and compact JSON reports instead of the full Jupytext CLI option set | Deterministic adaptation |
| `REQ-notebook-model` | `src/jupytext/jupytext.py` reads/writes notebooks; Jupytext works from nbformat-like notebook cells and metadata | Model is reduced to `metadata`, ordered `cells`, `id`, `cell_type`, `source`, selected metadata, execution counts, and outputs | Directly source-derived with scoped model |
| `REQ-percent-format` | `README.md` and `website/src/content/docs/formats/scripts.md` describe `py:percent` markers, markdown/raw cell types, and cell metadata | Percent syntax is fixed to a small deterministic subset with exact `minijupy`/`kernelspec` headers and marker JSON | Directly source-derived with deterministic syntax |
| `REQ-version-marker` | `website/src/content/docs/using/paired-notebooks.md` and `src/jupytext/pairs.py` describe newest-source behavior; Jupytext normally uses mtimes | Real mtimes are replaced by public integer version markers so tests are reproducible | Deterministic adaptation |
| `REQ-config` | `website/src/content/docs/using/config.md` documents `jupytext.toml` and project pairing formats | Config is reduced to `formats`, `notebook_dir`, and `script_dir` with a fixed base-directory rule | Directly source-derived with scoped TOML subset |
| `REQ-paired-paths` | `src/jupytext/paired_paths.py` and `tests/unit/test_paired_paths.py` cover same-directory and directory-prefix pairing | Mini task keeps same-directory pairing and one `notebook_dir`/`script_dir` mapping; mismatches fail rather than falling back | Directly source-derived with simplified path rules |
| `REQ-to-text` | CLI docs and `tests/functional/cli/test_cli.py` cover converting notebooks to text; `src/jupytext/jupytext.py` writes text formats | Mini task supports only `.ipynb -> py:percent` and requires output stripping because text cannot represent outputs | Directly source-derived |
| `REQ-to-ipynb` | CLI docs cover `--to notebook notebook.py`; roundtrip tests cover text back to notebook | Mini task supports only percent text to normalized `.ipynb` with empty outputs/null execution counts | Directly source-derived |
| `REQ-pair` | README, paired-notebook docs, config docs, and CLI docs cover `--set-formats ipynb,py:percent` | Mini task restricts `pair` input to `.ipynb` for deterministic scoring | Directly source-derived with input restriction |
| `REQ-sync` | README and paired-notebook docs state inputs come from the most recent paired file; `src/jupytext/sync_pairs.py` and `src/jupytext/pairs.py` implement pair sync | Source selection is by version marker or explicit `--source`, and JSON schema is fixed for all outcomes | Deterministic adaptation |
| `REQ-output-preservation` | README and paired-notebook docs state outputs are reloaded from `.ipynb`; `src/jupytext/sync_pairs.py` combines inputs with outputs | Mini task preserves `.ipynb` outputs/execution counts by public cell id or position fallback | Directly source-derived with public matching rule |
| `REQ-inspect` | Source read paths expose parsed notebook state internally; tests inspect conversions and metadata preservation | `inspect` is a mini-task command to expose parse behavior without hidden implementation inspection | Deterministic adaptation |
| `REQ-status` | CLI docs expose `--test`, `--test-strict`, `--paired-paths`, and `--check-source-is-newer`; tests cover source-newer behavior | `status` consolidates no-write paired-path, freshness, roundtrip, difference, and missing-path reporting into one JSON object | Deterministic adaptation |
| `REQ-error-atomic` | CLI tests cover invalid formats/options and synchronous edit/source-newer failures; sync tests assert no counterpart creation on failure | Mini task requires all failed write commands to leave existing files byte-unchanged | Directly source-derived with stronger public atomicity rule |
| `REQ-system-invariants` | Jupytext's paired notebook design requires multiple representations to agree; roundtrip, pairing, sync, metadata, and path tests cover this | Mini task makes global consistency an explicit benchmark target across public commands and files | Directly source-derived with benchmark framing |

## Unit Coverage

| Case | Focus | Requirement refs |
| --- | --- | --- |
| `JTU001` | `inspect` command public JSON for an `.ipynb` input | `REQ-cli`, `REQ-inspect`, `REQ-notebook-model` |
| `JTU002` | Missing `.ipynb` cell ids normalize to `c1`, `c2`, ... | `REQ-notebook-model`, `REQ-inspect` |
| `JTU003` | Duplicate `.ipynb` cell ids fail before output creation | `REQ-notebook-model`, `REQ-error-atomic` |
| `JTU004` | Percent header parses `minijupy` version and `kernelspec` | `REQ-percent-format`, `REQ-version-marker`, `REQ-inspect` |
| `JTU005` | Percent markers parse cell type, `id`, `tags`, and `name` | `REQ-percent-format`, `REQ-notebook-model`, `REQ-inspect` |
| `JTU006` | Percent writer emits header/markers and strips execution outputs | `REQ-percent-format`, `REQ-to-text`, `REQ-output-preservation` |
| `JTU007` | Config base directory controls mapped paired paths | `REQ-config`, `REQ-paired-paths`, `REQ-inspect` |
| `JTU008` | Default same-directory paired path derivation | `REQ-paired-paths`, `REQ-inspect` |
| `JTU009` | Directory-mapped paired path derivation from the text side | `REQ-config`, `REQ-paired-paths`, `REQ-inspect` |
| `JTU010` | `to-text` conversion strips `.ipynb` execution state | `REQ-to-text`, `REQ-percent-format`, `REQ-output-preservation` |
| `JTU011` | `to-ipynb` conversion emits normalized notebook cells | `REQ-to-ipynb`, `REQ-percent-format`, `REQ-notebook-model` |
| `JTU012` | `pair` sets metadata and creates the percent counterpart | `REQ-pair`, `REQ-version-marker`, `REQ-paired-paths` |
| `JTU013` | `pair` rejects text input without writing | `REQ-pair`, `REQ-error-atomic` |
| `JTU014` | `sync` chooses source by greater version | `REQ-sync`, `REQ-version-marker` |
| `JTU015` | `sync --source` overrides version comparison | `REQ-sync`, `REQ-version-marker` |
| `JTU016` | Local output preservation by matching cell id | `REQ-output-preservation`, `REQ-sync`, `REQ-notebook-model` |
| `JTU017` | Unsupported percent fields are dropped from normalized cells | `REQ-inspect`, `REQ-percent-format`, `REQ-notebook-model` |
| `JTU018` | `status` reports missing counterpart without writing files | `REQ-status`, `REQ-paired-paths`, `REQ-version-marker` |
| `JTU019` | Malformed percent marker fails without notebook output | `REQ-percent-format`, `REQ-error-atomic` |
| `JTU020` | Directory mapping mismatch fails without fallback writes | `REQ-config`, `REQ-paired-paths`, `REQ-error-atomic` |

## System Coverage

| Case | Dimension | Crossed modules | Requirement refs |
| --- | --- | --- | --- |
| `JTS001` | `roundtrip_consistency` | `.ipynb` normalization -> percent writer -> percent parser -> `.ipynb` writer -> inspect | `REQ-notebook-model`, `REQ-percent-format`, `REQ-to-text`, `REQ-to-ipynb`, `REQ-system-invariants` |
| `JTS002` | `sync_conflict_resolution` | status source prediction -> text-authoritative sync -> output preservation -> clean status | `REQ-sync`, `REQ-version-marker`, `REQ-status`, `REQ-output-preservation`, `REQ-system-invariants` |
| `JTS003` | `sync_conflict_resolution` | ipynb-authoritative sync -> percent writer -> status no-write report | `REQ-sync`, `REQ-version-marker`, `REQ-percent-format`, `REQ-status`, `REQ-system-invariants` |
| `JTS004` | `metadata_fanout` | notebook metadata/cell metadata -> percent header/markers -> rebuilt notebook -> inspect/status | `REQ-notebook-model`, `REQ-percent-format`, `REQ-to-text`, `REQ-to-ipynb`, `REQ-inspect`, `REQ-status`, `REQ-system-invariants` |
| `JTS005` | `multi_file_pairing` | config base directory -> mapped pair paths -> pair -> status -> sync | `REQ-config`, `REQ-paired-paths`, `REQ-pair`, `REQ-sync`, `REQ-status`, `REQ-system-invariants` |
| `JTS006` | `status_report_consistency` | version comparison -> status `would_write` -> sync writes -> clean status | `REQ-status`, `REQ-sync`, `REQ-version-marker`, `REQ-system-invariants` |
| `JTS007` | `output_preservation` | text authoritative model -> cell id matching -> reordered notebook output preservation | `REQ-sync`, `REQ-output-preservation`, `REQ-notebook-model`, `REQ-system-invariants` |
| `JTS008` | `status_report_consistency` | equal versions -> status source `none` -> sync no-op | `REQ-sync`, `REQ-status`, `REQ-version-marker`, `REQ-system-invariants` |
| `JTS009` | `sync_conflict_resolution` | `--source` override -> percent rewrite -> clean status | `REQ-sync`, `REQ-version-marker`, `REQ-status`, `REQ-system-invariants` |
| `JTS010` | `multi_file_pairing` | missing counterpart status -> pair creation -> status/sync no-op | `REQ-pair`, `REQ-status`, `REQ-sync`, `REQ-paired-paths`, `REQ-system-invariants` |
| `JTS011` | `output_preservation` | missing ids -> public id assignment -> positional output preservation -> inspect | `REQ-notebook-model`, `REQ-percent-format`, `REQ-sync`, `REQ-output-preservation`, `REQ-system-invariants` |
| `JTS012` | `metadata_fanout` | unsupported metadata filtering -> inspect -> text conversion -> rebuilt notebook | `REQ-notebook-model`, `REQ-percent-format`, `REQ-inspect`, `REQ-to-text`, `REQ-to-ipynb`, `REQ-system-invariants` |
| `JTS013` | `error_atomicity` | malformed `.ipynb` validation -> sync failure -> paired files unchanged | `REQ-error-atomic`, `REQ-sync`, `REQ-system-invariants` |
| `JTS014` | `error_atomicity` | config/path validation -> sync failure -> existing files unchanged | `REQ-config`, `REQ-paired-paths`, `REQ-error-atomic`, `REQ-system-invariants` |

## Fairness Notes

- Future `rubric.json` cases must be naturally inferable from `prd.md`.
- Tests may observe only public CLI stdout, stderr, exit code, and the `.ipynb`,
  `.py`, and config files defined by the PRD.
- Do not inspect Jupytext internals, private module structures, or any specific
  implementation architecture.
- Do not use real filesystem modification times; all freshness behavior must
  come from public version markers or `--source`.
- Do not require notebook execution, kernels, Jupyter server behavior,
  ContentsManager behavior, autosave, or external commands.
- Do not require full nbformat parity beyond the public notebook model in the
  PRD.
- Do not add Markdown, MyST, Quarto, Rmd, pandoc, marimo, or non-Python script
  formats to tests unless the PRD is explicitly revised first.
- Do not require metadata filter grammar or unsupported metadata preservation.
- Do not test private implementation details, exact algorithms, hidden helper
  APIs, or byte formatting beyond explicit PRD file-format rules.
- Candidate implementations may score 100/100; that is no-gap evidence, not a
  reason to introduce hidden requirements.
