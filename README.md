# Unit/System Gap Benchmark Task Draft

This repository contains one draft benchmark task:

- `task/bitcask-realrepo-001`

The task is derived from a real Bitcask-style key/value store and asks a
candidate model to implement a compact Python CLI, `kvmini.py`, from the public
product packet in `prd.md`.

## Current Status

The packet is structurally aligned with the Bmk-dev task layout:

- `prd.md`
- `rubric.json`
- `doc/source_repo.md`
- `doc/requirement_map.md`
- `doc/score_reports/`

The reference solution passes the full rubric:

- unit: 100.00%
- system: 100.00%
- gap: 0.00pp

Two candidate model runs also reached 100.00% unit and 100.00% system. That
means the task is reproducible and fair after the latest cleanup, but it is not
yet confirmed as a core-strong gap task. The next pass should add harder,
fair CLI-observable system workflows that expose model degradation without
checking private file formats or implementation details.

## Reproduce Scores

```console
python3 task/bitcask-realrepo-001/_reference/score.py \
  --solution task/bitcask-realrepo-001/_reference/kvmini.py \
  --rubric task/bitcask-realrepo-001/rubric.json \
  --label reference \
  --out task/bitcask-realrepo-001/doc/score_reports/score_report_reference_unit_system_v1.json
```

Candidate solutions should be generated from `task/bitcask-realrepo-001/prd.md`
only, then scored with the same harness.
