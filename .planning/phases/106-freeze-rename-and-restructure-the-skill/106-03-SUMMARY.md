---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 03
subsystem: skill
tags: [skill, rename, package-data, installer]
requires: ["106-01", "106-02"]
provides:
  - "frontier skill as package data in src/ailsa/skills/ailsa (6 commands, 5 ailsa-* agents, 4 references, INDEX.md, CHANGELOG.md)"
  - "tests/skill_files.sha256 manifest guard"
  - "vitus linked to the checkout"
key-files:
  created: [src/ailsa/skills/ailsa/INDEX.md, src/ailsa/skills/ailsa/CHANGELOG.md, tests/skill_files.sha256]
  modified: [tests/test_skill_files_unchanged.py, tests/test_case_md_wv07.py, tests/test_skill_lite.py, tests/test_cli_skill.py]
requirements-completed: [SKILL-01, SKILL-02]
completed: 2026-11-27
---

# Phase 106 Plan 03: Move the frontier skill into the package Summary

The frontier skill now lives in `src/ailsa/skills/ailsa/` under the names `/ailsa:*` and `ailsa-*`, with the supervisor agent removed and the hash guard moved to a manifest. The rule inventory reports 0 LOST units after the move (all 1642 `same`).

## Commits

- `ba15190` refactor: `git mv` of 15 files, rename script, INDEX.md and CHANGELOG.md, manifest guard, three tests repointed. `.claude/commands` and `.claude/agents` hold no tracked file.
- `0fec158` test: two real-tree installer tests (command skill listed with version 0.1.0; copy install gives 6 commands, 5 agents, all reference files).

## Verification

Quick tests (skill_lite, skill_files_unchanged, case_md_wv07, cli_skill) pass, 50 and then 16 for the installer file, with no skips. Ruff is clean on touched tests. The old name is absent from the package tree.

## Deviations from Plan

Residual hits after the scripted rename were fixed by a second scratch script: the bundled-filter path in the lsd-engineer text now reads `src/ailsa/fragments/`; the help command title and description follow the plan text. The manifest also covers INDEX.md (16 entries). `help.md` shows as add rather than rename in git because its content changed heavily. No other deviations.

## Machines

- **vitus** (this machine, hostname ChristosMBP2019): linked by this plan. The installer removed the six legacy `lucy-ng` and `lucy-*` links and linked `~/.claude/commands/ailsa`, five `ailsa-*` agents, `~/.claude/ailsa/references` and `INDEX.md`. No legacy regular file was found. (The checkout path itself contains `lucy-ng`, so `grep lucy` over link targets still matches; no link name does.)
- **Sheldon**: follows in Plan 14.
- **Laptop**: not covered by any plan. It shares this checkout through Dropbox, so once Dropbox syncs the move commit its old `~/.claude/commands/lucy-ng` and `~/.claude/agents/lucy-*.md` links dangle and `/lucy-ng:*` stops working there until the user runs on the laptop: `~/Dropbox/develop/lucy-ng/.venv/bin/ailsa skill install ailsa --target claude --link` (the checkout's `.venv` is the laptop's editable install, so link mode applies, and the installer removes the dangling legacy links).
- **caffeine**: no Dropbox and, as checked 2026-11-27, no AILSA checkout, no `ailsa` CLI and no old links, so nothing dangles and there is nothing to repair. It gets the skill only if the user wants it (Plan 15 gives the commands in `106-HUMAN-UAT.md`).

## Known Stubs

None.

## Self-Check: PASSED

Both commits exist; INDEX.md, CHANGELOG.md and the manifest exist; STATE.md and ROADMAP.md untouched.
