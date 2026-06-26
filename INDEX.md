# Repository Index For AI Review

Purpose: this repository is a benchmark task handoff package, not an
implementation repository.

## Entry Points

- `README.md`: repository purpose, task list, and deliverable boundary.
- `PROJECT_CONTEXT.md`: project background, current task status, and roadmap.
- `AGENTS.md`: construction rules, task priority, correctness gates, leakage
  prevention, and review workflow.

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
- Abstracted task direction: markdown/frontmatter static-site generation with
  taxonomy pages, pagination, feeds, search index, URL manifest, and
  wikilink/backlink consistency.
- Files:
  - `task/marmite-realrepo-001/prd.md`
  - `task/marmite-realrepo-001/rubric.json`
  - `task/marmite-realrepo-001/doc/source_repo.md`
  - `task/marmite-realrepo-001/doc/requirement_map.md`
- Status: hardened reference-satisfiable/no-positive-gap-observed evidence
  exists on `validation/marmite-hardened`. The hardened rubric has 34 cases
  (19 unit / 15 system). Reference passed 19/19 unit and 15/15 system;
  `codex_agent_001` also passed all cases; `codex_agent_002` and
  `codex_agent_003` passed 17/19 unit and 14/15 system. Their failures were
  local filename metadata / stream parsing issues, not positive unit/system gap
  evidence. Do not claim `core_strong`.

### `jupytext-realrepo-001`

- Source project: `mwouts/jupytext`
- Abstracted task direction: paired notebook conversion and synchronization
  across `.ipynb` and `py:percent` scripts, with deterministic version markers,
  pairing config, output preservation, and status reports.
- Files:
  - `task/jupytext-realrepo-001/prd.md`
  - `task/jupytext-realrepo-001/rubric.json`
  - `task/jupytext-realrepo-001/doc/source_repo.md`
  - `task/jupytext-realrepo-001/doc/requirement_map.md`
- Status: source-grounded handoff draft. The rubric has 34 cases
  (20 unit / 14 system). Validation has not started; do not claim
  `core_strong`, `confirmed benchmark`, or `gap-producing`.

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
python3 -m json.tool task/marmite-realrepo-001/rubric.json >/dev/null
python3 -m json.tool task/jupytext-realrepo-001/rubric.json >/dev/null
git ls-files | rg '(^|/)(_reference|score_reports?|runs|candidate|.*score\.py|evaluator|answer|expected[-_ ]output)'
python3 - <<'PY'
import json
from pathlib import Path

bad = {"solution", "reference", "implementation", "test_code", "code", "answer"}
for rubric_path in [
    Path("task/bitcask-realrepo-001/rubric.json"),
    Path("task/xitkit-realrepo-001/rubric.json"),
    Path("task/marmite-realrepo-001/rubric.json"),
    Path("task/jupytext-realrepo-001/rubric.json"),
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
task/bitcask-realrepo-001/prd.md
task/bitcask-realrepo-001/rubric.json
task/bitcask-realrepo-001/doc/source_repo.md
task/bitcask-realrepo-001/doc/requirement_map.md
task/xitkit-realrepo-001/prd.md
task/xitkit-realrepo-001/rubric.json
task/xitkit-realrepo-001/doc/source_repo.md
task/xitkit-realrepo-001/doc/requirement_map.md
task/marmite-realrepo-001/prd.md
task/marmite-realrepo-001/rubric.json
task/marmite-realrepo-001/doc/source_repo.md
task/marmite-realrepo-001/doc/requirement_map.md
task/jupytext-realrepo-001/prd.md
task/jupytext-realrepo-001/rubric.json
task/jupytext-realrepo-001/doc/source_repo.md
task/jupytext-realrepo-001/doc/requirement_map.md
```
