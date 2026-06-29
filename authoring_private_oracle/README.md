# Authoring Private Oracle

This directory is reserved for private E2E full-project benchmark authoring and
validation assets.

Expected task shape:

```text
authoring_private_oracle/<task-name>/
  scoring_manifest.json
  doc/source_repo.md
  doc/source_evidence_matrix.md
  doc/behavior_inventory.md
  doc/artifact_shape.md
  doc/requirement_map.md
  doc/test_inventory.md
  doc/test_derivability_review.md
  doc/environment_contract.md
  doc/oracle_validation_report.md
  doc/review_structure.md
  doc/review_fairness.md
  doc/review_oracle.md
  oracle/contract_tests/
  oracle/filtered_unit_tests/
  oracle/filtered_integration_tests/
  docker/run_eval.sh
  validation/original_report.json
  validation/model_reports/
```

Important boundary:

- Live oracle tests, Docker harnesses, reference/original checkouts, candidate
  outputs, score reports, and validation reports must not be committed to public
  handoff branches.
- This repository tracks this README as a directory boundary marker. Actual
  private runtime assets are ignored by `.gitignore` unless a branch is
  explicitly created as an internal validation branch.
- During candidate evaluation, agents must receive only the matching
  `public_candidate_packet/<task-name>/` directory.
