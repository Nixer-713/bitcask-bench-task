# Validation Summary

Branch: `validation/evidence`

This branch contains validation-only assets. It intentionally diverges from the
clean `main` handoff branch by including a reference implementation, scorer,
candidate outputs, and score reports.

## Commands

```console
python3 -m py_compile validation/score.py validation/reference/kvmini.py
python3 validation/score.py --solution validation/reference/kvmini.py \
  --label reference --out validation/reports/score_report_reference.json
python3 validation/score.py --solution validation/candidates/codex_agent_001/kvmini.py \
  --label codex_agent_001 --out validation/reports/score_report_codex_agent_001.json
python3 validation/score.py --solution validation/candidates/codex_agent_002/kvmini.py \
  --label codex_agent_002 --out validation/reports/score_report_codex_agent_002.json
python3 validation/score.py --solution validation/candidates/gpt54mini_agent_001/kvmini.py \
  --label gpt54mini_agent_001 --out validation/reports/score_report_gpt54mini_agent_001.json
```

## Results

| Solution | Unit | System | Gap | Failed cases | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| reference | 100.00% | 100.00% | 0.00pp | 0 | Reference is satisfiable. |
| codex_agent_001 | 100.00% | 100.00% | 0.00pp | 0 | No gap observed. |
| codex_agent_002 | 100.00% | 100.00% | 0.00pp | 0 | No gap observed. |
| gpt54mini_agent_001 | 100.00% | 100.00% | 0.00pp | 0 | No gap observed. |

## Status Decision

The task is validated as executable and reference-satisfiable, but it is not
validated as core-strong. Three non-reference code-agent runs achieved 100%
unit and 100% system scores, so the current rubric does not produce the intended
unit/system degradation signal.

Do not mark this task as `core_strong` based on this evidence.

## Next Action

Strengthen system cases only with behavior naturally inferable from `prd.md`.
Do not add implementation-detail checks or private file-format assumptions.
