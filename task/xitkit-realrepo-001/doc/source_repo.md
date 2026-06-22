# Source Repository Notes

Canonical source repository:
`https://github.com/hoechstleistungshaartrockner/xitkit.git`

Local checkout used for analysis:
`/Users/nixer/项目/benchmark-source-repos/xitkit`

Checked commit: `2fd55de` on branch `main`.

## Source Signals

XitKit is a command-line task manager for `.xit` and `.md` task files. The
README describes multiple task states, priority markers, due dates, tags,
multi-line descriptions, filtering, statistics, batch commands, move, and
recurrence. See
`/Users/nixer/项目/benchmark-source-repos/xitkit/README.md:3` and
`/Users/nixer/项目/benchmark-source-repos/xitkit/README.md:67`.

The source CLI exposes `show`, `stats`, `add`, `mark`, `move`, `prio`, `tag`,
`untag`, `reschedule`, and related commands. The `show` command supports status,
priority, tag, due-date, file, sort, and order options at
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/__main__.py:49`.

The format guide defines five checkbox statuses, invalid checkbox forms, the
mandatory separator, exact four-space continuation indentation, priority marker
rules, due-date forms, and tag/value syntax. See
`/Users/nixer/项目/benchmark-source-repos/xitkit/syntax_guide.txt:4`,
`:50`, `:92`, `:129`, and `:183`.

The parser is explicitly responsible for checkbox statuses, priorities, due
dates, tags, multi-line descriptions, and UTF-8 text. See
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/fileparser.py:258`.
It maps status characters to task states at
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/fileparser.py:277`.

Filtering and statistics are separate service behavior. `TaskFilter` carries
status, priority, tags, due-on, and due-by fields at
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/services.py:25`.
Filtering is applied by status, minimum priority, tags, due-on, and due-by at
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/services.py:68`.
Statistics count status, priority, file, tags, and due dates at
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/services.py:110`.

Sorting by priority and due date is a public command behavior in the CLI and a
service behavior in source. See
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/__main__.py:73` and
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/services.py:166`.

The source maintains parsed files and stable task IDs through a file repository.
The repository tracks files, tasks, and an incrementing ID counter at
`/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/file_repository.py:14`.
Writeback is central to the source: tasks can be serialized back to checkbox
format at `/Users/nixer/项目/benchmark-source-repos/xitkit/xitkit/task.py:471`.

The source tests include round-trip parse/write/parse checks, demonstrating that
writeback semantics are part of the product behavior. See
`/Users/nixer/项目/benchmark-source-repos/xitkit/tests/test_integration.py:203`.

## Mini-Task Adaptation

The benchmark narrows the source into a deterministic `xitlite.py` CLI. It keeps
the source-derived public behaviors most likely to create system-level
composition pressure:

- `.xit` task parsing
- stable task IDs
- status, priority, due-date, and tag extraction
- JSON list and stats views
- filtering and sorting
- writeback via add, mark, tag, untag, reschedule
- cross-file move consistency

The mini-task intentionally excludes Rich formatting, interactive mode, Markdown
code-block parsing, recurrence, shell expansion, pomodoro, and exact internal
class/module structure. These exclusions keep the benchmark deterministic and
avoid private implementation checks.
