# Marmite Rewrite Note

Status: prior Marmite PRD/rubric/map archived as no-positive-gap-observed
evidence under `archive/no-gap-observed/marmite-realrepo-001/`.

The active Marmite task is intentionally reset for redesign. Keep
`doc/source_repo.md` as the source-grounding base. Do not reuse the archived
PRD/rubric mechanically.

## Rewrite Focus

- Start from public behavior inventory, not Rust function boundaries.
- Build a capability map around build, inspect/check/status, content parsing,
  taxonomy generation, URL manifest, search/feed generation, wikilinks,
  backlinks, draft exclusion, and failure atomicity.
- Emphasize state/artifact flows that cannot collapse into one static content
  graph plus serializers.
- Prefer source-derived workflows such as build -> check/status -> failed
  rebuild atomicity -> derived index/manifest consistency.
- Do not add hidden requirements, exact Tera templates, full CommonMark parity,
  image processing, server/watch behavior, or Rust internals.
