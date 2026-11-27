---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 04
subsystem: skill
tags: [skill, lint, answer-scan, tests]
requires: ["106-03"]
provides:
  - "tests/test_skill_frontier.py: lint of the frontier skill with a PENDING set"
  - "tests/test_skill_answer_scan.py: local-only answer scan and teaching-set name check"
key-files:
  created: [tests/test_skill_frontier.py, tests/test_skill_answer_scan.py]
requirements-completed: [SKILL-05, SKILL-06]
completed: 2026-11-27
---

# Phase 106 Plan 04: Skill lint and local answer scan Summary

The skill form (size, contents list, no history, dataset numbers or model IDs, no dead references, one term per role, no capital-letter emphasis, database credit) is now checked by pytest, file by file through a 15-entry `PENDING` set, and a local-only test runs the private answer scan on both skills.

## Commits

- `7eb2535` test: lint for the frontier skill (18 test functions, 178 items).
- `0ffb4cf` test: local answer scan for the packaged skills.

## Verification

- Normal run: 42 passed, 135 skipped (pending files, reason "awaiting restructure"), 1 xfailed (`test_restructure_complete`). `PENDING` has 15 entries. Ruff clean.
- Positive control with `AILSA_LINT_IGNORE_PENDING=1`: 59 failed, 118 passed, 1 xfailed. Failures include test_size (case.md, ailsa-diagnostic.md), test_emphasis (devils-advocate agent), test_datasets (sanitise.md), test_model_ids (case.md), test_dead_refs (ailsa-diagnostic.md); by type: 4 size, 10 toc, 7 history, 8 datasets, 2 model IDs, 6 dead refs, 10 terms, 10 emphasis, 3 db credit.
- Answer scan test: 3 passed locally (two skills plus the name check); the three baseline hits (datasets 133, 148, 218) are all in pending files (devil's advocate agent, sanitise). With `AILSA_ANSWER_KEY_DIR=/nonexistent` the module skips (3 skipped). `.planning/CASE-DATASET-IDENTITIES.md` is git-ignored.

## Deviations from Plan

1. [Rule 1] The line-start command match (`ailsa ...`) first caught the prose line "ailsa CLI, LSD solver ..." in help.md; it now requires a lowercase command word after `ailsa`.
2. [Rule 1] The `devils advocate` term pattern got a `(?<!ailsa-)` lookbehind so the legitimate agent name `ailsa-devils-advocate` (INDEX.md link text) is not flagged.
3. No always-on check needed a skill text change, so `tests/skill_files.sha256` is unchanged.

## Known Stubs

None.

## Self-Check: PASSED

Both test files exist and are committed; STATE.md and ROADMAP.md untouched.
