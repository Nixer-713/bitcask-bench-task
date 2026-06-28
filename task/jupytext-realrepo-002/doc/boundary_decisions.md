# Jupytext 002 Boundary Decisions

Status: boundary locked for PRD drafting; no PRD or rubric is defined here.

Canonical source: `mwouts/jupytext` at
`40f3c5fd625f6b7c851bf3c632cd2f7f7e35c4f4`.

This note fixes the deterministic mini-task boundaries for
`jupytext-realrepo-002`. The goal is to preserve Jupytext's public paired
notebook workflow while avoiding non-deterministic mtimes, Jupyter runtime
state, and private implementation details.

## User-Provided Facts

- The benchmark should be redesigned around Jupytext paired-notebook behavior,
  not around isolated serializer functions.
- Source behaviors of interest are paired notebooks, `--set-formats`, `--sync`,
  paired paths, newest-source decisions, output preservation, conflicts,
  status/test behavior, and failure atomicity.
- A boundary note must be written before PRD drafting.

## Reasonable Inferences

- `jupytext-realrepo-001` likely scored too high because the task collapsed into
  one normalized notebook model plus serializers.
- `jupytext-realrepo-002` should turn paired notebook state into the central
  benchmark artifact: paired files, config, state, status/check reports, sync
  decisions, preserved outputs, and atomic writes.

## Boundary Decisions

| Boundary | Decision | Source-derived basis | Mini-task adaptation |
| --- | --- | --- | --- |
| Public state file | Introduce `.minijupy-state.json`. | Jupytext uses paired files plus mtimes to choose freshest input and protect against stale overwrites (`src/jupytext/pairs.py`, lines 15-55; `tests/functional/cli/test_source_is_newer.py`, lines 12-70). | Replace real mtimes with a public deterministic state file recording last-synced versions/hashes per pair. |
| Conflict definition | A pair is in conflict when both the `.ipynb` side and text side have public versions greater than the last synced versions in `.minijupy-state.json`. | Jupytext docs describe simultaneous notebook/text edits and require user choice/reload (`website/src/content/docs/using/paired-notebooks.md`, lines 29-41; `website/src/content/docs/reference/faq.md`, lines 90-98). | Define conflict with public version numbers instead of concurrent editor timing or filesystem mtimes. |
| `sync --all` atomicity | `sync --all` is all-or-nothing. If any pair in scope fails validation, no pair files or state file are written. | Jupytext protects individual writes with temp files, timestamp rechecks, cleanup, and `os.replace` (`src/jupytext/cli.py`, lines 814-919). Synchronous-change tests assert failed operations do not create partial counterparts (`tests/functional/cli/test_synchronous_changes.py`, lines 15-111). | Strengthen to a public project-level atomicity rule so system tests can check cross-pair consistency deterministically. |
| Output preservation matching | Preserve outputs by: cell id match -> same cell type plus same source hash -> position fallback -> otherwise drop outputs. | `combine_inputs_with_outputs` restores outputs/metadata from `.ipynb`; `map_outputs_to_inputs` uses multi-rule matching including type/source and position fallback (`src/jupytext/combine.py`, lines 36-177). | Expose a smaller deterministic matching order. Dropping unmatched outputs is public and avoids hidden heuristic dependence. |
| `status` / `check` output | Use a fixed JSON schema for status/check commands. | Jupytext exposes `--test`, `--test-strict`, `--paired-paths`, source-newer checks, and sync logs (`website/src/content/docs/using/cli.md`, lines 86-99; `src/jupytext/cli.py`, lines 173-177 and 214-223). | Replace text logs and mtime behavior with machine-checkable JSON fields for pair paths, source choice, conflict, planned writes, roundtrip state, and errors. |

## State File Contract For PRD

The PRD should define `.minijupy-state.json` as a public artifact created and
updated by successful `pair`, `sync`, and `sync --all` commands.

Recommended minimum shape:

```json
{
  "pairs": {
    "notebooks/demo.ipynb": {
      "ipynb": "notebooks/demo.ipynb",
      "text": "scripts/demo.py",
      "last_synced": {
        "ipynb_version": 2,
        "text_version": 2,
        "ipynb_hash": "public-hash",
        "text_hash": "public-hash"
      }
    }
  }
}
```

The exact hash algorithm can be PRD-defined as normalized JSON/source string
hashing, or the PRD can require only stable equality tokens if tests do not need
specific hash values.

## Conflict And Sync Semantics For PRD

- `status` reports conflict when both sides changed since the last synced state.
- `sync` without explicit source fails on conflict and writes nothing.
- `sync --source ipynb` uses `.ipynb` inputs plus `.ipynb` outputs as source of
  truth and updates the text counterpart and state.
- `sync --source text` uses text inputs as source of truth, preserves matching
  `.ipynb` outputs, updates `.ipynb`, text if needed, and state.
- Equal versions / equal hashes produce no planned writes.
- Missing counterpart is not conflict by itself; it is a planned create/update.

## `sync --all` Semantics For PRD

- Scope is all pairs reachable from the provided config root.
- The command first validates every pair and computes a complete write plan.
- If any pair has malformed input, path mismatch, duplicate mapping, invalid
  config, or unresolved conflict, the command exits nonzero and writes nothing.
- If validation succeeds, all planned pair files and `.minijupy-state.json` are
  updated together.
- `status --all` must predict the same pair set and planned writes as
  `sync --all`.

## Output Preservation Semantics For PRD

When text is the selected source and an `.ipynb` counterpart exists:

1. Match an output cell to an input cell with the same public cell id.
2. If no id match exists, match the first unused output cell with the same cell
   type and the same normalized source hash.
3. If no source-hash match exists, match by same position when cell types match.
4. If none match, preserve no outputs or execution count for that input cell.

This is source-grounded in Jupytext's output-combination behavior but avoids
requiring candidates to reproduce Jupytext's private matching heuristics.

## Status / Check JSON Schema For PRD

The PRD should define a stable JSON object. Suggested top-level keys:

```json
{
  "ok": true,
  "mode": "status",
  "root": ".",
  "pairs": [
    {
      "ipynb": "notebooks/demo.ipynb",
      "text": "scripts/demo.py",
      "exists": {"ipynb": true, "text": true},
      "versions": {"ipynb": 2, "text": 3, "last_ipynb": 2, "last_text": 2},
      "source": "text",
      "conflict": false,
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

`check` can use the same schema with `mode: "check"` and must write no files.

## Explicit Exclusions

- No real filesystem mtime as the source-of-truth.
- No Jupyter server, ContentsManager, browser reload prompt, or collaboration
  behavior.
- No notebook execution, kernel handling, pipes, nbconvert, papermill, or black.
- No exact Jupytext private serialization or internal matching algorithm.
- No full nbformat parity or full metadata filter grammar.
- No Markdown/MyST/Quarto/Rmd/light/nomarker/sphinx/spin/marimo format support.
- No Git/pre-commit index behavior.

## Open Questions Before PRD

1. Should `.minijupy-state.json` be required at repo root only, or beside the
   config file when `--config` is provided?
2. Should the PRD expose exact hash values, or only require stable equality
   tokens in status/check output?
3. Should `pair` initialize both side versions to `1`, or copy existing public
   versions from files when present?

These are PRD-detail questions. They do not reopen the five core boundaries
above.
