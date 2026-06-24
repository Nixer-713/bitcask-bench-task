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
- `tests/basic_functionality.rs` covers the show-urls command.
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

- Which Marmite behaviors should be retained in PRD versus left as non-goals?
- Should the mini task include both tags and streams, or only one taxonomy plus
  wikilinks/backlinks?
- Should feeds be RSS/XML, JSON feed, or a simplified public JSON feed?
- Should `urls.json` be the primary system invariant oracle?
- How should draft/excluded content be publicly specified so it affects pages,
  taxonomies, feeds, search, and manifest consistently?
