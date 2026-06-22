# Hardening Plan

Current validation shows no unit/system gap across three code-agent candidates.
The next iteration should strengthen system workflows while staying inside the
current PRD.

Candidate additions should target public, PRD-defined behavior:

- Longer mixed mutation histories before and after `compact`.
- Multiple `compact` calls interleaved with `put`, `update`, `delete`, `mget`,
  `list`, and `stats`.
- More explicit malformed-command atomicity sequences that check both
  `stats.log_entries` and live values after failure.
- Durability reload after every phase of a lifecycle: overwrite, delete,
  recreate, compact, and post-compact update.
- Rollover with a small `KVMINI_MAX_SEGMENT_BYTES` combined with delete,
  recreate, compact, and stats invariants.

Rules for hardening:

- Every new case must be inferable from `prd.md`.
- Do not constrain on-disk file names, record formats, segment counts, classes,
  functions, or internal algorithms.
- Update `requirement_map.md` with each new case.
- Re-run reference first; reference must remain 100% before scoring candidates.
