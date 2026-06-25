# Marmite Hardening Proposal

Status reviewed: `main` at Marmite handoff status plus validation evidence on
`validation/marmite`.

This note is a proposal only. It does not change `prd.md`, `rubric.json`, or
validation artifacts.

## Current Validation Summary

Current Marmite status:

```text
marmite-realrepo-001: reference-satisfiable; no positive gap observed in this validation batch
```

Evidence from `validation/marmite`:

| Run | Unit | System | Gap pp | Interpretation |
| --- | --- | --- | --- | --- |
| reference | 16/16 | 12/12 | 0.0 | satisfiable |
| codex_agent_001 | 16/16 | 12/12 | 0.0 | no gap observed |
| codex_agent_002 | 16/16 | 12/12 | 0.0 | no gap observed |
| codex_agent_003 | 8/16 | 9/12 | -25.0 | low unit, no positive gap |

This means the task is executable and reference-satisfiable, but the evidence
does not support `core_strong`, `confirmed benchmark`, or `gap-producing`.

## Why No Positive Gap Was Observed

The first two candidate implementations passed all unit and system cases. That
shows the current public surface, while broad, is still implementable end to
end by strong code agents from the PRD alone.

The third candidate failed many local behaviors before reaching a system-level
composition boundary. Its system failures were mostly downstream of the same
local parsing, slug, rendering, and manifest mistakes. Because unit score was
already low and system score was higher than unit score, it is not evidence of
the desired high-unit/lower-system degradation pattern.

## codex_agent_003 Failure Classification

| Failed cases | Classification | Reason |
| --- | --- | --- |
| `MMU001`, `MMU004`, `MMU005`, `MMU007` | weak local feature implementation | Inspect, title/slug, date/kind, and stream parsing did not match public PRD rules. |
| `MMU009`, `MMU012`, `MMU014`, `MMU015` | weak local feature implementation with downstream output effects | Rendered filenames, listing entries, search entries, and manifest paths diverged from the parsed slug model. |
| `MMS002`, `MMS005`, `MMS008` | downstream system failures, not true gap evidence | These failures followed from local slug/page/link mistakes rather than isolated units passing while composition failed. |
| none after validation fixes | PRD ambiguity | Initial filename slug ambiguity was fixed in `main`; current failed cases do not reveal a new PRD ambiguity. |
| none observed | scorer/rubric overconstraint | Current checks use public CLI output, generated files, and unordered JSON subset checks. No private implementation constraint was identified. |

## Source-Grounded Hardening Ideas

### 1. Draft-Aware Link Graph And Public Exclusion

Source behavior basis:

- `tests/content_generation.rs` covers `draft-` content exclusion.
- `src/feed.rs` filters stream `draft` content from RSS/JSON feeds.
- `src/site.rs` filters draft content from search and grouped views.
- `README.md` and `src/parser.rs` document wikilinks/backlinks as public
  features.

Public PRD behavior to add or clarify:

- Public wikilinks to draft content should behave like unresolved wikilinks.
- Draft content remains visible in `inspect.drafts`, but must not be a public
  wikilink target, backlink source/target, feed item, search item, taxonomy
  entry, or manifest path.

Likely unit coverage:

- A public page linking to a draft title keeps a visible missing wikilink.
- `inspect` still shows the draft with parsed title, slug, tags, and stream.

Likely system coverage:

- One content set includes public post, draft post, tag, stream, wikilink, feed,
  search, and manifest. The draft is visible only in `inspect` and absent from
  all public derived views.

Why it may create system-level pressure:

- The model must maintain one exclusion rule across parser state, link
  resolution, backlinks, taxonomies, feeds, search, and manifest. This is a
  genuine Marmite lifecycle interaction rather than a local command feature.

Risk:

- Low if defined publicly. Avoid requiring exact HTML template text or internal
  backlink storage shape.

### 2. Archive-Year Taxonomy From Dates

Source behavior basis:

- `src/site.rs` groups dated posts into archive pages and archive feeds.
- `src/site.rs` records archive URLs in `urls.json`.
- `source_repo.md` currently notes archives as source-supported but excluded
  from the first PRD.

Public PRD behavior to add:

- Generate `archive-{YYYY}.html` for each year with at least one non-draft
  post, plus `archive.html` as the aggregate archive listing.
- When JSON feeds are enabled, generate `archive-{YYYY}.json`.
- Add `archives` as a manifest group and summary count.

Likely unit coverage:

- Date extraction maps posts into archive years.
- Draft posts and pages do not appear in archive outputs.

Likely system coverage:

- Mixed years, tags, streams, pagination, feeds, search, and `urls.json` must
  agree on which posts belong to each year.

Why it may create system-level pressure:

- Archives reuse date classification, ordering, feed generation, manifest
  grouping, and draft exclusion. This adds an independent derived view without
  introducing private implementation checks.

Risk:

- Medium-low. It is source-derived and public, but broadens taxonomy surface.
  Keep it year-only; do not add month/day archives unless source grounding and
  PRD clarity justify it.

### 3. Author Taxonomy With Optional Config Metadata

Source behavior basis:

- `src/content.rs` parses `authors`.
- `src/config.rs` defines author metadata.
- `src/site.rs` generates author pages, author feeds, `authors.html`, and
  records author URLs in the manifest.
- `src/feed.rs` includes author data in feed items.

Public PRD behavior to add:

- Support frontmatter `authors` as `[a, b]` or comma-separated string.
- Generate `author-{author}.html`, `authors.html`, and optional
  `author-{author}.json` feeds.
- Preserve cleaned author strings in content/feed/search items and use
  slugified author names for filenames and manifest groups.

Likely unit coverage:

- Parse author lists and slugify author page names.
- Feed/search item authors match cleaned frontmatter strings.

Likely system coverage:

- A post with tags, stream, authors, draft status, and links must propagate to
  author pages/feeds, tag pages/feeds, stream pages/feeds, search, and manifest
  consistently.

Why it may create system-level pressure:

- Authors introduce a third taxonomy dimension parallel to tags and streams.
  Correct implementations need a reusable grouping model rather than one-off
  tag/stream handling.

Risk:

- Medium. Full Marmite author config includes avatars/links and is too broad.
  A mini-task should keep only public author strings and author grouping unless
  config metadata is explicitly justified.

### 4. Pinned Post Ordering Across Derived Views

Source behavior basis:

- `src/content.rs` parses `pinned`.
- `src/site.rs` sorts stream and author content with pinned items before
  unpinned items, then by date.

Public PRD behavior to add:

- Support frontmatter `pinned: true|false`, default `false`.
- Listing and corresponding feed order for index, tag, stream, archive, or
  author views should put pinned posts first, then unpinned posts by normal post
  order.

Likely unit coverage:

- Parse `pinned` in `inspect`.
- A single listing/feed shows pinned-before-date behavior.

Likely system coverage:

- The same pinned order must appear consistently in listing HTML, JSON feeds,
  and any order-sensitive public JSON outputs for index/tag/stream views.

Why it may create system-level pressure:

- Ordering is easy to get right in one output and wrong in another. It stresses
  shared sorted views across multiple derived products.

Risk:

- Medium. Order assertions can become overconstrained if the PRD does not define
  exact ordering. Only add this if exact public ordering is explicitly specified
  and checked through public outputs.

### 5. Show-URLs / Manifest Preview Command

Source behavior basis:

- `tests/basic_functionality.rs` covers `--show-urls`.
- `src/site.rs` has `show_urls`, `create_urls_json`, and grouped URL summary
  generation.

Public PRD behavior to add:

- Add a read-only command such as:

```console
python minisite.py urls --input INPUT [--config CONFIG]
```

- It prints the same manifest object that `build` would write, without creating
  output files.
- It must respect config, tags, streams, archives/authors if added, pagination,
  draft exclusion, feeds, search, and base URL rules.

Likely unit coverage:

- `urls` command emits JSON and writes no files.
- It handles config toggles without requiring an output directory.

Likely system coverage:

- `urls` output must match `build`'s `urls.json` for the same source state while
  also preserving error atomicity and no-write behavior.

Why it may create system-level pressure:

- It forces the same manifest derivation to work independently from file
  emission. This mirrors Marmite's URL preview behavior and catches duplicated
  build-only manifest logic.

Risk:

- Low-medium. It is source-derived, but it adds CLI surface. Keep the command
  read-only and JSON-only; do not require exact source CLI flags or absolute URL
  formatting unless explicitly defined in the PRD.

## Recommended Hardening Scope

If hardening proceeds, use a small pass rather than adding all ideas at once.
The best first pass is:

1. Draft-aware link graph and public exclusion.
2. Archive-year taxonomy.
3. Show-URLs / manifest preview command.

Defer author taxonomy and pinned ordering unless the first hardening pass still
does not produce useful evidence. Authors add breadth, and pinned ordering needs
careful public ordering semantics to avoid unfair scorer expectations.

Proceed with a small PRD/rubric hardening pass.
