# E2E Full-Project Benchmark Pipeline

This is the default process for new benchmark tasks after the v2 skill update.
It uses `benchmark-task-builder` in `e2e_full_project_task` mode unless a source
repository fails the E2E selection gate.

## 1. Mode And Repository Selection

Default mode:

```text
e2e_full_project_task
```

Use this mode when candidates should build a complete installable Python
package from a senior-engineer PRD. Candidates receive only the public packet,
not the source repository, upstream tests, scorer, original implementation, or
validation reports.

Accept a repository only when it has:

- a pure or mostly Python package shape;
- clear public README/docs/API/CLI behavior;
- executable pytest/unittest tests;
- separable local-feature and integration tests;
- deterministic local evaluation without accounts, GUI, live network, or
  heavyweight services;
- cross-module state or artifact flow, such as config, generated files,
  indexes, reports, update/sync state, rollback, or status views.

Reject or defer repositories whose difficulty is mostly private internals, whose
behavior collapses into one simple map/list, or whose tests cannot be made
candidate-packet-inferable.

## 2. Source Grounding

Before drafting a PRD or selecting tests, create private authoring docs:

```text
authoring_private_oracle/<task-name>/doc/source_repo.md
authoring_private_oracle/<task-name>/doc/source_evidence_matrix.md
authoring_private_oracle/<task-name>/doc/behavior_inventory.md
authoring_private_oracle/<task-name>/doc/artifact_shape.md
```

`source_repo.md` must record the canonical repository, checked commit SHA, and
repository-relative evidence paths only.

The evidence matrix is mandatory:

```text
Behavior ID | Public behavior | Source evidence path | Evidence type | Adaptation type | PRD location | Tests
```

Allowed adaptation types:

- `direct_copy`
- `deterministic_subset`
- `interface_translation`
- `repo_patch_scope`
- `excluded`

Do not use "inspired by" as evidence. PRD behavior without a matrix row is not
allowed.

## 3. Capability And State Decomposition

Decompose by public capability, not source functions:

```text
Capability | Public input | Public output | Persistent state/artifacts | Downstream effects | Evidence
```

Group capabilities into:

- Input layer: CLI, API, config, source files, JSON/YAML/TOML, existing state.
- Core state layer: parsed model, file tree, index, manifest, version/conflict
  state, package state, database state.
- Derived view layer: reports, status, generated files, search, graph,
  summaries, validation output.
- Mutation/recovery layer: create, update, sync, migrate, rollback, conflict
  resolution, no-partial-write behavior.

Integration cases should cross the core state, derived view, and
mutation/recovery layers.

## 4. Boundary Decisions And Public Packet

Before writing the PRD, classify every behavior:

```text
keep / simplify / translate interface / patch-scope / exclude
```

Valid deterministic adaptations include replacing mtimes with public version
markers, replacing human logs with JSON reports, narrowing many formats to one
representative format, and replacing background services with explicit commands.

Create the public candidate packet:

```text
public_candidate_packet/<task-name>/
  prd.md
  public_api_contract.md
  packaging_contract.md
  starter files if explicitly needed
```

The PRD must describe the project like a senior engineer's day-one assignment:
package shape, public API/CLI, config and artifact formats, feature behavior,
global invariants, error behavior, runtime constraints, and non-goals.

The PRD must not contain hidden test names, case IDs, expected outputs, scorer
logic, original source file paths to edit, private algorithms, or reference
implementation hints.

## 5. Oracle Construction

Inventory the source test suite before selecting the hidden oracle:

```text
authoring_private_oracle/<task-name>/doc/test_inventory.md
authoring_private_oracle/<task-name>/doc/test_derivability_review.md
authoring_private_oracle/<task-name>/doc/requirement_map.md
```

Each test entry must include path/name, layer, behavior asserted, PRD support,
source evidence, decision, and reason.

Layer labels:

- `contract`
- `unit`
- `integration`
- `regression`
- `excluded`

Keep only tests that are explicitly inferable from the public packet,
reasonably implicit for a senior engineer, or source-public regression behavior
that is documented in the PRD. Exclude private API, internal layout, private
algorithms, mtime/random/network/credential/GUI dependencies, and behavior
outside the declared task scope.

Gray-area tests must be marked `needs_prd_clarification`; then either clarify
the PRD and requirement map or exclude the test.

## 6. Environment And Harness

Create:

```text
authoring_private_oracle/<task-name>/doc/environment_contract.md
authoring_private_oracle/<task-name>/scoring_manifest.json
authoring_private_oracle/<task-name>/docker/run_eval.sh
```

The environment contract must state platform, base image, Python version,
`PYTHON_BIN`, dependency installation, network policy, writable paths, timeouts,
and reproducibility notes.

`run_eval.sh` must:

- install the candidate package;
- run contract, unit, and integration stages separately;
- preserve stdout, stderr, and JUnit/JSON artifacts for each stage;
- continue later stages when earlier test stages fail;
- write `summary.json` before choosing the final exit code;
- evaluate only `scoring_manifest.json` and selected oracle tests.

## 7. Review And Validation Gates

Run these reviews before candidate evaluation:

- Structure review: schema, IDs, layers, requirement refs, score groups,
  integration dimensions, forbidden fields, directory boundary.
- Fairness review: every PRD requirement is source-grounded or publicly adapted;
  every selected test is PRD-inferable.
- Oracle review: selected tests are stable, public, non-flaky, and free of
  implementation-detail assertions.
- Environment review: no network, credentials, local absolute paths, or hidden
  oracle/source visibility in candidate workspace.

Original implementation validation is mandatory. The checked source
implementation should pass contract, unit, and integration oracle tests at
100%. If not, classify each failure before running candidates and exclude or
normalize unresolved failures.

## 8. Candidate Evaluation And Interpretation

Run at least three independent code-agent candidates in isolated workspaces.
Each candidate receives only `public_candidate_packet/<task-name>/`.

For every run, record:

- install success;
- contract success;
- unit pass rate;
- integration pass rate;
- overall pass rate;
- integration gap pp;
- failed test IDs;
- qualitative failure category.

Claim levels:

- `oracle_validated`: original/reference passes the filtered oracle.
- `validated_candidate`: candidate batch completed.
- `positive_gap_observed`: at least two independent candidates show high unit
  pass rate with lower integration pass rate.
- `core_strong`: positive gap persists on core tests after fairness review and
  reruns.
- `no-gap-observed`: candidates pass everything or unit/integration are both
  high; do not add hidden assumptions to force failure.

## 9. Release Checklist

Before publishing a task packet:

```bash
git ls-files | rg '(^|/)(_reference|reference_solution|filtered_tests|oracle|score_reports?|runs|candidate|.*score\.py|evaluator|answer|expected[-_ ]output|original_source|validation)'
```

Interpret matches manually. Rule text may contain these words; deliverable
assets must not leak.

Public release may contain the candidate packet and non-sensitive summaries.
Filtered tests, scorer, reference/original checkout, candidate outputs, Docker
harness, validation reports, and score summaries must remain private unless the
branch is explicitly an internal validation branch.
