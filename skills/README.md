# E2E Pipeline Skills

This directory versions the local copy of the Bmk-dev SpecBench pipeline skills.

Runtime copies are installed under:

```text
/Users/nixer/.codex/skills/e2e-00-task-synthesizer/
/Users/nixer/.codex/skills/e2e-01-candidate-selector/
/Users/nixer/.codex/skills/e2e-02-spec-writer/
/Users/nixer/.codex/skills/e2e-03-test-filter/
/Users/nixer/.codex/skills/e2e-04-task-judge/
```

Use order:

1. `e2e-00-task-synthesizer`: orchestrates the whole pipeline.
2. `e2e-01-candidate-selector`: screens repositories and writes
   `wip/<task>/filter_notes.md`.
3. `e2e-02-spec-writer`: writes the candidate-visible behavioral spec.
4. `e2e-03-test-filter`: filters upstream tests into the oracle taxonomy.
5. `e2e-04-task-judge`: validates runs and decides whether a task qualifies.

When changing a skill, update this repository copy first, then sync it into
`/Users/nixer/.codex/skills/` before using it in a fresh Codex session:

```bash
scripts/sync_e2e_skills.sh
```
