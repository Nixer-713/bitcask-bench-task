# Candidate Runs

`candidate-runs/` stores local cleanroom model runs.

These outputs are not part of public candidate packets. Keep run directories
ignored by Git unless a sanitized report is explicitly requested.

Expected shape:

```text
candidate-runs/<model>-<task>-<date>-<run>/
  task_prompt.txt
  output/
  score_report.md
  score_result.json
```
