# Project Context For External AI Review

## Background

This repository is part of a benchmark construction effort for evaluating AI
coding agents on system-level software tasks. Existing single-issue repair
benchmarks can become saturated: models may pass isolated bug-fix or unit-level
tasks while still failing when multiple features must compose into one coherent
system.

The benchmark design here follows a PRD-plus-rubric handoff pattern:

- `prd.md` is the model-visible product requirement document.
- `rubric.json` is the hidden evaluation definition used to score outputs.

The selected source project is `SarthakMakhija/bitcask`, a Bitcask-style
log-structured key/value store. The task abstracts it into a smaller
mini-bitcask CLI while preserving system behaviors such as append-only writes,
tombstone deletion, compaction, metadata consistency, durability reload, and
error atomicity.

Current status: candidate handoff task. The PRD/rubric structure is ready for
external review, but this repository does not claim confirmed strong gap
evidence.

## Goal

The goal is to test whether a model can maintain global correctness across
composed workflows, not merely implement isolated commands.

The expected benchmark signal is:

```text
unit_score - system_score
```

The ideal task produces high unit pass rates but lower system pass rates for
weaker agents, revealing the gap between local feature correctness and
cross-feature system correctness.

## What To Review

Review these files first:

- `AGENTS.md`: repo-wide construction and leakage-prevention rules.
- `INDEX.md`: review index and mechanical checks.
- `task/bitcask-realrepo-001/prd.md`: model-visible requirements.
- `task/bitcask-realrepo-001/rubric.json`: unit/system evaluation cases.
- `task/bitcask-realrepo-001/doc/source_repo.md`: source-project rationale.
- `task/bitcask-realrepo-001/doc/requirement_map.md`: traceability map.

## Review Questions

1. Does `prd.md` describe only public, model-visible behavior?
2. Can every `rubric.json` case be naturally inferred from `prd.md`?
3. Are unit cases and system cases meaningfully separated?
4. Do system cases combine features and check global invariants?
5. Does the rubric avoid private implementation details?
6. Do all `requirement_refs` map back to `requirement_map.md`?
7. Is there any answer leakage, reference implementation, scorer, candidate
   output, or score report committed?
8. Are the repository rules in `AGENTS.md` sufficient for future task
   construction?

## Non-Goals

- Do not evaluate whether a submitted `kvmini.py` implementation is good; this
  repository should not contain one.
- Do not require the task to reproduce the full original Go project.
- Do not require a specific on-disk file format unless the PRD explicitly says
  so.

## Expected Review Output

Return findings ordered by severity. Each finding should include:

- file path and line number
- the concrete issue
- why it affects correctness, fairness, or leakage risk
- a specific recommended change

If there are no blocking issues, state that clearly and mention any residual
risks, such as insufficient evidence that the task produces a strong unit/system
gap.
