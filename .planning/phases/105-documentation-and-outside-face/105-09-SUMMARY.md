---
phase: 105-documentation-and-outside-face
plan: 09
subsystem: docs
tags: [phase-gate, grep, positive-control, link-check, cli-audit, figshare, deck]

# Dependency graph
requires:
  - phase: 105-documentation-and-outside-face
    provides: rewritten README/docs/CLAUDE.md (105-01..05), deck (105-06), figshare record v3 (105-07), removals (105-08), shift-source credit (105-10)
provides:
  - Repeatable phase gate `105-check-outside-face.sh` (12 checks, two positive controls) — green
  - CLI example audit `105-check-cli-examples.py` against the live `ailsa --help` (two positive controls) — 155 invocations clean
  - Three documentation defects fixed (TOC anchors, PyPI-deferral record, the "--format json everywhere" claim)
affects: [phase 105 verification, 106 (skill rename; README already names /ailsa:*), 111 (PyPI upload)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Phase gate with positive controls: plant the forbidden string in a scratch copy and require the grep to fire before trusting an empty result"
    - "CLI docs audit: walk each documented invocation down the Click tree via --help, check every option against the resolved command"

key-files:
  created:
    - .planning/phases/105-documentation-and-outside-face/105-check-outside-face.sh
    - .planning/phases/105-documentation-and-outside-face/105-check-cli-examples.py
    - .planning/phases/105-documentation-and-outside-face/deferred-items.md
  modified:
    - README.md
    - CLAUDE.md
    - docs/ARCHITECTURE.md
    - docs/INSTALLATION.md
    - docs/nmr_shift_prediction_tools.md
    - docs/infographics/build.py
    - docs/infographics/deck.html
    - docs/infographics/ailsa-infographics.pdf
    - .planning/phases/104-package-and-cli/104-HUMAN-UAT.md

key-decisions:
  - "D-05 check follows the renumbering: the PyPI upload is recorded as deferred until after Phase 111 (the repository phase, numbered 107 when D-05 was taken); the gate also rejects a leftover 'after Phase 107'"
  - "The docs, not the code, were corrected for the --format json claim: nine setup/visualize commands have no --format, and D-14 requires docs correct against the current CLI; adding the option is a deferred code item"

patterns-established:
  - "Gate scripts live in the phase directory (planning history), run from any cwd, print one PASS/FAIL line per check, exit non-zero on any FAIL"

requirements-completed: [DOC-01, DOC-02, DOC-03, DOC-04]

# Metrics
duration: 22min
completed: 2026-10-14
---

# Phase 105 Plan 09: Outside-face phase gate Summary

**Twelve-check outside-face gate and a live-`--help` CLI audit, both with positive controls, run green after fixing three doc defects the gate surfaced (broken TOC anchors, a stale PyPI-deferral record, and a false "every subcommand supports --format json" claim on the README, CLAUDE.md, ARCHITECTURE and deck).**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-10-14T15:02:31Z
- **Completed:** 2026-10-14T15:24Z
- **Tasks:** 2
- **Files modified:** 12 (3 created in the phase directory, 9 modified)

## Accomplishments

- Wrote `105-check-outside-face.sh` with all twelve checks of the plan, plus three extensions that
  make it stricter (anchor check 5c, README repository-link check 5d, file *names* in the residue
  check 3, and a guard against a leftover "after Phase 107" in check 8).
- Wrote `105-check-cli-examples.py` (stdlib only): 155 `ailsa` invocations across README.md,
  CLAUDE.md, docs/*.md and the deck README, resolved through 37 live `--help` texts.
- All three positive controls fire (old-name grep, no-better-claim regex, CLI audit), plus a second
  CLI control for an unknown option.
- Fixed every failure in its owning file; the deck was rebuilt from `build.py` and the PDF
  re-exported (8 pages).

## Final gate output (HEAD `f16c39c`)

Command: `python3 105-check-cli-examples.py && bash 105-check-outside-face.sh` → exit 0

```
       README.md: 35 invocation(s)
       CLAUDE.md: 5 invocation(s)
       docs/ARCHITECTURE.md: 11 invocation(s)
       docs/BENCHMARK.md: 0 invocation(s)
       docs/INSTALLATION.md: 17 invocation(s)
       docs/NUS-PORTABILITY.md: 13 invocation(s)
       docs/SERVER_BOOTSTRAP.md: 17 invocation(s)
       docs/USER_GUIDE.md: 55 invocation(s)
       docs/nmr_shift_prediction_tools.md: 0 invocation(s)
       docs/infographics/README.md: 2 invocation(s)
== 155 ailsa invocation(s) checked against `/opt/miniconda3/bin/ailsa ... --help` (37 help texts); 0 problem(s)
PASS
== Phase 105 outside-face gate (f16c39c)
PASS  1  old-name grep positive control fires (planted line reported as '495:lucy-ng')
PASS  2  no old name in the 20 outside-facing files
PASS  3  residue only in allow-listed files (7 file(s); 0 kept by user decision)
PASS  4  no MCP mention in README and the four setup/user docs
PASS  5a README links are absolute or #anchors (41 checked)
PASS  5b relative links in CLAUDE.md, docs/, deck README and faulon-bridge README resolve (13 checked)
PASS  5c #anchors match a heading in the target file (59 checked)
PASS  5d README links into github.com/steinbeck/ailsa name tracked paths (10 checked)
PASS  6a deck.html is in sync with build.py (rebuild changes nothing)
PASS  6b deck has 8 slides with counters 01/08..08/08
PASS  6c ailsa-infographics.pdf exists and is tracked
PASS  6d no deck file name carries the old name
PASS  7  figshare: title 'AILSA reference database: 13C NMR shifts and HOSE statistics for natural-product dereplication and shift prediction (COCONUT + NMRShiftDB)', doi 10.6084/m9.figshare.31073554.v3, file 61078393 (lucy-ng-derep.db.zip), version 3
PASS  8  D-05 PyPI upload recorded as deferred until after Phase 111 (REQUIREMENTS.md, 104-HUMAN-UAT.md)
PASS  9  README front page credits Nuzillard (first 30 lines) and spells out 'AI + LSD + Agents'
PASS  10a team as the design: README team section, ARCHITECTURE agent layer, deck slide 4 and CLAUDE.md
PASS  10b restricted configuration stated in README Evaluation, BENCHMARK execution section, deck slide 6 (once) and every file quoting 69.1
PASS  10c INSTALLATION and SERVER_BOOTSTRAP state 'do not form a team' and 'current schema'
PASS  10d hub-and-spoke confined to BENCHMARK 'How a benchmark run executes' (1 of 1 matches inside)
PASS  11a no-better-claim positive control fires (planted line reported as '495:With the agent team the full system achieves a higher rate.')
PASS  11b no claim that the full system performs better (README, BENCHMARK, ARCHITECTURE, build.py, deck.html)
PASS  12 shift-source DOI 10.5281/zenodo.6561449 in all 11 files that describe the reference DB
== 0 failing check(s)
```

CLI audit positive controls (scratch copies of README.md outside the repo, discarded):

```
PROBLEM …/README-plant.md:495: `ailsa lsd generate x` -> 'generate' is not a subcommand of `ailsa lsd` (has: analyze, check, rank, run, validate-inventory)
FAIL   (exit 1)
PROBLEM …/README-plant-opt.md:496: `ailsa lsd rank solutions.smi --bogus-flag 3` -> option --bogus-flag is not listed by `ailsa lsd rank --help`
FAIL   (exit 1)
```

Other acceptance criteria: the DOI `10.5281/zenodo.6561449` appears 4× in the gate script (checks 7
and 12); both fixed phrases are grepped by it; `git log --oneline 5f20057..HEAD -- .claude` prints
nothing.

## Task Commits

1. **Task 1: outside-face gate** — fixes `e2eff91` (fix, TOC anchors), `23e67d2` (docs, PyPI deferral record); script `a0b711f` (test)
2. **Task 2: CLI example audit** — fix `71a94de` (fix, --format json claim; deck rebuilt, PDF re-exported); script `f16c39c` (test)

**Plan metadata:** this SUMMARY's commit (immediately following)

## Files Created/Modified

- `105-check-outside-face.sh` — the phase gate (12 checks, positive controls 1 and 11a)
- `105-check-cli-examples.py` — CLI audit; optional file arguments for the positive control
- `deferred-items.md` — two CLI code observations outside the scope of a docs phase
- `docs/INSTALLATION.md`, `docs/nmr_shift_prediction_tools.md` — table-of-contents anchors repaired
- `README.md`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/infographics/build.py` (+ rebuilt `deck.html`, re-exported `ailsa-infographics.pdf`) — `--format json` claim names its exceptions
- `.planning/phases/104-package-and-cli/104-HUMAN-UAT.md` — PyPI deferral now names Phase 111

## Decisions Made

- **Check 8 targets Phase 111, not 107.** D-05 (2026-10-06) put the PyPI upload after "Phase 107
  (repo renamed)". The milestone extension of 2026-10-12 renumbered the repository phase to 111;
  REQUIREMENTS.md (PKG-01: "now Phase 111") and ROADMAP.md (Phase 111: "then the deferred PyPI
  upload") already said so, only 104-HUMAN-UAT.md still said 107. The check now requires "Phase 111"
  in both records and fails on a leftover "after Phase 107". This is the same check moved to the
  current numbering, not a weaker one.
- **Docs corrected, code left alone, for `--format json`.** See Deviation 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Broken table-of-contents anchors in two docs**
- **Found during:** Task 1 (the anchor check 5c, an extension of check 5)
- **Issue:** `docs/INSTALLATION.md` linked `#reference-databases`; the heading is "Reference
  Database". `docs/nmr_shift_prediction_tools.md` had six TOC anchors with a single hyphen where
  GitHub generates three for " - " in a heading (e.g. `#2-nmrnet---state-of-the-art-20242025`).
  Both predate Phase 105.
- **Fix:** anchors corrected to the GitHub slugs.
- **Files modified:** docs/INSTALLATION.md, docs/nmr_shift_prediction_tools.md
- **Commit:** e2eff91

**2. [Rule 3 - Blocking] D-05 bookkeeping named the renumbered phase**
- **Found during:** Task 1, check 8
- **Issue:** the plan's literal check ("after Phase 107" in REQUIREMENTS.md and 104-HUMAN-UAT.md)
  failed: REQUIREMENTS.md already says "now Phase 111"; 104-HUMAN-UAT.md was stale.
- **Fix:** 104-HUMAN-UAT.md updated to "after Phase 111" (with the renumbering explained); check 8
  updated as described under Decisions.
- **Files modified:** .planning/phases/104-package-and-cli/104-HUMAN-UAT.md
- **Commit:** 23e67d2

**3. [Rule 1 - Bug] "Every subcommand supports `--format json`" was false**
- **Found during:** Task 2 (an informal sweep beyond the audit: every leaf command's `--help`)
- **Issue:** 9 of 43 leaf commands have no `--format` (`database build/download/generate-hose-stats/info`,
  `fragment build/info`, `lsd check`, `predict build-table`, `visualize correlations`);
  `ailsa database info --format json` errors with "No such option". The claim stood in README (the
  future PyPI page), CLAUDE.md (2×), ARCHITECTURE (3×) and deck slide 8. D-14 requires the docs to
  be correct against the current CLI.
- **Fix:** each place now names the exceptions; deck slide 8 says "--format json on all analysis
  commands"; deck rebuilt, PDF re-exported (8 pages, text layer checked).
- **Files modified:** README.md, CLAUDE.md, docs/ARCHITECTURE.md, docs/infographics/build.py,
  docs/infographics/deck.html, docs/infographics/ailsa-infographics.pdf
- **Commit:** 71a94de

### Gate extensions beyond the plan (stricter, no check weakened)

- Check 3 also flags tracked *file names* containing the old name (only the allow-listed launchd
  plist has one).
- Check 5c verifies `#anchors` against GitHub heading slugs (README-internal, relative doc links,
  and README links into the repository); 5d verifies that README's absolute
  `github.com/steinbeck/ailsa/(blob|tree)/master/…` links name tracked paths.
- Check 7 also prints the record version (3).
- CLI audit: a second positive control (unknown option). An informal one-off check (not in the
  script) compared the 46 option lines listed under USER_GUIDE's command synopses with `--help`:
  all present.

## Issues Encountered

- First gate run: 5c (anchors) and 8 (D-05) failed → Deviations 1 and 2.
- After the `--format` fix, 6a failed until the rebuilt deck.html was committed — the check
  compares against the committed HTML, as intended.
- Chrome printed its usual harmless "Invalid mailbox" GPU message during the PDF export.

## Known Stubs

None.

## Deferred Issues

Logged in `deferred-items.md` (code under `src/`, out of scope for a docs phase): the top-level
`ailsa --help` prints its command list twice (the hand-written one omits `pylsd`); nine commands
lack `--format json`.

## Notes for verification

- The figshare data file is still named `lucy-ng-derep.db.zip` (file id 61078393 unchanged by
  design, no re-upload; the re-upload is one of the open v11.0 decisions). No outside-facing file
  in the repository names it.
- README names the skill commands `/ailsa:*`; the skill directory is still `.claude/commands/lucy-ng`
  until Phase 106 (final names per D-04). The PyPI upload after Phase 111 keeps the frozen PyPI
  README consistent with that.
- Manual prose checks of the plan's `<verification>` block (README intro, deck slides 4/6/8,
  BENCHMARK execution section) remain for `/gsd-verify-work`.

## User Setup Required

None.

## Self-Check: PASSED

- FOUND: .planning/phases/105-documentation-and-outside-face/105-check-outside-face.sh
- FOUND: .planning/phases/105-documentation-and-outside-face/105-check-cli-examples.py
- FOUND: .planning/phases/105-documentation-and-outside-face/deferred-items.md
- FOUND commits: e2eff91, 23e67d2, a0b711f, 71a94de, f16c39c
- Both scripts exit 0 at f16c39c; nothing pushed; `.planning/research/skill-rebuild/` untouched

---
*Phase: 105-documentation-and-outside-face*
*Completed: 2026-10-14*
