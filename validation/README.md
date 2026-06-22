# Validation Evidence Branch

This branch is separate from `main`. It may contain reference implementations,
scorers, candidate outputs, and score reports for validation evidence.

Do not merge these assets into the clean handoff branch unless the repository is
explicitly being converted into a Bmk-dev-style validated/core package.

## Assets

- `validation/reference/kvmini.py`: reference implementation.
- `validation/score.py`: scorer for `task/bitcask-realrepo-001/rubric.json`.
- `validation/candidates/`: code-agent candidate workspaces.
- `validation/reports/`: generated score reports and summaries.
