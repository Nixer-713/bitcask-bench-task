# Task Structure Review: doit-realrepo-001

Review type: read-only subagent structure/fairness review.

Result: `PASS`

## Scope

- `public_candidate_packet/doit-realrepo-001/`
- `authoring_private_oracle/doit-realrepo-001/scoring_manifest.json`
- `authoring_private_oracle/doit-realrepo-001/doc/*.md`
- `authoring_private_oracle/doit-realrepo-001/oracle/`
- `authoring_private_oracle/doit-realrepo-001/docker/run_eval.sh`
- `authoring_private_oracle/doit-realrepo-001/docker/Dockerfile`
- validation summaries and reports

## Findings

- The public packet is an E2E full-project task, not a function-level or tiny
  script task. It requires an installable Python package and defines CLI,
  config, task grammar, action DSL, state, commands, errors, and invariants.
- Public/private separation is clean. The public candidate packet contains only
  `prd.md`, `public_api_contract.md`, and `packaging_contract.md`.
- Source grounding and deterministic adaptations are traceable through
  `source_repo.md`, `source_evidence_matrix.md`, and `requirement_map.md`.
- The filtered oracle is derivable from the public packet and avoids private
  implementation checks, source internals, plugin APIs, exact reporter
  formatting, shell/Python action parity, backend matrices, `strace`, and
  excluded commands.
- Contract/unit/integration grouping is reasonable. Integration tests cross
  task loading, state, generated files, JSON reports, clean/forget mutation,
  config paths, and failure behavior.
- `run_eval.sh` separates install, contract, unit, and integration stages,
  preserves stdout/stderr/JUnit artifacts, writes `summary.json`, and then
  decides the final exit code.
- Current validation evidence does not support `core_strong` because candidate
  runs have no positive unit/integration gap.

## Residual Risks

- The private tree includes reference/oracle/model reports. This is acceptable
  for the internal validation branch but must not be shipped as a candidate-only
  public handoff.
- More candidate evidence can characterize difficulty, but stronger claims
  require repeated positive unit/integration gap or a redesigned/expanded
  integration oracle.
