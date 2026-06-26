# No-Gap Postmortem And Next-Task Strategy

Status baseline:

- `bitcask-realrepo-001`: candidate/no-gap-observed; not `core_strong`.
- `xitkit-realrepo-001`: source-grounded candidate/no-gap-observed; not
  `core_strong`.
- `marmite-realrepo-001`: hardened reference-satisfiable/no-positive-gap
  evidence; not `core_strong`.
- `jupytext-realrepo-001`: reference-satisfiable on `validation/jupytext`, but
  all three candidate agents also passed 34/34; not `core_strong`.

This memo is analysis only. It does not modify any task PRD/rubric, add
reference/scorer/candidate/report assets, or claim any current task is
gap-producing.

## Why The Current Tasks Did Not Produce Positive Gap

### Bitcask

Candidates likely passed because the task collapses into a simple state model:
parse commands, maintain the latest live value per key, and make `compact`
rewrite the live map. Unit cases and system cases both flow from the same
canonical abstraction.

The source-derived lifecycle pressure was fair: append-like mutation history,
delete tombstones, compaction, reload, small segment thresholds, and failed
command atomicity. But even after hardening, the public behavior still reduced
to:

```text
operation log -> live key map -> stats/compact/replay
```

Once a candidate implemented that central map correctly, additional lifecycle
cases mostly became longer traces of the same model. They tested correctness,
but did not create a strong unit/system split.

### Xitkit

Xitkit was more heterogeneous than Bitcask, but still manageable. The public
model was a task-list file with deterministic IDs, parsed attributes, filters,
sorts, stats, and writeback. Candidates could parse the file once into records,
mutate those records, and serialize them back.

The deterministic ID adaptation was necessary for fair scoring, but it also
removed much of the ambiguity that might have exposed system failures. Local
features such as status, priority, due date, tag extraction, and writeback were
simple enough that the system cases became cross-checks over one parsed list.

### Marmite

Marmite had the strongest derived-view shape among the first three tasks:
frontmatter and Markdown content fan out into pages, taxonomies, pagination,
feeds, search, URL manifests, wikilinks, backlinks, archives, draft exclusion,
and URL preview output.

The task was fair and source-grounded, but static generation is still a single
batch computation. A strong candidate can build a content graph once and derive
all outputs from it. The hardened archive/draft/URL cases increased coverage,
but did not force independently plausible local implementations to diverge.

The validation result confirmed this: reference passed 19/19 unit and 15/15
system; one candidate passed all cases; two candidates failed local filename
metadata / stream parsing behavior rather than showing high-unit/lower-system
positive gap.

### Jupytext

Jupytext looked promising because it has bidirectional representations,
pairing, sync, status, deterministic freshness, and output preservation. The
current mini-task also produced the cleanest PRD/rubric boundary: the public
rules for percent format, `metadata.minijupy.version`, pair paths, missing
counterparts, source override, and output preservation are explicit.

That fairness also made the task too implementable for this candidate batch.
A candidate can solve almost everything with:

```text
parse .ipynb/text -> normalized notebook model -> serialize/sync/status
```

Once that canonical notebook model is correct, unit cases and system cases both
fall out naturally. The validation branch showed:

| Run | Unit | System | Gap pp |
| --- | ---: | ---: | ---: |
| reference | 20/20 | 14/14 | 0.00 |
| codex_agent_001 | 20/20 | 14/14 | 0.00 |
| codex_agent_002 | 20/20 | 14/14 | 0.00 |
| codex_agent_003 | 20/20 | 14/14 | 0.00 |

This means `jupytext-realrepo-001` is executable and reference-satisfiable, but
no-positive-gap-observed for this batch. It is not invalid, but it is not
evidence for `core_strong`, `confirmed benchmark`, or `gap-producing`.

## Pattern Across The Four Tasks

The repeated failure mode is not bad validation. It is task abstraction that
allows one clean canonical model to drive every public output:

- Bitcask: live key map.
- Xitkit: parsed task record list.
- Marmite: content graph.
- Jupytext: normalized notebook model.

Canonical models are good engineering. Strong agents often find them. If a
single model can be rebuilt from scratch for every command and all outputs are
deterministic serializers over that model, then system tests may not be much
harder than unit tests.

The next task should create system pressure that is still public and
source-grounded, but harder to satisfy by rebuilding one model from scratch each
time.

## Criteria For The Next Source Task

Prefer sources with public behavior involving:

- irreversible or semi-irreversible state transitions;
- partial updates where only part of the state should change;
- dependency invalidation and stale cache detection;
- conflict detection when two public states diverge;
- multi-step user-visible history;
- lockfiles, status reports, manifests, or check reports that must agree with
  actual changes;
- workflows where locally correct commands can still leave global state
  inconsistent.

Avoid sources where the mini-task can be solved by:

- one canonical in-memory model plus deterministic serializers;
- one static build from source files to outputs;
- one live map/list plus metadata;
- hidden private implementation checks;
- exact templates, full language parity, network services, or external APIs.

System consistency should be emergent across independently plausible local
implementations. The PRD should still expose every tested behavior publicly.

## Whether To Harden Jupytext Further

Jupytext could be hardened only through public, source-grounded behavior. Plausible
directions include:

- project-level `sync` / `status` over multiple notebook pairs;
- conflict detection when both sides changed and versions diverge;
- cell deletion/rename output preservation edge cases;
- `status.differences` reasons that must match actual `sync` effects;
- a public manifest/check report, if source-grounded enough.

However, this should be a proposal step, not a direct PRD/rubric edit. The risk
is that more deterministic Jupytext cases will still be absorbed by the same
canonical notebook model, while less deterministic cases may drift into hidden
requirements.

Recommendation for Jupytext: stop current Jupytext as no-positive-gap evidence.
Do not harden it again unless a separate source-grounded proposal identifies a
behavior that cannot collapse into the existing canonical model.

## Next Source Candidates

### 1. `pydoit/doit`

- Repository: https://github.com/pydoit/doit
- Why stronger: doit is a task runner with DAG execution, file dependencies,
  cached results, and up-to-date skipping. Public docs describe tracking file
  dependencies and running only changed tasks.
- Likely mini-task shape: a deterministic `minidoit.py` reads task definitions,
  computes dependencies, runs actions, stores a state DB, reports `list`,
  `status`, `run`, `clean`, and `forget`.
- Likely unit cases: task parsing, topological ordering, file dependency
  hashing, action execution, target creation, stale/up-to-date detection, clean,
  invalid DAG errors.
- Likely system dimensions: dependency invalidation, stale cache consistency,
  partial rerun propagation, failure atomicity, clean/status/report agreement.
- Why it may produce positive gap: candidates can pass local DAG or action
  tests but fail when a changed dependency must invalidate only the correct
  downstream tasks while preserving unrelated cached state.
- Risks: real doit supports Python task functions and many plugins; mini-task
  must define a small public task-file format and deterministic built-in
  actions.

### 2. `pre-commit/pre-commit`

- Repository: https://github.com/pre-commit/pre-commit
- Why stronger: pre-commit combines config parsing, hook selection, file
  filtering, staged/all-file modes, autofix, fail-fast, reports, and exit
  status. Public docs describe a framework for configured hooks and hook
  execution.
- Likely mini-task shape: a deterministic `miniprecommit.py` reads a small hook
  config, filters files, runs built-in hook actions, applies autofixes, and
  emits report JSON.
- Likely unit cases: config parse, hook selection, include/exclude matching,
  single hook execution, autofix, exit code, invalid config errors.
- Likely system dimensions: filter/config/report fanout, autofix/report
  consistency, fail-fast boundaries, stage override consistency, invalid-config
  atomicity.
- Why it may produce positive gap: locally correct hooks may still produce
  inconsistent reports, file modifications, or exit codes when multiple hooks
  interact with the same file set.
- Risks: real external hook execution and Git index semantics are too
  environment-dependent; mini-task should use deterministic built-in hooks.

### 3. `sqlalchemy/alembic`

- Repository: https://github.com/sqlalchemy/alembic
- Why stronger: Alembic migration files form a public revision graph; docs
  describe non-linear dependency-graph versioning and migration script
  invocation.
- Likely mini-task shape: a deterministic `minialembic.py` reads migration
  files with `revision` / `down_revision`, tracks current revision(s), supports
  `history`, `heads`, `current`, `upgrade`, `downgrade`, `stamp`, and conflict
  reports over a small SQLite or JSON schema state.
- Likely unit cases: parse migration headers, build revision graph, detect
  multiple heads, compute upgrade path, apply one migration, report current
  state, reject broken dependencies.
- Likely system dimensions: revision graph consistency, multi-step upgrade
  history, branch conflict detection, downgrade/upgrade state agreement,
  failure atomicity.
- Why it may produce positive gap: local graph parsing or single migration
  application can pass while multi-step history, branch heads, current-state
  reports, and partial failure rollback diverge.
- Risks: full SQLAlchemy/Alembic behavior is too broad. The mini-task should use
  a tiny public migration operation language and avoid real autogeneration.

## Recommendation

Start next source selection with `pydoit/doit`.

Reason: it directly targets the missing benchmark shape: persistent state,
dependency invalidation, stale cache behavior, partial updates, and status/report
consistency. These are harder to reduce to one fresh canonical model per
command, but can still be defined with public, deterministic behavior.

Use `pre-commit/pre-commit` as the first backup if doit's source-grounding
proves too broad. Use `sqlalchemy/alembic` if the team wants stronger history
and conflict semantics and accepts a slightly higher mini-task design burden.

Do not continue hardening Jupytext by default. Record it as
reference-satisfiable/no-positive-gap-observed evidence, then start source
grounding for a new task.

## Sources Checked

- pydoit project/docs: https://pydoit.org/index.html
- pydoit repository: https://github.com/pydoit/doit
- pre-commit docs: https://pre-commit.com/
- pre-commit repository: https://github.com/pre-commit/pre-commit
- Alembic repository: https://github.com/sqlalchemy/alembic
- Alembic tutorial/docs: https://alembic.sqlalchemy.org/en/latest/tutorial.html
