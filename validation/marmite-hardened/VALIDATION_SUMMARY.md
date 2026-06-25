# Hardened Marmite Validation Summary

Branch: `validation/marmite-hardened`

Task: `task/marmite-realrepo-001`

Rubric size: 34 cases

- Unit: 19
- System: 15

Validation assets are kept under `validation/marmite-hardened/`. The main
handoff branch should not receive reference implementations, scorer scripts,
candidate outputs, reports, or score summaries.

## Runs

| Run | Type | Unit | System | Unit score | System score | Gap pp | Failed cases |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `reference` | reference | 19/19 | 15/15 | 100.00 | 100.00 | 0.00 | none |
| `codex_agent_001` | candidate | 19/19 | 15/15 | 100.00 | 100.00 | 0.00 | none |
| `codex_agent_002` | candidate | 17/19 | 14/15 | 89.47 | 93.33 | -3.86 | `MMU005`, `MMU007`, `MMS008` |
| `codex_agent_003` | candidate | 17/19 | 14/15 | 89.47 | 93.33 | -3.86 | `MMU005`, `MMU007`, `MMS008` |

## Reference Gate

The hardened reference implementation passes all rubric cases:

- `19/19` unit
- `15/15` system
- `100/100` overall satisfiability gate

This supports that the hardened PRD/rubric packet is executable and
reference-satisfiable.

## Candidate Failure Analysis

`codex_agent_001` passed all cases, so it provides no positive unit/system gap
evidence.

`codex_agent_002` and `codex_agent_003` failed the same three cases:

- `MMU005`: local date/kind parsing. Both candidates treated
  `from-frontmatter.md` with frontmatter date as if the filename supplied a
  stream prefix, producing `stream: "from"` and slug `from-frontmatter` instead
  of the PRD-derived index-stream post slug `front-date`.
- `MMU007`: local stream filename parsing. Both candidates mishandled
  `stream-S-name.md` with a valid frontmatter date; the expected public
  behavior is stream `guide` and slug `guide-front-date`.
- `MMS008`: system filename metadata flow. This failure is downstream of the
  same `stream-S-name.md` parsing issue, causing the wrong generated page,
  stream feed, and manifest entries.

These are weak local feature implementation failures, not positive
system-composition gap evidence. The observed gap is negative because system
score is higher than unit score for these two candidates.

## Interpretation

Current status:

```text
marmite-realrepo-001: reference-satisfiable; no positive unit/system gap observed in hardened validation batch
```

Do not claim:

- `core_strong`
- `confirmed benchmark`
- `gap-producing`

The hardening pass improved source-derived coverage around draft-aware link
exclusion, archive-year taxonomy, and `urls`/manifest parity, but this batch
does not show the desired high-unit/lower-system pattern. Further hardening, if
any, should continue to use only public, source-grounded Marmite behavior.
