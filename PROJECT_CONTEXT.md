# Project Context For External AI Review

## Background

This repository is part of a benchmark construction effort for evaluating AI
coding agents on system-level software tasks. Existing single-issue repair
benchmarks can become saturated: models may pass isolated bug-fix or unit-level
tasks while still failing when multiple features must compose into one coherent
system.

The benchmark design follows a PRD-plus-rubric handoff pattern:

- `prd.md` is the model-visible product requirement document.
- `rubric.json` is the hidden evaluation definition used to score outputs.

## Current Status

### Bitcask

`task/bitcask-realrepo-001` is a clean candidate handoff derived from
`SarthakMakhija/bitcask`. Validation evidence exists outside `main` showing that
the task is executable and reference-satisfiable, but tested code-agent
candidates also reached 100% unit and 100% system scores. Treat Bitcask as
candidate/no-gap-observed evidence. Do not claim `core_strong`, and do not add
more Bitcask lifecycle cases unless explicitly requested.

### Xitkit

`task/xitkit-realrepo-001` is a source-grounded candidate task derived from
`hoechstleistungshaartrockner/xitkit`. It abstracts the source into a local
`.xit` task-file CLI. The intended system pressure is that one task-file state
drives several public outputs and effects: parsed task records, filters, sorted
views, stats summaries, writeback results, and cross-file movement.

Initial validation evidence exists on `validation/xitkit`: the reference passed
16/16 unit and 12/12 system cases, and three independent code-agent candidates
also passed 16/16 unit and 12/12 system cases. Treat xitkit as
source-grounded candidate/no-gap-observed evidence. Do not claim
`core_strong`, `confirmed benchmark`, or `gap-producing` from current evidence.

### Marmite

`task/marmite-realrepo-001` is the active source-grounding target, derived from
`rochacbruno/marmite`. The expected benchmark direction is a static-site
generator task where one markdown content graph and configuration produce
multiple public outputs: rendered pages, taxonomies, pagination, feeds, search
index, URL manifest, and wikilink/backlink views.

`prd.md` now exists as the first model-visible draft, and
`doc/requirement_map.md` maps the public requirements and planned coverage.
Rubric is not drafted yet.

### Roadmap

The active roadmap is fixed unless the user changes it explicitly:

1. Keep Bitcask as candidate/no-gap-observed evidence.
2. Keep xitkit as source-grounded candidate/no-gap-observed evidence from
   initial validation.
3. Review the marmite PRD and requirement map, then draft rubric only after the
   public boundary is stable.

## Goal

The goal is to test whether a model can maintain global correctness across
composed workflows, not merely implement isolated commands.

The expected benchmark signal is:

```text
unit_score - system_score
```

The ideal task produces high unit pass rates but lower system pass rates for
weaker agents, revealing the gap between local feature correctness and
cross-feature system correctness. A 100/100 candidate result is no-gap evidence,
not proof that a task is invalid.

## What To Review

Review these files first:

- `AGENTS.md`: repo-wide construction, priority, and leakage-prevention rules.
- `INDEX.md`: task index and mechanical checks.
- `task/xitkit-realrepo-001/prd.md`: source-grounded model-visible requirements.
- `task/xitkit-realrepo-001/rubric.json`: source-grounded unit/system
  evaluation cases with no-gap-observed initial validation.
- `task/xitkit-realrepo-001/doc/source_repo.md`: source-grounding evidence.
- `task/xitkit-realrepo-001/doc/requirement_map.md`: traceability and
  source-grounding map.
- `task/marmite-realrepo-001/doc/source_repo.md`: active source-grounding notes
  for the next task.
- `task/marmite-realrepo-001/prd.md`: current Marmite model-visible draft.
- `task/marmite-realrepo-001/doc/requirement_map.md`: Marmite public
  requirements and planned unit/system coverage.

## Review Questions

1. Does each `prd.md` describe only public, model-visible behavior?
2. Can every `rubric.json` case be naturally inferred from the matching PRD?
3. Are unit cases and system cases meaningfully separated?
4. Do system cases combine heterogeneous features and derived views?
5. Does each rubric avoid private implementation details?
6. Do all `requirement_refs` map back to `requirement_map.md`?
7. Is there any answer leakage, reference implementation, scorer, candidate
   output, or score report committed to `main`?
8. Does xitkit's no-gap-observed validation status stay clearly separated from
   any `core_strong` or confirmed benchmark claim?

## Non-Goals

- Do not evaluate a generated implementation in this repository.
- Do not require tasks to reproduce full original projects.
- Do not require private implementation structures unless the PRD explicitly
  exposes them as public behavior.

## Expected Review Output

Return findings ordered by severity. Each finding should include file path and
line number, the concrete issue, why it affects correctness/fairness/leakage
risk, and a specific recommended change. If there are no blocking issues, state
that clearly and mention residual risks.
