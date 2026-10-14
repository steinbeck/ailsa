---
phase: 105-documentation-and-outside-face
plan: 08
subsystem: docs
tags: [git-rm, repo-cleanup, copyright, rename]

# Dependency graph
requires:
  - phase: 105-documentation-and-outside-face
    provides: D-11/D-15 removal-candidate list and approval checkpoint design (105-CONTEXT.md)
provides:
  - Five old-name/ballast documents removed from the public tree via `git rm` (recoverable from git history)
  - Confirmation that no tracked file outside .planning/ references any removed path
affects: [105-09 (phase gate / old-name residue allow-list)]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - analysis_ibuprofen/CASE_RESULTS.md (removed)
    - docs/superpowers/specs/2026-07-02-case-webview-design.md (removed)
    - docs/superpowers/specs/2026-08-10-case-forced-ranking-design.md (removed)
    - background/sherlock-analysis.md (removed)
    - background/wenk-thesis.txt (removed)

key-decisions:
  - "User approved removal of all five candidates, verbatim: \"Ok, Altdateien löschen.\" (2026-10-13)"

patterns-established: []

requirements-completed: [DOC-02]

# Metrics
duration: 10min
completed: 2026-10-13
---

# Phase 105 Plan 08: Remove old-name ballast documents Summary

**Five old-name/third-party ballast documents removed from the public tree via `git rm` after explicit user approval; all remain recoverable from git history.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-13T08:43:00Z (approx; Task 1 decision was answered prior to this execution run)
- **Completed:** 2026-10-13T08:53:37Z
- **Tasks:** 2
- **Files modified:** 5 (all deletions)

## Accomplishments
- Obtained and recorded the user's approval of the full removal list before any `git rm` ran (Task 1, resolved prior to this execution).
- Re-ran the reference check immediately before removal: no tracked file outside `.planning/` named any of the five candidate paths.
- Removed exactly the five approved files with `git rm`, committed in a single atomic commit.
- Confirmed the untracked local thesis PDF (the local thesis PDF in `background/`) and its `.gitignore` rule (`background/*.pdf`) are untouched.

## Task Commits

1. **Task 1: Present the removal list and get the user's approval** — checkpoint, no commit (decision recorded below; resolved 2026-10-13 prior to this execution run)
2. **Task 2: Remove exactly the approved files** - `60d6818` (chore)

**Plan metadata:** (this SUMMARY's commit, immediately following)

## Files Created/Modified
- `analysis_ibuprofen/CASE_RESULTS.md` - removed (dated February-era manual ibuprofen example run, old CLI argument order, not linked from any tracked file)
- `docs/superpowers/specs/2026-07-02-case-webview-design.md` - removed (dated internal design spec for the run dashboard, already built, not linked)
- `docs/superpowers/specs/2026-08-10-case-forced-ranking-design.md` - removed (dated internal design spec for forced ranking, already built, not linked)
- `background/sherlock-analysis.md` - removed (analysis of a named third party's PhD thesis on a competing CASE system, not linked)
- `background/wenk-thesis.txt` - removed (full text of that third-party dissertation — third-party copyright in a public repo, D-15)

## Decisions Made

**Task 1 decision — User's answer, recorded verbatim:** "Ok, Altdateien löschen."

This was interpreted as approval of option `remove-all` (all five candidates), per the plan's
`<decision>` block ("Which of the five old-name ballast documents are removed from the public
repository?") and its `remove-all` option ("Alle fünf entfernen (empfohlen)"). No subset was
named and no exception was raised, so all five were removed.

## Deviations from Plan

None - plan executed exactly as written. Task 1's checkpoint was already resolved by the user
before this execution run began (per the orchestrator's instructions); this run recorded the
verbatim answer, re-ran the reference check as Task 2 requires, and executed the removal.

## Issues Encountered

None. The reference check (`git ls-files | grep -v '^\.planning/' | xargs grep -l -F -e
analysis_ibuprofen -e superpowers -e sherlock-analysis -e wenk-thesis`) found zero matches both
before and after removal, confirming the five files were never linked from any other tracked
file outside `.planning/`.

## Old-name residue kept by user decision

None. The user approved removal of all five candidates — there is no subset left for the
phase gate (plan 105-09) to allow-list.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

The public tree no longer carries any of the five approved ballast documents (all recoverable
from git history via `git log --diff-filter=D`). The untracked local thesis PDF in
`background/` was never in git and stays on disk, unaffected. Plan 105-09's phase gate has
nothing to allow-list from this plan — no old-name residue remains among these five candidates.

## Self-Check: PASSED

- `git ls-files analysis_ibuprofen docs/superpowers background` returns empty for the five
  removed paths (confirmed before writing this summary).
- Commit `60d6818` exists: `git log --oneline --all | grep 60d6818` → found.
- the local thesis PDF in `background/` confirmed present and untracked (not in
  `git ls-files`) after removal.
- `.planning/STATE.md` confirmed untouched (still shows as `M` unstaged, not included in any
  commit made by this execution).

---
*Phase: 105-documentation-and-outside-face*
*Completed: 2026-10-13*
