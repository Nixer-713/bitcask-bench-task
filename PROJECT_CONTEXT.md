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

`task/marmite-realrepo-001` is reset for redesign from `rochacbruno/marmite`.
The prior handoff packet defined a static-site generator task where one
markdown content graph and configuration produced multiple public outputs:
rendered pages, taxonomies, pagination, feeds, search index, URL manifest, and
wikilink/backlink views.

Prior validation evidence on `validation/marmite` was reference-satisfiable but
no-positive-gap-observed. After that, a small source-grounded hardening pass
added draft-aware link exclusion, archive-year taxonomy, and a read-only URL
manifest preview command.

Hardened validation evidence exists on `validation/marmite-hardened`. The
hardened rubric had 34 cases: 19 unit and 15 system. The reference passed 19/19
unit and 15/15 system cases. `codex_agent_001` also passed 19/19 unit and 15/15
system. `codex_agent_002` and `codex_agent_003` each passed 17/19 unit and
14/15 system; their failures were local filename metadata / stream parsing
issues, not positive unit/system gap evidence.

The prior PRD/rubric/requirement map is archived under
`archive/no-gap-observed/marmite-realrepo-001/`. The active task directory keeps
`doc/source_repo.md` and `doc/rewrite_note.md` only. Treat Marmite as archived
reference-satisfiable/no-positive-gap-observed evidence until a fresh redesign
produces a new PRD/rubric. Do not claim `core_strong`, `confirmed benchmark`,
or `gap-producing` from current evidence.

### Jupytext

`task/jupytext-realrepo-001` is reset for redesign from `mwouts/jupytext`. The
prior handoff abstracted paired notebook behavior into a deterministic local CLI
where one notebook model stayed consistent across `.ipynb`, `py:percent` text,
pairing metadata, version-based sync, output preservation, and status reports.

Validation evidence exists on `validation/jupytext`: the reference and three
independent candidates all passed 20/20 unit and 14/14 system cases. This is
reference-satisfiable/no-gap-observed evidence, not positive unit/system gap
evidence.

The prior PRD/rubric/requirement map is archived under
`archive/no-gap-observed/jupytext-realrepo-001/`. The active task directory
keeps `doc/source_repo.md` and `doc/rewrite_note.md` only. Treat Jupytext as
archived reference-satisfiable/no-gap-observed evidence until a fresh redesign
produces a new PRD/rubric. Do not claim `core_strong`, `confirmed benchmark`,
or `gap-producing` from current evidence.

### Copier

`task/copier-realrepo-001` is a draft handoff derived from `copier-org/copier`
at commit `454ec4244132bce478e60c4707ee418312ca8922`. It abstracts Copier into
a compact local CLI, `minicopier.py`, covering copy, recopy, update,
check-update, answers files, local Git refs/tags, exclude/skip, pretend mode,
safe tasks/migrations, subdirectory rendering, update conflicts, and
atomicity.

The task is source-grounded and has PRD, requirement map, rubric, boundary
decisions, and review docs on `main`. Validation evidence has not been accepted
into `main`. Treat Copier as draft/pending validation until a validation branch
shows reference 100/100 and candidate results. Do not claim `core_strong`,
`confirmed benchmark`, or `gap-producing`.

### Roadmap

The active roadmap is fixed unless the user changes it explicitly:

1. Keep Bitcask as candidate/no-gap-observed evidence.
2. Keep xitkit as source-grounded candidate/no-gap-observed evidence from
   initial validation.
3. Keep archived Marmite as hardened reference-satisfiable/no-positive-gap
   evidence.
4. Keep archived Jupytext as reference-satisfiable/no-gap-observed evidence.
5. Redesign Marmite and Jupytext from public behavior inventory, capability
   modules, state/artifact models, and system-testable cross-feature workflows
   before drafting new PRDs or rubrics.
6. Validate `copier-realrepo-001` on a validation branch. Keep reference,
   scorer, candidate outputs, reports, and summaries out of `main`.

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
- `task/marmite-realrepo-001/doc/source_repo.md`: source-grounding notes for
  the Marmite redesign.
- `task/marmite-realrepo-001/doc/rewrite_note.md`: Marmite reset boundary.
- `task/jupytext-realrepo-001/doc/source_repo.md`: Jupytext source-grounding
  evidence.
- `task/jupytext-realrepo-001/doc/rewrite_note.md`: Jupytext reset boundary.
- `task/copier-realrepo-001/prd.md`: Copier model-visible requirements.
- `task/copier-realrepo-001/rubric.json`: Copier draft unit/system cases.
- `task/copier-realrepo-001/doc/source_repo.md`: Copier source evidence and
  Source Evidence Matrix.
- `task/copier-realrepo-001/doc/requirement_map.md`: Copier traceability map.
- `archive/no-gap-observed/marmite-realrepo-001/`: archived Marmite handoff.
- `archive/no-gap-observed/jupytext-realrepo-001/`: archived Jupytext handoff.

## Review Questions

1. Does each `prd.md` describe only public, model-visible behavior?
2. Can every `rubric.json` case be naturally inferred from the matching PRD?
3. Are unit cases and system cases meaningfully separated?
4. Do system cases combine heterogeneous features and derived views?
5. Does each rubric avoid private implementation details?
6. Do all `requirement_refs` map back to `requirement_map.md`?
7. Is there any answer leakage, reference implementation, scorer, candidate
   output, or score report committed to `main`?
8. Do xitkit, Marmite, and Jupytext statuses stay clearly separated from any
   `core_strong` or confirmed benchmark claim?

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
