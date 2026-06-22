# Repository Index For AI Review

Purpose: this repository is a handoff package for one benchmark task, not an
implementation repository.

## Entry Points

- `README.md`: high-level repository purpose and deliverable boundary.
- `AGENTS.md`: construction rules, correctness gates, leakage prevention, and required review workflow.
- `task/bitcask-realrepo-001/prd.md`: public requirement document shown to model/code agents.
- `task/bitcask-realrepo-001/rubric.json`: hidden unit/system evaluation cases.
- `task/bitcask-realrepo-001/doc/source_repo.md`: source-project rationale.
- `task/bitcask-realrepo-001/doc/requirement_map.md`: traceability from PRD requirements to rubric cases.

## Task Summary

- Source project: `SarthakMakhija/bitcask`
- Abstracted task: mini-bitcask command-line key/value store.
- Core capability target: system-level correctness under append-only writes,
  tombstone deletion, compaction, metadata consistency, durability reload, and
  error atomicity.
- Intended signal: `unit_score - system_score` gap, where local feature tests
  pass more often than cross-feature system workflows.

## Review Checklist

- PRD contains user-visible requirements only.
- Rubric cases are inferable from PRD, not from hidden assumptions.
- Unit cases test local capabilities.
- System cases combine at least two capabilities and check global invariants.
- Tests observe only public behavior: stdout, stderr, exit code, and PRD-defined state.
- No committed reference implementation, scorer, score report, or candidate output.
- No rubric keys such as `solution`, `reference`, `implementation`, or `test_code`.
- `requirement_refs` in rubric map back to `doc/requirement_map.md`.
- Review history should show two independent checks before handoff:
  structure validation and PRD/rubric fairness review with file evidence.

## Suggested AI Review Prompt

Review this repository as a benchmark task handoff. Verify that `prd.md` defines
only public model-visible requirements, `rubric.json` evaluates only behaviors
inferable from that PRD, and no implementation, scorer, candidate output, or
answer leakage is committed. Cite concrete file paths and line numbers for every
finding. Prioritize fairness issues, hidden assumptions, implementation-detail
tests, missing requirement mappings, malformed rubric cases, and weak
unit/system separation. Also verify that the handoff used two independent
checks: benchmark-structure validation and PRD/rubric fairness review.

## Mechanical Checks

```console
git ls-files
python3 -m json.tool task/bitcask-realrepo-001/rubric.json >/dev/null
git ls-files | rg '(^|/)(_reference|score_reports?|runs|candidate|.*score\.py|evaluator|answer|expected[-_ ]output)'
python3 - <<'PY'
import json
from pathlib import Path
rubric = json.loads(Path("task/bitcask-realrepo-001/rubric.json").read_text())
ids = [case.get("id") for case in rubric]
bad = {"solution", "reference", "implementation", "test_code", "code", "answer"}
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
print("cases", len(rubric))
print("errors", errors)
PY
```

Expected review outcome: either no blocking issues, or a list of specific
PRD/rubric inconsistencies with file evidence.

## Expected File Tree

```text
README.md
AGENTS.md
INDEX.md
task/bitcask-realrepo-001/prd.md
task/bitcask-realrepo-001/rubric.json
task/bitcask-realrepo-001/doc/source_repo.md
task/bitcask-realrepo-001/doc/requirement_map.md
```
