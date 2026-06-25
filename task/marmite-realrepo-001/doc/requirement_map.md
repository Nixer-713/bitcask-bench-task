# Mini Marmite Requirement Map

Public packet: `prd.md`

Rubric: `rubric.json`

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

## Unit Coverage

| Case ID | Unit focus | Requirement refs |
| --- | --- | --- |
| `MMU001` | Input discovery ignores fragments/non-Markdown and exposes inspect records | `REQ-cli-build-inspect`, `REQ-input-layout`, `REQ-inspect` |
| `MMU002` | Config defaults and feed/search toggles affect manifest groups | `REQ-config`, `REQ-json-feeds`, `REQ-search-index`, `REQ-url-manifest` |
| `MMU003` | Supported frontmatter fields parse into inspect output | `REQ-frontmatter`, `REQ-inspect` |
| `MMU004` | Title and slug derivation use heading and filename fallbacks | `REQ-title-slug`, `REQ-inspect` |
| `MMU005` | Date extraction drives post/page classification | `REQ-date-kind`, `REQ-inspect` |
| `MMU006` | Tags parse from list/string forms and slugify into tag groups | `REQ-tags`, `REQ-inspect` |
| `MMU007` | Streams parse from frontmatter and filename forms | `REQ-streams`, `REQ-title-slug`, `REQ-inspect` |
| `MMU008` | Drafts remain visible to inspect but leave public post/stream sets | `REQ-drafts`, `REQ-inspect` |
| `MMU009` | Markdown subset renders headings, paragraphs, escaping, and local links | `REQ-markdown-html`, `REQ-content-pages` |
| `MMU010` | Wikilinks resolve known targets and preserve unknown labels visibly | `REQ-wikilinks-backlinks`, `REQ-content-pages` |
| `MMU011` | Content pages include observable backlink sections | `REQ-wikilinks-backlinks`, `REQ-content-pages` |
| `MMU012` | Index and pages listings are generated with manifest entries | `REQ-list-pages`, `REQ-content-pages` |
| `MMU013` | JSON feed includes non-draft posts and base-URL-aware URLs | `REQ-json-feeds`, `REQ-config` |
| `MMU014` | Search index includes non-draft post/page metadata and rendered text | `REQ-search-index`, `REQ-markdown-html` |
| `MMU015` | URL manifest grouping and summary counts follow PRD grouping rules | `REQ-url-manifest` |
| `MMU016` | Invalid config fails without writing public output files | `REQ-cli-build-inspect`, `REQ-error-atomic`, `REQ-config` |

## System Coverage

| Case ID | system_dimension | Crossed modules | Requirement refs |
| --- | --- | --- | --- |
| `MMS001` | `content_graph_fanout` | frontmatter -> render pages -> listings -> feed -> search -> manifest | `REQ-frontmatter`, `REQ-content-pages`, `REQ-list-pages`, `REQ-json-feeds`, `REQ-search-index`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS002` | `classification_propagation` | date/kind/draft classification -> public pages -> listings -> feed/search/manifest absence | `REQ-date-kind`, `REQ-drafts`, `REQ-list-pages`, `REQ-json-feeds`, `REQ-search-index`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS003` | `taxonomy_cross_views` | tags + streams -> taxonomy listing pages -> taxonomy feeds -> manifest groups | `REQ-tags`, `REQ-streams`, `REQ-list-pages`, `REQ-json-feeds`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS004` | `pagination_manifest_consistency` | pagination config -> tag/stream listing files -> manifest membership | `REQ-config`, `REQ-list-pages`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS005` | `link_graph_consistency` | slug derivation -> wikilink rendering -> backlink pages -> manifest | `REQ-title-slug`, `REQ-markdown-html`, `REQ-wikilinks-backlinks`, `REQ-content-pages`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS006` | `exclusion_propagation` | draft detection -> absence from rendered pages/listings/feeds/search/manifest | `REQ-drafts`, `REQ-tags`, `REQ-streams`, `REQ-json-feeds`, `REQ-search-index`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS007` | `config_effects` | base URL and toggles -> feed URLs/search presence -> manifest consistency | `REQ-config`, `REQ-json-feeds`, `REQ-search-index`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS008` | `filename_metadata_flow` | filename date/stream parsing -> slug/output path -> stream listing/feed/manifest | `REQ-title-slug`, `REQ-date-kind`, `REQ-streams`, `REQ-content-pages`, `REQ-list-pages`, `REQ-json-feeds`, `REQ-url-manifest` |
| `MMS009` | `manifest_summary_consistency` | generated pages/listings/feeds/search -> manifest groups -> summary counts | `REQ-list-pages`, `REQ-json-feeds`, `REQ-search-index`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS010` | `inspect_build_consistency` | inspect parsed state -> generated files -> listing and manifest entries | `REQ-inspect`, `REQ-content-pages`, `REQ-list-pages`, `REQ-url-manifest`, `REQ-system-invariants` |
| `MMS011` | `error_atomicity` | duplicate slug detection -> command failure -> no partial public files | `REQ-title-slug`, `REQ-error-atomic` |
| `MMS012` | `error_atomicity` | invalid frontmatter detection -> command failure -> no partial public files | `REQ-frontmatter`, `REQ-error-atomic` |

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
- Marmite rubric JSON subset checks use `*_json_contains_unordered` so arrays
  assert membership, not order, unless a path-specific exact scalar check is
  used.
