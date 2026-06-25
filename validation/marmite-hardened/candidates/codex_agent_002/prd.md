# Mini Marmite Static Site PRD

## Goal

Build `minisite.py`, a local static-site generator inspired by
`rochacbruno/marmite`. The program reads Markdown content files, extracts a
small public metadata subset, renders deterministic HTML and JSON outputs, and
keeps posts, pages, taxonomies, pagination, feeds, search, URL manifest,
wikilinks, backlinks, and draft exclusion mutually consistent.

The benchmark focuses on observable behavior. It does not require the original
Marmite package, Rust code, Tera templates, exact CommonMark parity, server
mode, themes, image processing, shortcodes, or any private internal structure.

## Invocation

All commands are run as:

```console
python minisite.py COMMAND [OPTIONS]
```

Paths are interpreted relative to the current working directory unless absolute.
Successful commands print one compact JSON value followed by a newline. Failed
commands exit non-zero, print a useful stderr message, and must not partially
write or corrupt the output directory.

Supported commands:

```console
python minisite.py build --input INPUT --output OUTPUT [--config CONFIG]
python minisite.py inspect --input INPUT [--config CONFIG]
python minisite.py urls --input INPUT [--config CONFIG]
```

`build` reads content from `INPUT`, writes the generated site to `OUTPUT`, and
prints the same JSON object written to `OUTPUT/urls.json`.

`inspect` parses the same input state without writing site files and prints a
compact JSON object with `posts`, `pages`, `tags`, `streams`, and `drafts`
arrays. This command exists to expose parsing behavior for local verification.

`urls` parses the same input state and prints the same manifest object that
`build` would write to its `OUTPUT/urls.json`, without creating an output
directory or writing any site files. It must respect config, taxonomy, archives,
pagination, draft exclusion, feed/search toggles, and base URL rules.

## Input Layout

If `INPUT/content/` exists, Markdown content is read recursively from that
directory. Otherwise Markdown content is read recursively from `INPUT`.

Only files ending in `.md` are content files. Files whose basename starts with
`_` are fragments and are ignored by this mini task. Non-Markdown files are
ignored.

The optional config path defaults to `INPUT/marmite.yaml`. If `--config CONFIG`
is supplied, use that file instead. A missing config file is allowed and means
defaults.

## Config Format

The config file is a small YAML-like file with one `key: value` pair per line.
Blank lines and lines beginning with `#` are ignored. Supported keys:

- `site_name`: string, default `"Mini Marmite"`.
- `base_url`: string, default `""`.
- `pagination`: positive integer, default `10`.
- `json_feed`: boolean, default `true`.
- `enable_search`: boolean, default `true`.

Boolean values accept `true` and `false`. Unsupported config keys are ignored.
Invalid supported values fail non-zero and write no output.

## Frontmatter Format

A content file may start with YAML-like frontmatter delimited by a line exactly
equal to `---` and the next line exactly equal to `---`.

Supported metadata keys:

- `title`: string.
- `slug`: string.
- `date`: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM[:SS]`.
- `tags`: either `[a, b]` or comma-separated string.
- `stream`: string.
- `description`: string.

Quoted string values may use single or double quotes. Unsupported frontmatter
keys are ignored. Invalid supported values fail non-zero and write no output.

## Content Model

Every parsed content item has:

- `title`
- `slug`
- `source`: POSIX-style path relative to the content root
- `kind`: `post` or `page`
- `date`: normalized `YYYY-MM-DD` string or `null`
- `tags`: array of strings
- `stream`: string for posts, `null` for pages
- `description`: string or `null`
- `draft`: boolean
- `links_to`: array of slugs
- `backlinks`: array of slugs

### Title

Use frontmatter `title` when present. Otherwise use the first Markdown heading
line beginning with `# `. If neither exists, use the filename stem after removing
date and stream prefixes.

### Slug

Use frontmatter `slug` when present. Otherwise slugify the title. If the title
was inferred from filename fallback, slugify the cleaned filename stem. For
recognized date-prefixed or stream-prefixed post filenames, the filename slug
base below is used when frontmatter `slug` is absent; the title may still come
from frontmatter or the first heading.

Slugification lowercases text, replaces every run of non-ASCII alphanumeric
characters with `-`, and trims leading/trailing `-`.

Date prefixes are removed from filename-derived slugs:

- `YYYY-MM-DD-name.md` -> `name`
- `YYYY-MM-DD-HH-MM-SS-name.md` -> `name`

Stream filename prefixes are also recognized:

- `stream-YYYY-MM-DD-name.md` -> stream `stream`, slug `stream-name`
- `stream-S-name.md` with a valid date in frontmatter -> stream `stream`, slug
  `stream-name`

If a non-default stream is supplied by frontmatter, the output slug is
`stream-base-slug`. If the stream is missing or `index`, do not add a stream
prefix.

### Date, Posts, And Pages

If a valid date exists in frontmatter, use it. Otherwise try to derive the date
from a recognized date-prefixed filename. Items with a date are posts. Items
without a date are pages.

Posts are sorted by date descending, then slug ascending. Pages are sorted by
title ascending, then slug ascending.

### Tags

Tags may come only from frontmatter. Empty tags are ignored. Tag slugs use the
same slugification rule as content slugs. A post can belong to multiple tags.
Pages do not appear in tag listing pages or tag feeds.

Content item `tags` arrays in `inspect`, JSON feeds, and `search_index.json`
preserve the cleaned tag strings from frontmatter. Tag map keys, tag page
filenames, and tag feed filenames use slugified tag names.

### Streams

Posts belong to stream `index` by default. A stream may be supplied by
frontmatter or by the recognized filename prefixes above. Stream listing pages
are generated for non-`index` streams. Pages do not belong to streams and must
use `stream: null` in JSON outputs.

### Drafts And Exclusion

A post is a draft when its stream is `draft`, including filename-derived stream
prefixes such as `draft-2026-01-01-note.md`. Draft content is parsed and exposed
by `inspect` with `draft: true`, but `build` must exclude it from public output:
no HTML page, listing entry, taxonomy entry, feed item, search item, backlink,
or URL manifest entry is generated for draft content.

Draft content is not a public wikilink target. If public content links to a
draft title with `[[Title]]` or `[[Title|Label]]`, that wikilink behaves like an
unknown wikilink. Draft content also must not appear as a backlink source or
backlink target in public generated pages.

This is a deterministic mini-task adaptation of Marmite's draft-stream
filtering behavior.

## Markdown Rendering

The renderer only needs this subset:

- `# Heading` becomes `<h1 id="heading">Heading</h1>`.
- `## Heading` becomes `<h2 id="heading">Heading</h2>`.
- Non-empty plain text lines become `<p>text</p>`.
- Blank lines separate paragraphs.
- Inline links `[text](target.md)` and `[text](target.html)` to local content are
  rewritten to the target slug plus `.html`.
- External links beginning with `http://` or `https://` are preserved.
- Wikilinks `[[Title]]` resolve by case-insensitive title match to
  `slug.html`. Wikilinks `[[Title|Label]]` use `Label` as link text. Unknown
  wikilinks remain as links with `data-wikilink="missing"` and href based on the
  slugified title.

HTML escaping is required for text content and metadata. Raw HTML, tables,
footnotes, syntax highlighting, emojis, spoilers, and full CommonMark behavior
are non-goals.

## Generated Files

Before writing, `build` may create `OUTPUT` if needed. Existing files in
`OUTPUT` that are part of this mini task may be overwritten. Output filenames
are flat: generated files live directly under `OUTPUT`. For this task the
search index path is exactly `OUTPUT/search_index.json`.

### Content Pages

Every non-draft post and page generates `{slug}.html`.

Each page must contain:

- `<title>{title}</title>`
- a rendered content body
- a backlink section listing source slugs that link to this page, if any

### Index And Pages Listings

`index.html` is always generated. It lists non-draft posts from stream `index`,
sorted by post order. If the post count exceeds `pagination`, also generate
`index-2.html`, `index-3.html`, and so on. `index-1.html` is not required.

`pages.html` is generated when there is at least one non-draft page. It lists
all pages sorted by page order. Pages are not paginated.

Listing pages must include links to each listed content page.

### Tag Listings

For every tag used by at least one non-draft post, generate `tag-{tag}.html`.
If that tag has more posts than `pagination`, also generate
`tag-{tag}-2.html`, `tag-{tag}-3.html`, and so on.

`tags.html` is generated when at least one tag page is generated. It lists all
generated tag pages.

### Stream Listings

For every non-`index`, non-`draft` stream used by at least one non-draft post,
generate `{stream}.html`. If that stream has more posts than `pagination`, also
generate `{stream}-2.html`, `{stream}-3.html`, and so on.

`streams.html` is generated when at least one non-default stream page is
generated. It lists all generated non-default stream pages.

### Archive Listings

For every year with at least one non-draft post, generate
`archive-{YYYY}.html`. If that archive year has more posts than `pagination`,
also generate `archive-{YYYY}-2.html`, `archive-{YYYY}-3.html`, and so on.

`archive.html` is generated when at least one archive year page is generated.
It lists all generated archive year pages. Archive pages include only non-draft
posts and exclude pages. Archive item order follows post order.

## JSON Feeds

When `json_feed` is true, generate:

- `feed.json` for non-draft `index` stream posts.
- `tag-{tag}.json` for each tag.
- `{stream}.json` for each non-`index`, non-`draft` stream.
- `archive-{YYYY}.json` for each archive year.

Each feed is a JSON object:

```json
{"title":"","items":[]}
```

`title` is the site name for `feed.json`, `tag:{tag}` for tag feeds,
`stream:{stream}` for stream feeds, and `archive:{YYYY}` for archive feeds.
Each item contains `title`, `slug`, `url`, `date`, `tags`, `stream`, and
`description`. `url` is `{slug}.html` when `base_url` is empty, otherwise
`{base_url}/{slug}.html` with exactly one slash between base and slug. Feed item
order follows the corresponding listing order.

When `json_feed` is false, no feed files are generated and `urls.json.feeds`
must be empty.

## Search Index

When `enable_search` is true, generate `search_index.json`, a JSON array
containing every non-draft post and page. Each item contains `title`, `slug`,
`url`, `kind`, `tags`, `stream`, and plain rendered text without HTML tags.
Search item `url` follows the same rule as feed item `url`.

When `enable_search` is false, no `search_index.json` is generated and
`urls.json.search` must be empty.

## URL Manifest

`build` must write `OUTPUT/urls.json` and print the same compact JSON object.

The manifest contains arrays of generated paths grouped by kind:

```json
{
  "posts": [],
  "pages": [],
  "index": [],
  "tags": [],
  "streams": [],
  "archives": [],
  "feeds": [],
  "search": [],
  "misc": [],
  "summary": {}
}
```

Paths are relative output paths without a leading slash, for example
`post-one.html`. If `base_url` is non-empty, each generated content, listing,
feed, and search item may also include full URLs internally, but manifest paths
remain relative.

Manifest groups have these meanings:

- `posts`: non-draft post content pages.
- `pages`: page content pages plus `pages.html` when generated.
- `index`: `index.html` and index pagination files.
- `tags`: tag listing pages plus `tags.html` when generated.
- `streams`: stream listing pages plus `streams.html` when generated.
- `archives`: archive year listing pages plus `archive.html` when generated.
- `feeds`: generated JSON feed files.
- `search`: `search_index.json` when generated.
- `misc`: `urls.json` only, unless a later PRD revision explicitly defines
  another miscellaneous public file.

`summary` must include integer counts for every array key plus `total`.
`summary.<group>` equals `len(manifest[group])` for each manifest array,
including `summary.misc == 1` because `misc` contains `urls.json`.
`summary.total` is the sum of all generated public paths represented in the
manifest except `urls.json` itself, so it equals the sum of all group lengths
minus one.

The manifest is the primary global invariant: every public generated file must
be represented exactly once in the appropriate manifest group, and draft content
must not appear in any manifest path.

## Inspect Output

`inspect` prints:

```json
{"posts":[],"pages":[],"tags":{},"streams":{},"drafts":[]}
```

`posts` and `pages` contain non-draft content-model objects. `drafts` contains
draft content-model objects. `tags` maps tag slugs to non-draft post slugs.
`streams` maps stream names to non-draft post slugs, excluding `draft`. Inspect
output includes drafts so parser behavior is visible, but public build outputs
exclude drafts.

## Error Behavior

These fail non-zero and write no output files:

- unsupported command
- missing required arguments
- missing input directory
- invalid config value
- invalid supported frontmatter value
- duplicate final slug among non-draft content
- invalid `pagination` value
- unable to create or write output directory

If a build fails after creating `OUTPUT`, it must not leave any partially
generated mini-task output files in that directory.

## Global Invariants

- The same parsed source state must drive HTML pages, listing pages, feeds,
  search index, backlinks, and `urls.json`.
- Post/page classification must be consistent across all outputs.
- Tags and streams must agree across content pages, listing pages, feeds,
  search index, inspect output, and manifest groups.
- Archive years must agree across post dates, archive listing pages, archive
  feeds, search index, and manifest groups.
- Pagination must agree with generated listing files and manifest paths.
- Wikilink resolution and backlinks must agree with final slugs.
- Draft content must be visible in `inspect` but absent from all public build
  outputs.
- Config toggles must affect all relevant outputs consistently.
- `urls` output must match the manifest that `build` would write for the same
  input and config, while writing no site files.
- Re-running `build` on the same input must produce the same public files and
  JSON content, ignoring file modification times.

## Non-Goals

- No full CommonMark or GitHub Flavored Markdown parity.
- No Tera templates, theme loading, or exact Marmite HTML layout.
- No image resizing, image downloading, galleries, or media copying.
- No syntax highlighting.
- No RSS/XML feed generation.
- No sitemap generation.
- No server, watch mode, live reload, or network behavior.
- No shortcodes, comments integration, or interactive prompts.
- No authors, series, or custom file mappings in this mini task.
- No dependency on Marmite internals, Rust structs, module names, or rendering
  order.
