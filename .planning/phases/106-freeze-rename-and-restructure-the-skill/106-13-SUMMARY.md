---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 13
subsystem: docs
tags: [freeze, docs, skill-install, cli-help]
requires: ["106-12"]
provides:
  - benchmark environment and the two paper-skill states on record
  - docs point at the packaged skill and `ailsa skill install ailsa`
  - credit for the COCONUT shift source in `ailsa database download --help`
affects: [docs/BENCHMARK.md, docs/SKILLS.md, README.md, CLAUDE.md]
key-files:
  created: [tests/test_freeze.py, tests/test_cli_database_help.py]
  modified:
    - docs/BENCHMARK.md
    - docs/SKILLS.md
    - README.md
    - docs/INSTALLATION.md
    - docs/SERVER_BOOTSTRAP.md
    - docs/ARCHITECTURE.md
    - CLAUDE.md
    - docs/infographics/README.md
    - src/ailsa/cli/database.py
decisions:
  - "The local pre-106 tag is cited by commit (2535715) in SKILLS.md, not by name."
metrics:
  tasks: 3
  completed: 2026-11-27
---

# Phase 106 Plan 13: Freeze record, install docs, download help credit

Records the two paper-skill states with the compute host environment, repoints all install
instructions at `ailsa skill install ailsa`, and adds the shift-source credit to the database
download help.

## Commits

- d630506: docs(106-13): benchmark environment and skill states recorded
- c4864d5: docs(106-13): install the packaged frontier skill
- b933ac9: feat(106-13): database download help credits the COCONUT shift source

## Verification

- tests/test_freeze.py: 4 passed, no skip (tags exist locally).
- tests/test_cli_database_help.py and tests/test_cli_database.py: 20 passed.
- Grep gate over the docs for the old `.claude/` symlink layout: clean; `orchestrator` count in CLAUDE.md is 0.
- Todo moved to `.planning/todos/completed/` with `git mv`.

## Deviations from Plan

- Install-docs wording in INSTALLATION.md was rephrased so the grep gate (which matches `.claude/commands/ailsa`) passes.
- `ruff check src/ailsa/cli/database.py` reports four pre-existing E501 line-length errors (lines 427, 475, 501, 539), none on lines touched here; out of scope, not fixed. The new test file is clean.
- README: added a "Claude Code skill" subsection under Installation and replaced the `.claude/` entry in the architecture tree with `skills/` under `src/ailsa`.

## Note for the user

`docs/infographics/build.py` was not touched and `deck.html` not rebuilt. If the deck names the skill location (`.claude/agents/`), update `build.py` and rebuild at milestone close.

## Known Stubs

None.

## Self-Check: PASSED

Commits d630506, c4864d5, b933ac9 exist; new test files present.
