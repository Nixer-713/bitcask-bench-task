# Marmite Source Repository Notes

## Canonical Source

- Repository: `https://github.com/rochacbruno/marmite`
- Local checked revision: `908a69e` on `main`
- Local checkout used for analysis only:
  `/Users/nixer/项目/benchmark-source-repos/marmite`

Primary evidence should cite repository-relative paths, not local absolute
paths.

## Source Evidence Paths

- `README.md`
- `src/content.rs`
- `src/parser.rs`
- `src/site.rs`
- `src/feed.rs`
- `src/config.rs`
- `tests/basic_functionality.rs`
- `tests/content_generation.rs`
- `tests/features.rs`
- `tests/streams.rs`
- `tests/wikilinks_integration.rs`

## Source Capability Map

### CLI And Site Build

- `README.md` documents the public CLI shape:
  `marmite <INPUT_FOLDER> <OUTPUT_FOLDER>` with optional config.
- `README.md` describes the core build pipeline: read markdown files, parse
  CommonMark, extract metadata from frontmatter or filename, render HTML files,
  and output a static site.

### Content Parsing

- `src/content.rs` builds `Content` from markdown files.
- `parse_front_matter` is used to split metadata from raw markdown.
- `get_title` derives title from frontmatter or the first markdown heading.
- `get_slug` derives slug from frontmatter title/slug or filename.
- `get_date` derives date from frontmatter or date-prefixed filenames.
- `get_tags`, `get_authors`, `determine_stream`, and `determine_series` extract
  grouping metadata.

### Post/Page Classification

- `README.md` states that `date` differentiates posts from pages.
- `src/site.rs` pushes dated content into `posts` and undated content into
  `pages`.
- Posts are sorted newest first; pages are sorted by title.

### Taxonomies And Grouped Views

- `src/site.rs` groups posts by tag, author, archive year, stream, and series.
- Tag URLs use `tag-{slug}.html`.
- Stream URLs use `{stream}.html` except the default `index` stream.
- Archive, author, and series pages have their own grouped outputs.
- `tests/content_generation.rs` checks tag page generation.
- `tests/streams.rs` checks stream pages from frontmatter and filename
  patterns.

### Pagination

- `src/site.rs` records pagination URLs for index, pages, tags, authors,
  streams, archives, and series when content count exceeds configured
  pagination.
- `tests/content_generation.rs` checks `index.html` and `index-2.html` when
  pagination is set to 2.

### Feeds

- `src/feed.rs` generates RSS and JSON feeds from dated content.
- Draft stream content and undated pages are excluded from feeds.
- `src/site.rs` records feed URLs for streams, tags, authors, archives, and
  series.

### Search Index

- `README.md` lists static search index as a feature.
- `src/site.rs` calls `generate_search_index` when `enable_search` is true.
- `tests/features.rs` checks search-related static asset behavior.

### URL Manifest

- `src/site.rs` collects generated URLs across posts, pages, tags, authors,
  series, streams, archives, feeds, pagination, file mappings, and misc files.
- `src/site.rs` can publish `urls.json` when enabled by config.
- `tests/basic_functionality.rs` covers the `--show-urls` command.
- `tests/features.rs` covers sitemap generation.

### Wikilinks And Backlinks

- `README.md` lists wikilinks and backlinks as features.
- `src/parser.rs` resolves wikilinks against site data.
- `src/site.rs` collects backlinks by comparing each content item's outgoing
  links against other generated slugs.
- `tests/wikilinks_integration.rs` checks resolved wikilinks and unresolved
  wikilink behavior.

## Candidate Benchmark Shape

The likely mini-task should be a local static-site CLI, not a full Rust
reimplementation. A Python implementation target is reasonable if the PRD
defines observable output files and leaves internal architecture free.

Candidate public surface:

```console
python minisite.py build --input INPUT --output OUTPUT [--config CONFIG]
python minisite.py inspect --input INPUT [--config CONFIG]
```

Potential public outputs:

- Rendered `*.html` files for posts and pages.
- `index.html` and paginated `index-N.html`.
- Tag pages such as `tag-rust.html` plus tag pagination.
- Stream pages such as `news.html` plus stream pagination.
- RSS or JSON feed files for index/tags/streams.
- `search_index.json`.
- `urls.json` manifest.
- Resolved wikilink HTML and backlink lists.

## Case-Like Difficulty Rationale

Marmite is a stronger candidate than Bitcask/xitkit for system-gap pressure
because one source content graph fans out into many derived views. A model must
keep these outputs mutually consistent:

- frontmatter and filename parsing determine slug/date/status;
- date determines post vs page;
- post/page classification drives index, feeds, search, and URLs;
- tags/streams/authors/archives create taxonomy pages and feed subsets;
- pagination affects both generated files and URL manifest;
- wikilinks/backlinks require cross-content graph resolution;
- draft/excluded content must disappear from all derived outputs, not only from
  post pages.

This makes system cases naturally cross heterogeneous modules without relying
on private implementation details.

## Public Adaptation Boundaries

Likely source-derived behaviors:

- Markdown files are the source of content.
- YAML frontmatter can define title, slug, date, tags, authors, stream, and
  draft-like exclusion semantics.
- Date-bearing content is treated as post; undated content is page.
- Filename prefixes can contribute date/stream/slug information.
- Output site is flat: generated pages use `*.html` at output root.
- Tags and streams generate grouped listing pages.
- Pagination generates deterministic page files.
- Feeds/search/url manifest are derived from the same parsed content state.
- Wikilinks resolve to known content slugs; unknown links remain visibly
  unresolved.

Likely mini-task adaptations:

- Use a reduced markdown renderer, for example headings/paragraphs/links only.
- Use deterministic JSON manifests for easy scoring.
- Define a smaller config surface for site name, base URL, pagination, feeds,
  and search.
- Define exact filenames for mini outputs instead of reproducing every Marmite
  template.

Likely exclusions unless explicitly justified later:

- Exact Tera templates and theme system.
- Image resizing/downloads.
- Live server/watch mode.
- Syntax highlighting.
- Shortcodes beyond simple wikilinks.
- Full CommonMark parity.
- Exact Rust internal structs, modules, or rendering order.

## Next Source-Grounding Questions

Resolved boundary proposal below answers these questions for the first PRD
draft. The current `prd.md` follows this proposal. Rubric cases should not be
written until the PRD boundary is reviewed and stable.

## PRD Boundary Proposal

### Behavior Scope Decisions

| Source behavior | Decision | Reason |
| --- | --- | --- |
| Markdown input directory and output directory CLI | Keep | Core public Marmite behavior from `README.md`. |
| YAML frontmatter parsing | Keep, simplified | Needed for title, slug, date, tags, stream, draft, and config-derived outputs. |
| Title extraction from frontmatter or first heading | Keep | Source-derived in `src/content.rs`; easy to observe in HTML and manifests. |
| Slug extraction from frontmatter/title/filename | Keep, simplified | Central to generated filenames, URLs, wikilinks, feeds, and manifests. |
| Date extraction from frontmatter and date-prefixed filename | Keep | Drives post/page classification and chronological ordering. |
| Post/page classification by presence of date | Keep | Explicit in `README.md` and `src/site.rs`. |
| Tags taxonomy | Keep | Public feature and good cross-output system dimension. |
| Streams taxonomy | Keep | Public feature; source tests cover frontmatter and filename-derived streams. |
| Authors/series/archive | Simplify or exclude from first PRD | Useful but increases breadth; tags+streams already provide two heterogeneous groupings. |
| Pagination | Keep | Strong system pressure because it affects listing pages and URL manifest. |
| RSS/XML feed | Exclude from first PRD | XML parsing details add surface area without much extra source-graph pressure. |
| JSON feed | Keep | Source-supported and scorer-friendly; preserves feed semantics without XML friction. |
| `urls.json` manifest / `--show-urls` | Keep as core invariant | Source has `create_urls_json`, `generate_urls_json`, and `--show-urls`; ideal global oracle. |
| Search index | Keep | Source-supported; tests can check that only public content enters search. |
| Wikilinks | Keep | Public feature and tested integration behavior. |
| Backlinks | Keep as required derived metadata | Source collects backlinks; forces graph-level consistency across pages. |
| Draft/excluded content | Keep, define explicitly | Source filters draft-stream content from feeds/search and grouped listings; the mini task should make exclusion propagation public and deterministic. |
| Static/media copy | Exclude or mark optional | Mostly file-copy behavior; less useful for unit/system gap. |
| Sitemap | Exclude initially | `urls.json` covers the same global URL invariant in simpler JSON form. |
| Tera templates/theme system | Exclude | Private rendering architecture and large unrelated surface. |
| Full CommonMark/GFM parity | Exclude | Mini task should define a small observable markdown subset. |
| Image resizing/downloads | Exclude | Requires binary assets and external-image semantics. |
| Server/watch/live reload | Exclude | Operational mode, not needed for benchmark core. |
| Shortcodes/gallery/highlighting/comments | Exclude | Feature-specific and not necessary for source-derived system pressure. |

### Proposed Public Outputs

The mini task should expose these observable outputs:

- `*.html` files for each rendered post and page.
- `index.html` and paginated `index-N.html` post listings.
- `pages.html` for undated pages.
- `tag-{tag}.html` and `tag-{tag}-N.html` listing pages.
- `{stream}.html` and `{stream}-N.html` listing pages for non-default streams.
- `feed.json`, `tag-{tag}.json`, and `{stream}.json` JSON feeds.
- `search_index.json`.
- `urls.json` with grouped arrays and summary counts.
- Per-page HTML containing resolved wikilinks and backlink sections.

`urls.json` should be the primary system invariant oracle because it can tie
generated HTML files, taxonomy pages, pagination, feeds, and search-visible
content back to one parsed source state.

### Likely Unit Modules

- Frontmatter parsing and fallback title extraction.
- Slug/date extraction from frontmatter and filenames.
- Post/page classification.
- Tag extraction and tag page naming.
- Stream extraction from frontmatter and filename patterns.
- Basic markdown-to-HTML rendering for headings, paragraphs, and links.
- JSON feed item generation.
- Search index item generation.
- Wikilink resolution.
- Draft/excluded content recognition.

### Likely System Dimensions

- `content_graph_fanout`: one markdown source state generates pages, listings,
  feeds, search index, and URL manifest.
- `classification_propagation`: post/page/draft classification affects every
  derived output consistently.
- `taxonomy_cross_views`: tags and streams create pages, feed subsets,
  pagination, and manifest entries from the same posts.
- `pagination_manifest_consistency`: page counts and generated listing files
  agree with `urls.json`.
- `link_graph_consistency`: wikilinks and backlinks agree across rendered HTML
  and manifests.
- `exclusion_propagation`: draft content is consistently absent from the
  public outputs defined by the mini PRD while non-draft content remains
  visible.
- `config_effects`: config values such as pagination, base URL, and JSON feed
  toggle affect all relevant outputs consistently.

### Boundary Decisions For Open Questions

- Include both tags and streams. Tags alone are too close to one grouping
  module; tags+streams force parallel taxonomy logic and filename/frontmatter
  interactions.
- Use JSON feed rather than RSS/XML. Marmite supports both, but JSON is easier
  to score and still preserves feed membership/order semantics.
- Make `urls.json` a core invariant. It should be checked in most system cases
  because Marmite's source uses generated URL collection as a global site map.
- Make wikilinks/backlinks required system behavior. They are source-supported,
  observable, and graph-like enough to create system pressure.
- Define draft/excluded content publicly as `stream: draft` or filename stream
  prefix `draft-YYYY-MM-DD-...`. Source Marmite filters draft-stream content
  from feeds, search, and grouped listing contexts; the mini task should use a
  simpler public rule: excluded content produces no public page, taxonomy entry,
  feed item, search item, or URL manifest entry. This is a deterministic
  adaptation and must be stated in PRD before rubric cases rely on it.
