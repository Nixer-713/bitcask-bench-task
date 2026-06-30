# Fairness Review: doit-realrepo-001

Status: `PASS`

This review checks that the public packet, source evidence, requirement map,
and selected oracle remain aligned. It is not a claim that the task is
`core_strong`; candidate validation did not show a positive unit/integration
gap.

## Candidate-Facing Fairness

| Check | Verdict | Evidence |
| --- | --- | --- |
| PRD excludes hidden test names and case IDs | PASS | Public packet has no pytest names, oracle paths, scoring manifest, model reports, or reference hints. |
| PRD describes senior-engineer public behavior | PASS | Public packet defines package shape, CLI/API, task file grammar, safe action DSL, state, reports, errors, invariants, and non-goals. |
| Deterministic adaptations are public | PASS | Safe action DSL, JSON state, JSON reports, restricted `dodo.py`, content signatures, and excluded dynamic features are stated in PRD/API and traced in the requirement map. |
| Candidates do not receive source implementation | PASS | Public packet contains only public docs; source evidence and oracle are private. |

## Source Grounding

| Requirement area | Source basis | Adaptation status |
| --- | --- | --- |
| CLI task runner behavior | Source docs and CLI/source evidence rows in `source_evidence_matrix.md` | deterministic subset |
| `dodo.py` task creator model | Public source docs/tests/source evidence | deterministic subset |
| actions/dependencies/targets | Source task model evidence | deterministic safe DSL |
| state and dependency persistence | Source dependency backend behavior | public JSON state translation |
| list/info/clean/forget/dumpdb | Public command evidence | deterministic subset / JSON translation |
| excluded features | Source capabilities outside v1 scope | explicitly excluded |

## Selected Oracle Fairness

| Layer | Count | Verdict |
| --- | ---: | --- |
| Contract | 4 | Public package/CLI behavior only. |
| Unit | 15 | Local public features: parser, config, safe actions, state, reports, and errors. |
| Integration | 8 | Cross-command workflows over task file, state, targets, reports, clean/forget, config, and failure behavior. |

Every selected test appears in `doc/requirement_map.md` under Selected Oracle
Coverage. Integration tests include system dimensions and cross multiple public
capabilities.

## Review Fixes Applied

- Removed an oracle assertion that required a file written before a later
  failing action to remain. The PRD only permits that behavior, so the hidden
  oracle now checks only no later action, no dependent output, and no false
  success state.
- Removed exact stderr-wording assertions where the public contract only
  requires useful non-empty stderr.
- Added a contract test for `dumpdb --file` rejection after the reference was
  found too permissive.
- Removed local temporary checkout paths from source-grounding docs.

## Verdict

The oracle is fair relative to the public packet and source-grounded
adaptations. Current candidate evidence is `no positive gap observed`, not
`core_strong`.
