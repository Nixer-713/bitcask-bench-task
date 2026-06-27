# Jupytext Rewrite Note

Status: prior Jupytext PRD/rubric/map archived as no-gap-observed evidence under
`archive/no-gap-observed/jupytext-realrepo-001/`.

The active Jupytext task is intentionally reset for redesign. Keep
`doc/source_repo.md` as the source-grounding base. Do not reuse the archived
PRD/rubric mechanically.

## Rewrite Focus

- Start from public paired-notebook behavior, not Jupytext function boundaries.
- Build a capability map around `.ipynb` parsing, `py:percent` parsing,
  conversion, pairing config, sync source selection, status/check reports,
  output preservation, conflict detection, multi-file pair handling, and error
  atomicity.
- Add system pressure through public state flow: pair -> persisted sync state ->
  status/check -> conflict detection -> sync resolution -> output preservation.
- Consider a public state file or report only if the behavior is explicitly
  defined in the new PRD and source-grounded as a deterministic adaptation.
- Do not add real mtimes, notebook execution, full nbformat parity, Markdown /
  MyST / Quarto / Rmd, server/ContentsManager behavior, or private Jupytext
  internals.
