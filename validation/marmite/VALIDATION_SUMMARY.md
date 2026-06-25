# Marmite Validation Summary

Branch: `validation/marmite`

Task: `task/marmite-realrepo-001`

Rubric size: 28 cases, 16 unit and 12 system.

## Scope

Validation assets are under `validation/marmite/` on this validation branch:

- `reference/minisite.py`
- `score.py`
- `reports/*.json`
- `candidates/codex_agent_*/`
- `score_summary.csv`

Candidate agents were assigned separate directories containing only `prd.md`
and were instructed not to inspect the rubric, scorer, reference, reports, or
other candidates.

## PRD/Rubric Alignment Found During Validation

Reference validation exposed one public ambiguity:

- Several rubric cases expected date-prefixed or stream-prefixed post filenames
  to drive the final slug even when the title came from a heading.

The PRD was clarified on this branch to make that behavior public:

- Recognized date-prefixed or stream-prefixed post filenames provide the slug
  base when frontmatter `slug` is absent.
- The title may still come from frontmatter or the first heading.

One direct rubric alignment fix was also made:

- `MMU015` now expects `news-post.html` for `2026-11-01-post.md` with
  `stream: news`, matching the clarified filename slug rule.

These are public behavior fixes, not hidden test additions.

## Results

| Run | Unit | System | Gap pp | Failed case IDs | Status |
| --- | --- | --- | --- | --- | --- |
| reference | 16/16 | 12/12 | 0.0 | none | satisfiable |
| codex_agent_001 | 16/16 | 12/12 | 0.0 | none | no_gap_observed |
| codex_agent_002 | 16/16 | 12/12 | 0.0 | none | no_gap_observed |
| codex_agent_003 | 8/16 | 9/12 | -25.0 | MMU001 MMU004 MMU005 MMU007 MMU009 MMU012 MMU014 MMU015 MMS002 MMS005 MMS008 | low_unit_no_positive_gap |

## Qualitative Failure Reasons

`codex_agent_003` failed mostly on local parsing and slug/rendering behavior:

- inspect output did not match input layout, title/slug, date/kind, or stream
  expectations.
- rendered page filenames for heading-derived pages did not match PRD slugs.
- search index and manifest entries did not stay aligned with expected slugs.
- link graph cases failed because generated page filenames/backlinks diverged
  from the parsed slug model.

Because unit score was already low and system score was not lower than unit,
this run does not provide unit/system degradation evidence.

## Interpretation

This validation proves:

- the Marmite task is executable;
- the reference implementation satisfies the current PRD/rubric;
- at least two independent code-agent candidates can reach 100/100;
- one candidate fails, but not in the desired high-unit/lower-system pattern.

Current status:

```text
marmite-realrepo-001: reference-satisfiable; no positive gap observed in this validation batch
```

Do not claim:

```text
core_strong
confirmed gap-producing
```

