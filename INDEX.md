# Repository Index For AI Review

Purpose: this repository is a benchmark task handoff package, not an
implementation repository.

## Entry Points

- `README.md`: repository purpose, task list, and deliverable boundary.
- `PROJECT_CONTEXT.md`: project background, current task status, and roadmap.
- `AGENTS.md`: construction rules, task priority, correctness gates, leakage
  prevention, and review workflow.
- `doc/e2e_full_project_pipeline.md`: v2 source-selection-to-eval workflow for
  full-project tasks that use public candidate packets and private filtered
  test oracles.
- `public_candidate_packet/README.md`: candidate-visible E2E packet boundary.
- `authoring_private_oracle/README.md`: private oracle/evaluation boundary.

## Task Index

### `bitcask-realrepo-001`

- Source project: `SarthakMakhija/bitcask`
- Abstracted task: mini-bitcask command-line key/value store.
- Files:
  - `task/bitcask-realrepo-001/prd.md`
  - `task/bitcask-realrepo-001/rubric.json`
  - `task/bitcask-realrepo-001/doc/source_repo.md`
  - `task/bitcask-realrepo-001/doc/requirement_map.md`
- Status: candidate/no-gap-observed evidence exists on validation branch;
  do not claim `core_strong` from current evidence.

### `xitkit-realrepo-001`

- Source project: `hoechstleistungshaartrockner/xitkit`
- Abstracted task: local `.xit` task-file CLI.
- Files:
  - `task/xitkit-realrepo-001/prd.md`
  - `task/xitkit-realrepo-001/rubric.json`
  - `task/xitkit-realrepo-001/doc/source_repo.md`
  - `task/xitkit-realrepo-001/doc/requirement_map.md`
- Status: source-grounded candidate. Initial validation on `validation/xitkit`
  showed reference 100/100 and three code-agent candidates 100/100, so this is
  no-gap-observed evidence and must not be claimed as `core_strong`.

### `marmite-realrepo-001`

- Source project: `rochacbruno/marmite`
- Active direction: reset for redesign from source-grounded public behavior,
  state/artifact flow, and system invariants.
- Files:
  - `task/marmite-realrepo-001/doc/source_repo.md`
  - `task/marmite-realrepo-001/doc/rewrite_note.md`
- Archived packet:
  - `archive/no-gap-observed/marmite-realrepo-001/prd.md`
  - `archive/no-gap-observed/marmite-realrepo-001/rubric.json`
  - `archive/no-gap-observed/marmite-realrepo-001/doc/source_repo.md`
  - `archive/no-gap-observed/marmite-realrepo-001/doc/requirement_map.md`
- Status: prior hardened packet is reference-satisfiable/no-positive-gap
  evidence from `validation/marmite-hardened`; do not claim `core_strong`.

### `jupytext-realrepo-001`

- Source project: `mwouts/jupytext`
- Active direction: reset for redesign from source-grounded paired-notebook
  behavior, conflict/status/check flows, output preservation, and system
  invariants.
- Files:
  - `task/jupytext-realrepo-001/doc/source_repo.md`
  - `task/jupytext-realrepo-001/doc/rewrite_note.md`
- Archived packet:
  - `archive/no-gap-observed/jupytext-realrepo-001/prd.md`
  - `archive/no-gap-observed/jupytext-realrepo-001/rubric.json`
  - `archive/no-gap-observed/jupytext-realrepo-001/doc/source_repo.md`
  - `archive/no-gap-observed/jupytext-realrepo-001/doc/requirement_map.md`
- Status: prior packet is reference-satisfiable/no-gap-observed evidence from
  `validation/jupytext`; reference and three candidates passed all 34 cases.
  Do not claim `core_strong`, `confirmed benchmark`, or `gap-producing`.

### `copier-realrepo-001`

- Source project: `copier-org/copier`
- Checked source revision: `454ec4244132bce478e60c4707ee418312ca8922`
- Abstracted task: local project-template generator/updater CLI,
  `minicopier.py`.
- Files:
  - `task/copier-realrepo-001/prd.md`
  - `task/copier-realrepo-001/rubric.json`
  - `task/copier-realrepo-001/doc/source_repo.md`
  - `task/copier-realrepo-001/doc/boundary_decisions.md`
  - `task/copier-realrepo-001/doc/requirement_map.md`
  - `task/copier-realrepo-001/doc/review_structure.md`
  - `task/copier-realrepo-001/doc/review_fairness.md`
- Status: draft handoff created. Validation has not been merged into `main`;
  do not claim `core_strong`, `confirmed benchmark`, or `gap-producing`.

## Archive Index

Archived packets under `archive/no-gap-observed/` are design history and
validation evidence, not active handoff targets. They may be reviewed to
understand why prior task abstractions did not produce positive unit/system
gap, but new Marmite/Jupytext PRDs and rubrics should be drafted fresh.

## Review Checklist

- PRD contains user-visible requirements only.
- Rubric cases are inferable from PRD, not hidden assumptions.
- Unit cases test local capabilities.
- System cases combine heterogeneous capabilities and derived views.
- Tests observe only public behavior: stdout, stderr, exit code, and
  PRD-defined files/state.
- No committed reference implementation, scorer, score report, or candidate
  output in `main`.
- No rubric keys such as `solution`, `reference`, `implementation`, or
  `test_code`.
- `requirement_refs` in rubric map back to `doc/requirement_map.md`.
- Review history should include two independent checks before handoff:
  structure validation and PRD/rubric/source-grounding fairness review.

## Suggested AI Review Prompt

Review this repository as a benchmark task handoff. Verify that each `prd.md`
defines only public model-visible requirements, each `rubric.json` evaluates
only behaviors inferable from that PRD, and no implementation, scorer,
candidate output, or answer leakage is committed. Cite concrete file paths and
line numbers for every finding. Prioritize fairness issues, hidden assumptions,
implementation-detail tests, missing requirement mappings, malformed rubric
cases, weak unit/system separation, and weak source grounding.

## Mechanical Checks

```console
python3 -m json.tool task/bitcask-realrepo-001/rubric.json >/dev/null
python3 -m json.tool task/xitkit-realrepo-001/rubric.json >/dev/null
python3 -m json.tool archive/no-gap-observed/marmite-realrepo-001/rubric.json >/dev/null
python3 -m json.tool archive/no-gap-observed/jupytext-realrepo-001/rubric.json >/dev/null
python3 -m json.tool task/copier-realrepo-001/rubric.json >/dev/null
git ls-files | rg '(^|/)(_reference|reference_solution|filtered_tests|oracle/|score_reports?|runs/|validation/|candidates?/|.*score\.py|evaluator|answer|expected[-_ ]output|original_source)'
git ls-files | rg '(^|/)authoring_private_oracle/.+/(oracle|docker|validation|reference_solution|original_source_checkout|model_reports|score_reports|candidates)/'
python3 - <<'PY'
import json
from pathlib import Path

bad = {"solution", "reference", "implementation", "test_code", "code", "answer"}
for rubric_path in [
    Path("task/bitcask-realrepo-001/rubric.json"),
    Path("task/xitkit-realrepo-001/rubric.json"),
    Path("archive/no-gap-observed/marmite-realrepo-001/rubric.json"),
    Path("archive/no-gap-observed/jupytext-realrepo-001/rubric.json"),
    Path("task/copier-realrepo-001/rubric.json"),
]:
    rubric = json.loads(rubric_path.read_text())
    ids = [case.get("id") for case in rubric]
    errors = []
    if len(ids) != len(set(ids)):
        errors.append("duplicate ids")
    if any(case.get("layer") not in {"unit", "system"} for case in rubric):
        errors.append("invalid layer")
    if any(not case.get("requirement_refs") for case in rubric):
        errors.append("missing requirement_refs")
    if any(case.get("layer") == "system" and not case.get("system_dimension") for case in rubric):
        errors.append("system case missing system_dimension")
    forbidden = sorted({k for case in rubric for k in case if k in bad})
    if forbidden:
        errors.append(f"forbidden rubric fields: {forbidden}")
    print(rubric_path, "cases", len(rubric), "errors", errors)
PY
```

## Expected File Tree

```text
README.md
AGENTS.md
INDEX.md
PROJECT_CONTEXT.md
doc/e2e_full_project_pipeline.md
public_candidate_packet/README.md
authoring_private_oracle/README.md
task/bitcask-realrepo-001/prd.md
task/bitcask-realrepo-001/rubric.json
task/bitcask-realrepo-001/doc/source_repo.md
task/bitcask-realrepo-001/doc/requirement_map.md
task/xitkit-realrepo-001/prd.md
task/xitkit-realrepo-001/rubric.json
task/xitkit-realrepo-001/doc/source_repo.md
task/xitkit-realrepo-001/doc/requirement_map.md
task/marmite-realrepo-001/doc/source_repo.md
task/marmite-realrepo-001/doc/rewrite_note.md
task/jupytext-realrepo-001/doc/source_repo.md
task/jupytext-realrepo-001/doc/rewrite_note.md
archive/no-gap-observed/marmite-realrepo-001/prd.md
archive/no-gap-observed/marmite-realrepo-001/rubric.json
archive/no-gap-observed/marmite-realrepo-001/doc/source_repo.md
archive/no-gap-observed/marmite-realrepo-001/doc/requirement_map.md
archive/no-gap-observed/jupytext-realrepo-001/prd.md
archive/no-gap-observed/jupytext-realrepo-001/rubric.json
archive/no-gap-observed/jupytext-realrepo-001/doc/source_repo.md
archive/no-gap-observed/jupytext-realrepo-001/doc/requirement_map.md
task/copier-realrepo-001/prd.md
task/copier-realrepo-001/rubric.json
task/copier-realrepo-001/doc/source_repo.md
task/copier-realrepo-001/doc/boundary_decisions.md
task/copier-realrepo-001/doc/requirement_map.md
task/copier-realrepo-001/doc/review_structure.md
task/copier-realrepo-001/doc/review_fairness.md
```
