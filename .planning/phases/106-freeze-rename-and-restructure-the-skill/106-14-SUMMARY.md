---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 14
subsystem: infra
tags: [sheldon, gate, wheel, skill-install, bundle]
requires: ["106-13"]
provides:
  - full gate at the phase head equal to the 106.1 baseline
  - wheel containing the frontier skill
  - Sheldon main checkout at the phase head with the skill linked
affects: ["106-15"]
key-files:
  created: []
  modified: []
requirements: [SKILL-01, SKILL-02, SKILL-03]
metrics:
  completed: 2026-11-27
---

# Phase 106 Plan 14: Sheldon gate, wheel and install Summary

The phase head `f56327a` runs on Sheldon exactly as green as the 106.1 baseline, the wheel ships the
frontier skill, and the main checkout carries the renamed skill by link; headless `/ailsa:status`
loads there. No tracked file changed; nothing was pushed.

## Gate (Task 1)

Code moved by bundle only: `p106.bundle` (`8c63cc3..master`) into the separate area, then
`git fetch` plus `merge --ff-only`; `repo/` HEAD equals vitus HEAD `f56327a`. Load at start was
about 12 (of 80 threads). The gate ran detached, single-process, niced, in about 3 minutes.

| Check | Baseline 106.1 | Phase head | Verdict |
|---|---|---|---|
| pytest | 5 failed, 1953 passed, 100 skipped | 5 failed, 2335 passed, 105 skipped | equal failures |
| failing ids new at head | | 0 | none |
| ruff | 273 | 273 | equal |
| mypy | 151 in 40 files | 151 in 40 files | equal |

The five failures are the baseline `tests/test_cli_webview.py` cases (missing webview extra), still
the same ids. Five new skips, all by design on Sheldon: two freeze-tag checks (tags
`paper-skill-v1`, `paper-skill-v2` absent in the bundle clone), two answer-scan checks (private
answer key not on this machine) and one teaching-set-name check (identities table is
maintainer-local). 0 skips under `tests/record`.

Wheel (`/mnt/raid_drive/chris/ailsa-106.1/p106-dist/ailsa-0.1.0-py3-none-any.whl`): the 31 files
under `ailsa/skills/ailsa/` are identical to the source tree on vitus (INDEX.md, CHANGELOG.md, six
commands, five agents, 18 references). No pytest or mypy process of this plan remains.

## Main checkout (Task 2)

- Preconditions: no `blind_case_batch.py` running; checkout clean at `5ed443a`.
- Bundle `p106b.bundle` (`5ed443a..master`, needed because `5ed443a` is older than `8c63cc3`),
  fetched and fast-forwarded: HEAD `f56327a`, `git status` empty. `uv pip install -e .` done;
  `hosegen` import already worked.
- `ailsa skill install ailsa --target claude --link` removed the six legacy links
  (`commands/lucy-ng`, five `agents/lucy-*.md`) and linked `commands/ailsa`, five `agents/ailsa-*.md`,
  `ailsa/references`, `ailsa/INDEX.md`. No regular file was left alone.
- Checks: `ailsa lsd check` LSD and outlsd available; `ailsa predict c13 CCO` succeeds (2 of 2);
  `ailsa database info` schema 3, 928,443 compounds, 111,493 formulas (DB untouched).
  `~/.local/bin/ailsa` did not exist; created as a new link to the checkout venv's `ailsa`.
  The legacy `~/.local/bin/lucy` link is still there (outside the plan's scope, left alone).
- Headless `/ailsa:status` (model `claude-opus-5-5`, fresh temp folder, logged in): recognised as a
  command; reported ailsa CLI OK (0.1.0), LSD OK, outlsd OK, database MISSING. The database line is
  expected: the check looks for the relative path `data/reference/ailsa-derep.db` in the working
  folder, while the host DB file is `data/reference/lucy-ng-derep.db` in the main checkout and
  `/mnt/raid_drive/chris/ailsa-db/ailsa-derep.db` elsewhere. Plan 15 must give the run the database
  explicitly (`LUCY_DATABASE`), as the gate script does; no login blocker.
- `case-uat-results*` listing unchanged (four folders before and after).

## Machines

Linked now:
- **vitus** (Plan 3): skill linked from the checkout there.
- **Sheldon** (this plan): `~/.claude/commands/ailsa` ->
  `/mnt/raid_drive/chris/lucy-ng/src/ailsa/skills/ailsa/commands`; five `~/.claude/agents/ailsa-*.md`
  -> `.../skills/ailsa/agents/`; `~/.claude/ailsa/references` and `INDEX.md` ->
  `.../skills/ailsa/`. No `lucy` entry remains in `~/.claude/commands` or `agents`.

Not linked by any plan:
- **Laptop**: shares the checkout through Dropbox; its old links dangle since the move synced. The
  user runs there once:
  `~/Dropbox/develop/lucy-ng/.venv/bin/ailsa skill install ailsa --target claude --link`
- **caffeine**: has no AILSA installation, so nothing to repair; optional install commands go into
  `106-HUMAN-UAT.md` in Plan 15.

Legacy regular files left alone by the installer on Sheldon: none.

SKILL-01 and SKILL-02 are complete on the reachable machines; the laptop command above is the one
named manual step.

## Deviations from Plan

None in substance. The bundle basis for the main checkout was `5ed443a` (older) rather than
`8c63cc3`, so a second bundle was cut; `p106.bundle` served the separate area. The first backgrounded
ssh launch returned slowly but the gate started and finished normally.

## Self-Check: PASSED

Verified: Sheldon HEADs equal `f56327a`; gate files `p106-repo.*` and `gate-106.done` present; links
present; no tracked file changed (`git status` shows only the pre-existing untracked research folder).
