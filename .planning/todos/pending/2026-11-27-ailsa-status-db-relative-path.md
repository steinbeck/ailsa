---
created: 2026-11-27
title: "`/ailsa:status` reports the reference database as missing when the session does not start in the checkout"
area: skill
files:
  - src/ailsa/skills/ailsa/commands/status.md
---

## Context — found in the Phase 106 acceptance (106-HUMAN-UAT.md, item 6)

`/ailsa:status` checks the reference database at the fixed relative path
`data/reference/ailsa-derep.db`. A session started anywhere else (a dataset folder, Sheldon's run
area) therefore reports the database as missing, although the analysis commands find it through the
usual search (environment variable, then standard locations); the Phase 106 acceptance run on
Sheldon had to pass it explicitly via `LUCY_DATABASE` only for the status report.

Inherited from the old skill, not caused by the rename. User decision 2026-11-27 (followed the
recommendation): leave it for the foundation phase (108), where the prerequisite check is revised
(FOUND-04: the check verifies every capability the skill relies on).

## Fix sketch

Let the status command call `ailsa database info` without a path, so it uses the same search as the
analysis commands, and report the path it found. Regenerate `tests/skill_files.sha256` in the same
commit.
