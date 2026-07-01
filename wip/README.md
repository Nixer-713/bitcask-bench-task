# Work In Progress Tasks

`wip/` holds active task synthesis work.

Each candidate task should have:

```text
wip/<task-id>/
  PIPELINE_STATE.md
  filter_notes.md
  spec/
  filter/
  judge/
```

Start a new task by copying `wip/_template/PIPELINE_STATE.md` into the task
directory and replacing `{TASK_ID}` and `{DATE}`.

Do not move a task into `tasks/` until the judge marks it `QUALIFIED`.
