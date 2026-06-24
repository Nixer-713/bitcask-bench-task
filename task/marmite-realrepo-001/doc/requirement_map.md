# Mini Marmite Requirement Map

Public packet: `prd.md`

Rubric: not drafted yet

## Public Requirements

| ID | Capability | Public basis |
| --- | --- | --- |
| `REQ-cli-build-inspect` | Provide `build` and `inspect` commands with JSON stdout and non-zero failures | Invocation |
| `REQ-input-layout` | Discover Markdown content under `INPUT/content/` or `INPUT`, ignore fragments and non-Markdown files | Input Layout |
| `REQ-config` | Parse supported config keys and apply defaults/toggles | Config Format |
| `REQ-frontmatter` | Parse supported frontmatter keys and reject invalid supported values | Frontmatter Format |
| `REQ-title-slug` | Derive deterministic title and slug from frontmatter, heading, or filename | Content Model, Title, Slug |
| `REQ-date-kind` | Derive dates from frontmatter/filename and classify posts vs pages | Date, Posts, And Pages |
| `REQ-tags` | Extract tags, slugify tag names, and group non-draft posts by tag | Tags, Tag Listings |
| `REQ-streams` | Extract streams from frontmatter/filename and group non-draft posts by stream | Streams, Stream Listings |
| `REQ-drafts` | Expose drafts in `inspect` while excluding them from public build outputs | Drafts And Exclusion |
| `REQ-markdown-html` | Render the defined Markdown subset with escaping and local-link rewriting | Markdown Rendering |
| `REQ-wikilinks-backlinks` | Resolve known wikilinks, preserve unknown wikilinks, and generate backlinks | Markdown Rendering, Content Pages |
| `REQ-content-pages` | Generate deterministic post/page HTML files with title, body, and backlinks | Generated Files, Content Pages |
| `REQ-list-pages` | Generate index, pages, tag, and stream listing pages with pagination | Index And Pages Listings, Tag Listings, Stream Listings |
| `REQ-json-feeds` | Generate JSON feeds when enabled and omit feeds when disabled | JSON Feeds |
| `REQ-search-index` | Generate search index when enabled and omit it when disabled | Search Index |
| `REQ-url-manifest` | Generate `urls.json` with precise groups and summary counts | URL Manifest |
| `REQ-inspect` | Emit parsed posts, pages, tags, streams, and drafts without writing site files | Inspect Output |
| `REQ-error-atomic` | Failed commands write no output files and report useful errors | Error Behavior |
| `REQ-system-invariants` | Keep parsed state, generated files, feeds, search, backlinks, and manifest mutually consistent | Goal, Global Invariants |

## Source Grounding Notes

| Requirement | Source-derived basis | Adaptation note |
| --- | --- | --- |
| `REQ-cli-build-inspect` | Marmite CLI builds input to output; tests cover help, minimal generation, and `--show-urls` | `inspect` is a mini-task adaptation to expose parser state without hidden tests. |
| `REQ-input-layout` | `README.md` and `src/site.rs` use input/content paths and skip fragment-like files | Fragment behavior is simplified to ignore underscore files. |
| `REQ-config` | `src/config.rs` defines many config fields | Mini task keeps only site name, base URL, pagination, feeds, and search toggles. |
| `REQ-frontmatter` | `src/content.rs` and `src/parser.rs` parse frontmatter | Mini task defines a small YAML-like subset for deterministic scoring. |
| `REQ-title-slug` | `get_title` and `get_slug` derive title/slug from frontmatter, heading, and filename | Slugification is explicitly simplified and public. |
| `REQ-date-kind` | `README.md` states date differentiates posts/pages; `get_date` reads frontmatter/filename | Date formats are narrowed to fixed literal forms. |
| `REQ-tags` | Marmite groups posts by tags and generates tag pages/feeds | Authors/series/archives are excluded from first PRD to keep scope focused. |
| `REQ-streams` | Marmite supports streams from frontmatter and filename patterns; tests cover both | Keep streams with tags to create parallel taxonomy pressure. |
| `REQ-drafts` | Source filters draft stream content from feeds/search/group listings | Mini task uses a clearer public exclusion rule for all public build outputs. |
| `REQ-json-feeds` | `src/feed.rs` supports JSON feeds in addition to RSS | JSON is retained; RSS/XML is excluded for scoring simplicity. |
| `REQ-url-manifest` | `src/site.rs` collects generated URLs and can emit `urls.json`; tests cover `--show-urls` | Manifest grouping and summary counts are made exact for rubric stability. |
| `REQ-wikilinks-backlinks` | `README.md`, `src/parser.rs`, and `src/site.rs` support wikilinks/backlinks | Mini task limits link syntax and makes backlink section observable. |

## Planned Unit Coverage

No rubric cases are drafted yet. The likely unit modules are:

- CLI argument handling and config defaults.
- Input layout discovery and fragment ignoring.
- Frontmatter parsing for supported keys.
- Title and slug derivation.
- Date extraction and post/page classification.
- Tag extraction and tag slugification.
- Stream extraction from frontmatter and filename patterns.
- Draft recognition.
- Markdown subset rendering and local-link rewriting.
- Wikilink resolution.
- JSON feed generation.
- Search index generation.
- URL manifest grouping and summary counting.
- Error handling for invalid config, invalid frontmatter, duplicate slugs, and missing input.

## Planned System Coverage

No rubric cases are drafted yet. System cases should cross heterogeneous modules
and derived outputs:

| system_dimension | Crossed modules |
| --- | --- |
| `content_graph_fanout` | parse content -> render pages -> listings -> feeds -> search -> manifest |
| `classification_propagation` | date/kind classification -> post/page pages -> feeds/search/manifest |
| `taxonomy_cross_views` | tags + streams -> taxonomy pages -> taxonomy feeds -> manifest |
| `pagination_manifest_consistency` | pagination config -> listing files -> manifest groups/counts |
| `link_graph_consistency` | slug derivation -> wikilinks -> backlinks -> rendered HTML |
| `exclusion_propagation` | draft detection -> absence from public pages/listings/feeds/search/manifest |
| `config_effects` | config toggles/base URL -> feeds/search URLs -> manifest consistency |
| `error_atomicity` | invalid input/config -> no partial output files |

## Fairness Notes

- Future rubric cases must be inferable from `prd.md`, not from private Marmite
  internals.
- Tests should observe only public CLI output, exit code, stderr, and files
  explicitly defined by the PRD.
- The rubric must not require exact Marmite templates, Rust modules, Tera
  behavior, full CommonMark rendering, RSS/XML, image processing, server/watch
  behavior, or file modification time semantics.
- `urls.json` should be used as a global invariant oracle, but it must follow
  the PRD's explicit group and summary definitions.
- Draft behavior is a documented mini-task adaptation; tests may rely on it only
  because the PRD states it publicly.
