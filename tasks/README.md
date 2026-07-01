# Qualified Tasks

`tasks/` is reserved for completed SpecBench-style tasks that pass the full
pipeline.

A qualified task should contain the public spec and non-sensitive traceability
artifacts needed for review, such as:

```text
tasks/<task-id>/
  MANIFEST.json
  spec.md
  kept_nodeids.txt
  taxonomy.jsonl
  spec_test_map.md
  reference_score.json
```

Do not place candidate attempts, hidden source checkouts, raw score reports, or
private oracle fixtures here unless the task is intentionally being published as
an internal benchmark package.
