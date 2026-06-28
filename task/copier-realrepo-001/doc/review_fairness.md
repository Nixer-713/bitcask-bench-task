# Copier Fairness Review

## Scope

Reviewed whether Copier PRD, source grounding, requirement map, and rubric are
aligned with public behavior and deterministic mini-task adaptations.

## Review Findings

| Area | Issue | Resolution | Verdict |
| --- | --- | --- | --- |
| Update options | Rubric used update-time `--exclude` and `--skip`, but the initial PRD command surface did not expose them. | PRD now exposes `--exclude` and `--skip` on `recopy` and `update`, and the exclude/skip invariant applies across copy, recopy, update, and pretend. | keep |
| Custom answers file | `_answers_file` and custom answers path behavior were present, but later commands needed an explicit public way to locate non-default answers files. | PRD now defines `--answers-file FILE` for `copy`, `recopy`, `update`, and `check-update`, and states it is required for later commands when a non-default answers file was used. | keep |
| Non-Git `_commit` | A rubric assertion originally implied `_commit` for a non-Git filesystem template. | PRD now states `_commit` is omitted for non-Git filesystem templates, and the rubric no longer checks `_commit` in that non-Git case. | keep |
| Pretend JSON | Rubric checked `"pretend": true` but the initial PRD did not state that field explicitly. | PRD now defines that `--pretend` prints JSON with `"pretend": true`, planned writes, skipped paths, and excluded paths. | keep |
| Recopy precedence | PRD wording made previous answers appear lower priority than template defaults. | PRD now defines separate precedence for `copy` versus `recopy`/`update`, with existing answers overriding defaults and CLI data overriding both. | keep |
| Conflict update advancement | Rubric expected conflict-producing updates to advance `_commit`, but PRD only implied this through successful update wording. | PRD now states public conflict artifacts are successful updates that exit `0`, report `conflicts`, and advance the answers file to the selected new `_commit`. | keep |

## Source Support

| Behavior | PRD support | Source evidence | Adaptation note | Verdict |
| --- | --- | --- | --- | --- |
| Copy/render files and paths | `prd.md#copy`, `prd.md#rendering` | `README.md`, `docs/generating.md`, `docs/creating.md`, `tests/test_copy.py`, `copier/_main.py` | Simple `{{ variable }}` substitution is a public deterministic subset. | keep |
| Answers precedence and storage | `prd.md#answers` | `docs/configuring.md`, `copier/_user_data.py`, `tests/test_cli.py`, `tests/test_answersfile.py` | Non-interactive answers only; secrets omitted from answers file. | keep |
| Local Git refs and updates | `prd.md#local-git`, `prd.md#update` | `docs/updating.md`, `copier/_cli.py`, `copier/_main.py`, `tests/test_updatediff.py`, `tests/test_check_update.py` | Only local Git refs/tags are supported; exact Copier merge internals are excluded. | keep |
| Tasks and migrations | `prd.md#tasks-and-migrations` | `docs/configuring.md`, `tests/test_tasks.py`, `tests/test_migrations.py` | Shell execution is replaced by safe `write`/`append` actions gated by `--trust`. | keep |
| Error atomicity | `prd.md#error-handling-and-atomicity` | `tests/test_cleanup.py`, `tests/test_updatediff.py`, `copier/_main.py` | Atomicity is made explicit for all mini-task write commands. | keep |

## Unresolved Blockers

None after the PRD/rubric alignment fixes above.
