# Validation Summary

Branch: `validation/evidence`

This branch contains validation-only assets. It intentionally diverges from the
clean `main` handoff branch by including a reference implementation, scorer,
candidate outputs, and score reports.

## Commands

```console
python3 -m json.tool task/bitcask-realrepo-001/rubric.json >/dev/null
python3 -m py_compile validation/score.py validation/reference/kvmini.py \
  validation/candidates/codex_agent_001/kvmini.py \
  validation/candidates/codex_agent_002/kvmini.py \
  validation/candidates/gpt54mini_agent_001/kvmini.py
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

Rubric size after lifecycle hardening: 35 total cases, 17 unit cases, and 18
system cases.

| Solution | Unit | System | Gap | Failed cases | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| reference | 100.00% | 100.00% | 0.00pp | 0 | Reference is satisfiable. |
| codex_agent_001 | 100.00% | 100.00% | 0.00pp | 0 | No gap observed. |
| codex_agent_002 | 100.00% | 100.00% | 0.00pp | 0 | No gap observed. |
| gpt54mini_agent_001 | 100.00% | 100.00% | 0.00pp | 0 | No gap observed. |

## Status Decision

The task is validated as executable and reference-satisfiable, but it is not
validated as core-strong. Three non-reference code-agent runs achieved 100%
unit and 100% system scores after adding source-derived Bitcask lifecycle system
cases, so this evidence still does not show a unit/system degradation signal.

Do not mark this task as `core_strong` based on this evidence.

## Hardening Applied

Added `KVS013` through `KVS018` to cover long mutation replay, tombstone
survival through compact/reload, rollover replay order, repeated compaction
idempotence, error atomicity after compact, and read/metadata agreement after a
mixed lifecycle. These cases check only public CLI behavior, exit status, JSON
outputs, and PRD-defined `stats` fields.

## Next Action

Keep the task status as candidate. Future hardening should remain source-derived
and must not add implementation-detail checks or private file-format assumptions.
