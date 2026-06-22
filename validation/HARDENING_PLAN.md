# Hardening Plan

Current validation still shows no unit/system gap across three code-agent
candidates. This means the evidence does not support `core_strong`; it does not
make the task invalid.

## Applied Lifecycle Cases

The rubric now includes `KVS013` through `KVS018`, all targeting public,
PRD-defined Bitcask lifecycle behavior:

- Longer mixed mutation histories before and after `compact`.
- Multiple `compact` calls interleaved with `put`, `update`, `delete`, `mget`,
  `list`, and `stats`.
- More explicit malformed-command atomicity sequences that check both
  `stats.log_entries` and live values after failure.
- Durability reload after every phase of a lifecycle: overwrite, delete,
  recreate, compact, and post-compact update.
- Rollover with a small `KVMINI_MAX_SEGMENT_BYTES` combined with delete,
  recreate, compact, and stats invariants.

Reference remains 100/100 after these additions. Three non-reference candidates
also remain 100/100, so the current evidence status is `no_gap_observed`.

## Rules for Further Hardening

- Every new case must be inferable from `prd.md`.
- Do not constrain on-disk file names, record formats, segment counts, classes,
  functions, or internal algorithms.
- Update `requirement_map.md` with each new case.
- Re-run reference first; reference must remain 100% before scoring candidates.
