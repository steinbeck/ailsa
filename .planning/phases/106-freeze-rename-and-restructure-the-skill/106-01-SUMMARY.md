---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 01
subsystem: cli
tags: [skill, installer, symlink, click]
requires: []
provides:
  - "ailsa skill install for the command skill (INDEX.md kind): copy and --link mode, --root, legacy cleanup"
  - "local annotated tag frontier-skill-pre-106 (baseline for the rule inventory)"
affects: [106-03]
key-files:
  created: [tests/test_cli_skill.py]
  modified: [src/ailsa/cli/skill.py]
requirements-completed: [SKILL-01]
duration: 15min
completed: 2026-11-27
---

# Phase 106 Plan 01: Installer for the command skill Summary

`ailsa skill install ailsa` now places commands, agents and references under `~/.claude` (or `--root`) by copy or by symlink (`--link`), removes only old `lucy-ng` symlinks, and never deletes through a link.

## Tasks

1. Baseline tag and red tests: tag `frontier-skill-pre-106` created locally (annotated, not pushed) on commit `2535715`; `.claude` was verified identical to `f746297`. Tests commit `698996a` (12 test functions, 14 cases, 13 red).
2. Implementation: commit `feat(106-01): install the command skill by copy or link`. 26 tests green (new file plus `test_skill_lite.py`), ruff clean, mypy strict on `skill.py`: Success (finished within the minute locally).

## Decisions and deviations

- Package layout assumed by the installer (from RESEARCH/PATTERNS): `skills/ailsa/{INDEX.md,commands,agents,references}`; the test fixture builds exactly that (the plan text placed commands beside `skills/`, which contradicts the later plans).
- [Rule 2] The lean-skill path: a destination that is a symlink without `--force` now errors like an existing directory (previously `rmtree` on a link path would have failed anyway); with `--force` the link is unlinked, never `rmtree`d.
- `--link`/`--root` on an Agent Skill exit 1 with a one-line reason.

## Known Stubs

None.

## Self-Check: PASSED

Tag, tests file, `skill.py` and both commits exist; STATE.md and ROADMAP.md untouched.
