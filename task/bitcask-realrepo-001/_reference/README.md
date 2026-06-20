# Reference (private) — bitcask-realrepo-001

This folder holds the **hidden** artifacts for the task. In a real benchmark run
it would not be shipped to candidates. It is included here so the score report is
fully reproducible.

Contents:

- `kvmini.py` — the reference solution. Passes the whole rubric (100/100, 0pp gap).
- `build_rubric.py` — regenerates `../rubric.json` from a single source of truth.
- `score.py` — the scoring harness. Runs each rubric case in an isolated temp
  workspace, executes the commands as separate process invocations, enforces
  `expect_error`, applies the checks, and writes a report in the score-report schema.

## Run

```console
python3 build_rubric.py
python3 score.py --solution ./kvmini.py --rubric ../rubric.json \
    --label reference --out ../doc/score_reports/score_report_reference_unit_system_v1.json
```

## Score any candidate

```console
python3 score.py --solution /path/to/candidate/kvmini.py --rubric ../rubric.json \
    --label codex_subagent_001 \
    --out ../doc/score_reports/score_report_codex_subagent_001_unit_system_v1.json
```

The candidate's `kvmini.py` must accept `kvmini.py DBDIR COMMAND [ARGS...]` and is
invoked once per command, exactly as a user would run it.

## Rubric case schema

Each case in `rubric.json`:

- `id`, `layer` (`unit`|`system`), `category`, `requirement_refs`, `description`, `weight`
- `system_dimension` — system cases only
- `env` — optional environment variables applied to every command
- `setup_files` — optional files written into the workspace before commands run
- `commands` — list; each item is `["DBDIR","cmd",...]` or `{"args":[...],"expect_error":true}`
- `checks` — `{kind: {command_index: expected}}` where kind is one of
  `stdout_equals`, `stdout_json`, `stdout_contains`, `stdout_json_contains`
