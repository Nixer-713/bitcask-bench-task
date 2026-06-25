# Next Source Task Selection Memo

Status baseline:

- `bitcask-realrepo-001`: candidate / no-gap-observed.
- `xitkit-realrepo-001`: source-grounded candidate / no-gap-observed.
- `marmite-realrepo-001`: hardened reference-satisfiable / no-positive-gap-observed.

This memo evaluates next source repositories only. It does not start a new task,
write PRD/rubric files, or add reference/scorer/candidate/validation assets.

## Selection Lens

Prefer source projects where one public input state drives several heterogeneous
outputs or effects: parsed records, config effects, generated files, indexes,
reports, graph/link views, validation results, state transitions, and recovery
behavior. Avoid sources that collapse into a single map/list plus metadata or
require exact private internals.

## Candidate 1: `mwouts/jupytext`

- Repository: https://github.com/mwouts/jupytext
- Public signal: Jupytext exposes command-line pairing, conversion, and sync
  between `.ipynb` notebooks and text formats such as Markdown or Python percent
  scripts. The README describes CLI actions such as `--set-formats`,
  `--sync`, `--to`, and piping notebooks.
- Why plausible: one notebook state can drive multiple public representations:
  `.ipynb`, paired text file, metadata, cell order, cell type, tags, execution
  counts, outputs, sync status, and conversion reports.
- Public feature modules:
  - notebook JSON parsing
  - percent-script or Markdown cell parsing
  - paired format config
  - conversion/writeback
  - sync/newest-source decision
  - metadata and cell tag preservation
  - status/check reporting
  - error atomicity for malformed notebooks or conflicting pairs
- Likely unit cases:
  - parse minimal `.ipynb`
  - parse percent-script cells
  - derive paired paths from config
  - preserve cell type, source, metadata, tags
  - convert notebook to text
  - convert text to notebook
  - report malformed JSON/frontmatter/cell markers
- Likely system dimensions:
  - roundtrip_consistency: `.ipynb -> text -> ipynb` preserves public notebook
    model
  - sync_conflict_resolution: newer paired representation drives both outputs
    and status report
  - metadata_fanout: notebook metadata/cell tags affect text headers, inspect
    output, and rebuilt notebook
  - multi_file_pairing: project config maps several notebooks to paired files
  - error_atomicity: malformed paired file leaves both representations unchanged
- Why it may produce high-unit/lower-system behavior: candidates can pass local
  parsers or one-way conversion but fail when bidirectional sync, metadata,
  paired-path derivation, and status reports must all agree from the same source
  state.
- Risks / reasons to reject:
  - full Jupyter/Jupytext parity is too broad.
  - exact percent/Markdown format details can become hidden if not explicitly
    scoped.
  - file timestamp semantics should be simplified or replaced with explicit
    public version markers for deterministic scoring.
- Estimated mini-task scope: medium. A self-contained `minijupy.py` can use
  Python stdlib JSON and a small public subset of percent-script/Markdown cell
  syntax.

## Candidate 2: `pre-commit/pre-commit`

- Repository: https://github.com/pre-commit/pre-commit
- Public signal: the project is a framework for running configured hooks; the
  docs describe `.pre-commit-config.yaml`, hook repositories, file filtering,
  stages, and running hooks.
- Why plausible: one config plus one working tree can drive selected hooks,
  skipped hooks, transformed files, status codes, human/JSON reports, and
  failure behavior.
- Public feature modules:
  - config parsing
  - hook selection by stage/id
  - file include/exclude filters
  - simulated hook execution
  - fail-fast and aggregate reporting
  - autofix/writeback behavior
  - error atomicity for invalid config
- Likely unit cases:
  - parse hook config
  - select hooks by stage
  - match files by regex/type
  - run a single built-in hook
  - report pass/fail/skip
  - apply simple autofix
- Likely system dimensions:
  - config_file_filter_fanout: config determines hook set, files, reports, and
    exit status
  - autofix_report_consistency: file writeback and report status agree
  - fail_fast_boundary: first failure changes later hook execution and summary
  - stage_override_consistency: stage selection affects hooks and file reports
  - error_atomicity: invalid config writes no hook outputs or modified files
- Why it may produce high-unit/lower-system behavior: local hook parsing is
  straightforward, but combining config inheritance, filters, stages, autofix,
  fail-fast, and reports creates system-level consistency pressure.
- Risks / reasons to reject:
  - real hook execution and Git staging semantics are too environment-dependent.
  - mini-task must use simulated built-in hooks, not external commands.
  - YAML support must be a small public subset to avoid dependency burden.
- Estimated mini-task scope: medium-high. Strong candidate if scoped to a
  deterministic hook runner with built-in hook actions.

## Candidate 3: `simonw/sqlite-utils`

- Repository: https://github.com/simonw/sqlite-utils
- Public signal: sqlite-utils is a Python CLI/library for creating and
  manipulating SQLite databases from files; its CLI reference lists commands
  such as `insert`, `query`, `search`, `transform`, `extract`, `schema`,
  `indexes`, and `enable-fts`.
- Why plausible: one dataset can drive SQLite tables, inferred schema, indexes,
  full-text search tables, query output, exports, schema reports, and analysis
  summaries.
- Public feature modules:
  - JSON/CSV import
  - schema inference
  - primary keys/upsert
  - query/export formats
  - index and FTS metadata
  - transform/extract operations
  - schema/analyze reports
- Likely unit cases:
  - import JSON rows
  - infer simple column types
  - query table rows
  - create index
  - enable simple text search
  - export JSON/CSV
  - reject invalid schema/data
- Likely system dimensions:
  - import_schema_query_consistency: rows, schema, query, and export agree
  - fts_index_search_consistency: imported text drives search and metadata
  - transform_report_consistency: transformed table updates schema/query/export
  - error_atomicity: invalid transform leaves DB unchanged
- Why it may produce high-unit/lower-system behavior: system cases can combine
  inferred schema, query results, index metadata, and export/report views.
- Risks / reasons to reject:
  - many behaviors collapse to SQLite's built-in correctness if candidates use
    `sqlite3` directly.
  - exact sqlite-utils CLI parity is large.
  - less graph-like than Jupytext/pre-commit.
- Estimated mini-task scope: medium. Feasible with stdlib `sqlite3`, but may be
  less discriminative than the top candidates.

## Candidate 4: `cookiecutter/cookiecutter`

- Repository: https://github.com/cookiecutter/cookiecutter
- Public signal: Cookiecutter is a command-line project generator from template
  directories and `cookiecutter.json` context.
- Why plausible: one template plus context can drive generated paths, rendered
  file content, skip/overwrite behavior, replay/context files, and validation
  reports.
- Public feature modules:
  - context parsing and defaults
  - variable substitution in paths and files
  - conditional file inclusion in a mini subset
  - replay/no-input behavior
  - overwrite/conflict handling
  - generated manifest/report
- Likely unit cases:
  - parse `cookiecutter.json`
  - substitute variables in filenames
  - substitute variables in file bodies
  - apply default values
  - reject missing required context
  - detect output conflicts
- Likely system dimensions:
  - context_fanout: one answer set drives paths, file bodies, manifest, and
    replay state
  - conflict_atomicity: conflict prevents partial generation
  - replay_consistency: replayed context regenerates the same public files
  - conditional_generation: config affects generated tree and manifest
- Why it may produce high-unit/lower-system behavior: path rendering, content
  rendering, conflict handling, and replay consistency often fail when treated
  as isolated string substitutions.
- Risks / reasons to reject:
  - full Jinja2 template behavior is too broad and dependency-heavy.
  - template syntax must be a small public subset.
  - could become hidden if exact escaping/templating details are not specified.
- Estimated mini-task scope: medium. Good backup if Jupytext is rejected.

## Candidate 5: `rust-lang/mdBook`

- Repository: https://github.com/rust-lang/mdBook
- Public signal: mdBook builds books from `book.toml`, `SUMMARY.md`, and chapter
  Markdown; documentation states that `SUMMARY.md` determines included chapters,
  order, hierarchy, and source paths.
- Why plausible: one book source can drive chapter HTML, navigation order,
  rewritten links, search index, missing-file diagnostics, generated summary
  outputs, and cleanup reports.
- Public feature modules:
  - `SUMMARY.md` parser
  - chapter discovery/order/hierarchy
  - Markdown subset rendering
  - link rewriting
  - config-driven search/index toggles
  - generated file manifest
  - error handling for missing duplicate chapters
- Likely unit cases:
  - parse simple summary tree
  - render chapter page
  - rewrite local chapter links
  - generate search index item
  - apply config toggle
  - report missing chapter file
- Likely system dimensions:
  - summary_graph_fanout: summary drives navigation, pages, search, and manifest
  - link_rewrite_consistency: source paths, output paths, and rendered links
    agree
  - config_search_consistency: config affects search file and manifest
  - missing_file_atomicity: bad summary fails without partial output
- Why it may produce high-unit/lower-system behavior: candidates can parse
  chapters or render Markdown locally but fail when hierarchy, path rewriting,
  search, and manifest must stay coherent.
- Risks / reasons to reject:
  - overlaps heavily with Marmite's static-site-generator shape.
  - strong agents already did well on hardened Marmite.
  - exact mdBook templates and full Markdown are out of scope.
- Estimated mini-task scope: medium. Plausible, but less differentiated from
  Marmite than Jupytext or pre-commit.

## Recommendation

Recommend starting with `mwouts/jupytext`.

Why it is stronger than the three existing tasks:

- Stronger than Bitcask: it is not a single live-state model. Correctness
  depends on bidirectional representations, metadata preservation, path pairing,
  and sync/status consistency.
- Stronger than xitkit: it has more heterogeneous derived views than task lists:
  notebook JSON, text notebook syntax, paired-file config, sync result, status
  report, and error recovery.
- Stronger than Marmite: it is less likely to collapse into one static
  generation pass. A mini Jupytext task can require roundtrip and sync behavior
  where the same notebook model must remain consistent across multiple writable
  representations.

Suggested next step:

```text
Start source-grounding for jupytext-realrepo-001.
Do not draft PRD/rubric until README, docs, CLI behavior, paired format rules,
sync semantics, metadata handling, and tests have been inspected.
```

If Jupytext is rejected after source-grounding, use `pre-commit/pre-commit` as
the next candidate because its config/filter/hook/report/autofix interactions
also create clear system-level composition pressure.

## Sources Used

- Jupytext README / CLI overview: https://github.com/mwouts/jupytext
- Jupytext changelog / CLI sync references:
  https://jupytext.readthedocs.io/en/latest/changelog.html
- pre-commit documentation: https://pre-commit.com/
- sqlite-utils CLI reference:
  https://sqlite-utils.datasette.io/en/stable/cli-reference.html
- sqlite-utils repository: https://github.com/simonw/sqlite-utils
- Cookiecutter repository: https://github.com/cookiecutter/cookiecutter
- mdBook SUMMARY documentation:
  https://rust-lang.github.io/mdBook/format/summary.html
- mdBook repository: https://github.com/rust-lang/mdBook
