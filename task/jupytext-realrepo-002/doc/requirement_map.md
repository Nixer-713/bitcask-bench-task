# Jupytext 002 Requirement Map

## Public Requirements

| Requirement ID | Public behavior |
| --- | --- |
| `REQ-cli` | `minijupy.py` exposes `inspect`, `to-text`, `to-ipynb`, `pair`, `status`, `check`, and `sync`; successful commands print JSON and failures are nonzero with stderr. |
| `REQ-files-config` | Supports `.ipynb`, `py:percent`, `minijupy.toml`, and `.minijupy-state.json`; config can define same-directory or `notebook_dir` / `script_dir` mapped pairs. |
| `REQ-notebook-model` | Parses and normalizes the public notebook model: nbformat, metadata, cell order, ids, cell types, source, tags/name, execution counts, and outputs. |
| `REQ-percent-format` | Parses and writes the PRD-defined percent header, `# %%` markers, cell type markers, and marker JSON for id/tags/name. |
| `REQ-pair-paths` | Derives paired `.ipynb` / `.py` paths consistently for same-directory and directory-mapped configs; rejects path mismatch or duplicate mappings. |
| `REQ-state-file` | Creates and updates `.minijupy-state.json` with pair paths, last synced versions, and stable equality tokens after successful pair/sync. |
| `REQ-version` | Reads public versions from `.ipynb` metadata and percent headers; missing version is `1`; invalid versions fail. |
| `REQ-convert` | `to-text` strips outputs/execution counts while preserving representable public fields; `to-ipynb` creates normalized notebooks with no outputs. |
| `REQ-pair` | `pair` creates or updates counterpart files, writes pairing metadata, preserves existing `.ipynb` outputs, and initializes state. |
| `REQ-inspect` | `inspect` is read-only and prints the normalized public notebook model for one `.ipynb` or `py:percent` file. |
| `REQ-status` | `status` is read-only and reports paths, existence, versions, source, conflict, missing files, planned writes, differences, errors, and summary. |
| `REQ-check` | `check` is read-only and reports roundtrip consistency and public difference categories. |
| `REQ-sync` | `sync` selects source by explicit `--source` or state/version comparison, updates counterpart files, preserves outputs when text is source, and updates state. |
| `REQ-conflict` | Conflict means both sides changed beyond last synced versions; status/check report it; sync without source fails; source override resolves. |
| `REQ-missing` | Missing counterpart is reported and can be created by pair/sync; text-created notebooks have no outputs; ipynb-created text strips outputs. |
| `REQ-output-preservation` | When text is source, outputs are preserved by id, then same type plus source hash, then position fallback, otherwise dropped. |
| `REQ-sync-all` | `sync --all` discovers project pairs from config, validates every pair before writing, and is all-or-nothing. |
| `REQ-error-atomic` | Failed commands leave `.ipynb`, `.py`, config, state, and new output files unchanged; read-only commands do not write. |
| `REQ-invariants` | Normalized model, path rules, state, status/check, sync, output preservation, and atomicity remain mutually consistent. |
| `REQ-non-goals` | Excludes real mtimes, Jupytext internals, full nbformat, extra formats, Jupyter server, execution, Git/pre-commit, rich media, and watchers. |

## Source Grounding Notes

| Requirement | Source-derived basis | Mini-task adaptation |
| --- | --- | --- |
| `REQ-cli` | Jupytext CLI exposes conversion, `--sync`, `--paired-paths`, `--test`, and `--test-strict` in `src/jupytext/cli.py`. | Commands are renamed into smaller verbs and JSON stdout is fixed. |
| `REQ-files-config` | Jupytext docs and config support paired formats and subfolder mappings. | Config grammar is reduced to `formats`, `notebook_dir`, and `script_dir`. |
| `REQ-notebook-model` | Jupytext reads/writes notebooks and preserves cells/metadata/outputs. | Public model is reduced to fields needed for paired sync. |
| `REQ-percent-format` | Jupytext `py:percent` docs and reader/writer support cell markers and metadata. | Only Python percent format is required. |
| `REQ-pair-paths` | `paired_paths.py` derives base/full paired paths and rejects mismatches. | Only same-directory and one directory mapping are required. |
| `REQ-state-file`, `REQ-version`, `REQ-conflict` | Jupytext uses mtimes/newest source and stale-source checks. | Real mtimes are replaced by public versions and `.minijupy-state.json`. |
| `REQ-output-preservation` | `combine.py` merges text inputs with `.ipynb` outputs. | Matching order is explicitly public and deterministic. |
| `REQ-status`, `REQ-check` | `--paired-paths`, `--test`, `--test-strict`, and stale-source checks are public. | Stable JSON report replaces logs and timing behavior. |
| `REQ-sync-all` | Project config and pre-commit flows imply multi-file sync/check workflows. | All-or-nothing project sync is a public deterministic strengthening. |
| `REQ-error-atomic` | Jupytext uses temp files and synchronous modification checks; tests assert no partial counterpart creation. | Atomicity is made explicit for all mini-task write commands. |

## Unit Coverage

| Case ID | Focus | Requirement refs |
| --- | --- | --- |
| `JTU001` | Parse and normalize `.ipynb` | `REQ-notebook-model`, `REQ-inspect` |
| `JTU002` | Parse `py:percent` header and markers | `REQ-percent-format`, `REQ-version`, `REQ-notebook-model`, `REQ-inspect` |
| `JTU003` | Write percent and strip outputs | `REQ-convert`, `REQ-percent-format`, `REQ-output-preservation` |
| `JTU004` | Same-directory paired path derivation | `REQ-pair-paths`, `REQ-status` |
| `JTU005` | Directory-mapped paired path derivation | `REQ-files-config`, `REQ-pair-paths`, `REQ-status` |
| `JTU006` | Create `.minijupy-state.json` | `REQ-pair`, `REQ-state-file`, `REQ-version` |
| `JTU007` | Detect stale text version | `REQ-status`, `REQ-version`, `REQ-state-file` |
| `JTU008` | Detect conflict | `REQ-conflict`, `REQ-status`, `REQ-state-file` |
| `JTU009` | Preserve outputs by id | `REQ-sync`, `REQ-output-preservation` |
| `JTU010` | Preserve outputs by fallback | `REQ-sync`, `REQ-output-preservation` |
| `JTU011` | Single-pair status report | `REQ-status`, `REQ-invariants` |
| `JTU012` | Single-pair check report | `REQ-check`, `REQ-convert`, `REQ-invariants` |
| `JTU013` | Malformed percent atomicity | `REQ-percent-format`, `REQ-error-atomic` |
| `JTU014` | Malformed notebook atomicity | `REQ-notebook-model`, `REQ-error-atomic` |

## System Coverage

| Case ID | System dimension | Crossed modules | Requirement refs |
| --- | --- | --- | --- |
| `JTS001` | `pair_status_sync_clean_loop` | pair -> state -> status -> sync -> status | `REQ-pair`, `REQ-state-file`, `REQ-status`, `REQ-sync`, `REQ-invariants` |
| `JTS002` | `text_edit_sync_updates_notebook` | state/version -> status source -> sync -> notebook update -> state | `REQ-version`, `REQ-status`, `REQ-sync`, `REQ-state-file` |
| `JTS003` | `conflict_resolution_workflow` | both-side edits -> conflict report -> failed sync -> source override | `REQ-conflict`, `REQ-sync`, `REQ-error-atomic`, `REQ-state-file` |
| `JTS004` | `sync_all_mixed_states` | config discovery -> clean/stale/missing/conflict pair statuses | `REQ-files-config`, `REQ-pair-paths`, `REQ-sync-all`, `REQ-missing`, `REQ-conflict` |
| `JTS005` | `sync_all_malformed_atomicity` | multi-pair validation -> malformed input -> no project writes | `REQ-sync-all`, `REQ-error-atomic`, `REQ-invariants` |
| `JTS006` | `output_preservation_after_cell_edits` | text edit/reorder/insert/delete -> sync -> output map | `REQ-sync`, `REQ-output-preservation`, `REQ-notebook-model` |
| `JTS007` | `check_detects_state_file_mismatch` | state -> files -> check differences/errors | `REQ-check`, `REQ-state-file`, `REQ-invariants` |
| `JTS008` | `directory_pair_mapping_workflow` | config mapping -> pair -> status -> sync across directories | `REQ-files-config`, `REQ-pair-paths`, `REQ-pair`, `REQ-sync` |
| `JTS009` | `state_drives_status_after_manual_changes` | manual version changes -> state comparison -> status planned writes | `REQ-state-file`, `REQ-version`, `REQ-status` |
| `JTS010` | `source_override_updates_files_and_state` | conflict/source override -> output preservation -> both files/state agree | `REQ-conflict`, `REQ-sync`, `REQ-output-preservation`, `REQ-state-file` |

## Fairness Notes

- Rubric cases must be inferable from `prd.md`.
- Tests should observe only stdout JSON, stderr, exit code, `.ipynb`, `.py`,
  config, and `.minijupy-state.json` files.
- Do not test real mtimes, private Jupytext internals, exact Jupytext
  serialization, full nbformat parity, notebook execution, server behavior,
  Git/pre-commit internals, or unsupported formats.
- Unit cases test local capabilities. System cases cross state, paths, reports,
  sync decisions, output preservation, and atomicity.
