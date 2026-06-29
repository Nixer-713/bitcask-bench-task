# Public Candidate Packet

This directory is reserved for candidate-visible E2E full-project benchmark
packets.

Candidates may receive only files under a specific task packet here, normally:

```text
public_candidate_packet/<task-name>/
  prd.md
  public_api_contract.md
  packaging_contract.md
  starter files if explicitly needed
```

Rules:

- Do not place hidden tests, scorer scripts, source implementation checkouts,
  reference solutions, validation reports, or model outputs here.
- Do not include test names, case IDs, exact hidden expected outputs, scoring
  logic, private algorithms, or original implementation hints.
- The packet should be enough for a senior engineer to implement a complete
  installable package from scratch.
- Use `${PYTHON_BIN:-python3} -m pip install -e .` as the default editable
  install command unless the task explicitly declares a different command.

Current repository tasks under `task/` are legacy mini-product handoff packets.
New E2E full-project tasks should use this public/private split.
