---
phase: 105-documentation-and-outside-face
plan: 01
subsystem: docs
tags: [readme, pypi-long-description, ailsa-rename, benchmark-reporting]

requires:
  - phase: 104-package-and-cli
    provides: "ailsa CLI, module and PyPI package name; ailsa-derep.db default filename"
provides:
  - "README.md rewritten as the AILSA front page: name/expansion, LSD/Nuzillard credit up front"
  - "Team-as-design description of the CASE agent team (direct review loop, requests to NMR chemist) per D-13a"
  - "Evaluation section stating the benchmark figures were measured in a restricted configuration"
  - "Fixed phrases ('specialists that coordinate with each other', 'direct review loop', 'ask the NMR chemist', 'restricted configuration', 'without the agent team', 'without statistical detection') that the 105-09 phase gate greps for"
affects: [105-03, 105-06, 105-09]

tech-stack:
  added: []
  patterns:
    - "README links are absolute github.com/steinbeck/ailsa URLs (PyPI long-description safety) rather than repo-relative paths"

key-files:
  created: []
  modified:
    - README.md

key-decisions:
  - "Both plan tasks (top-half rewrite, bottom-half rewrite) were delivered in a single Write + single commit, since the two tasks rewrite the same file as one coherent pass and a mid-file split would have produced an internally inconsistent intermediate commit (still-old CLI name in the bottom half while the top half already said AILSA)."
  - "Diagram for 'How a run unfolds' redrawn to show the coordinator connected to all four specialists plus the two specialist-to-specialist channels (LSD Engineer <-> Devil's Advocate direct review loop; LSD Engineer -> NMR Chemist requests), replacing the old hub-only diagram."

requirements-completed: [DOC-01, DOC-02]

duration: 35min
completed: 2026-10-13
---

# Phase 105 Plan 01: README rewrite as AILSA front page Summary

**README.md rewritten end to end as the AILSA project page — LSD and Jean-Marc Nuzillard credited in the first ten lines, the CASE agent team described as a coordinated design with its direct review loop and NMR-chemist request channel, and the Evaluation section stating plainly that the 69.1% benchmark figure was measured without the agent team and without statistical detection.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-10-13
- **Tasks:** 2 (delivered as one Write + one commit — see Decisions)
- **Files modified:** 1 (README.md)

## Accomplishments
- README identity, credit and CLI examples rewritten and verified against the live `ailsa --help` CLI (all 16 command groups, five `--help` invocations exit 0 with every flag used in the README actually present).
- "The CASE Agent Team" section and its ASCII diagram rewritten per D-13a: the team is presented as the design (four specialists plus a direct review loop between the LSD Engineer and the Devil's Advocate, and a direct request channel from the LSD Engineer to the NMR Chemist), sourced from the live `.claude/agents/lucy-lsd-engineer.md` and `.claude/agents/lucy-devils-advocate.md` message-interface sections.
- Evaluation section keeps every benchmark figure verbatim from `docs/BENCHMARK.md` (177/256, 189/256, 76.6%, 81.8%, 25 timeouts, 67 vs 40, 30 won/3 lost, p = 1.4·10⁻⁶) and adds the restricted-configuration statement next to them, without any claim that the full system performs better.
- All Lucy/lucy-ng traces removed (0 case-insensitive "lucy" hits in the whole file), including the Lucy-lineage blockquote and the "original Lucy concept" acknowledgment line.
- Every non-anchor README link converted to an absolute `https://github.com/steinbeck/ailsa/...` URL (0 relative links remain) so the file is safe as the eventual PyPI long description.

## Task Commits

Both plan tasks were delivered in one commit, since they rewrite the same file as a single continuous pass (Task 2 explicitly starts from "README.md (current state after Task 1)" and the two halves must be internally consistent at every commit — see Decisions Made):

1. **Task 1 + Task 2: Rewrite README.md top and bottom halves (identity/team/CLI, then evaluation/installation/background/architecture/citation)** - `2b6af6c` (docs)

**Plan metadata:** pending (final commit by the orchestrator step, per instructions this executor does not update STATE.md/ROADMAP.md)

## Files Created/Modified
- `README.md` - Full rewrite: AILSA identity and LSD/Nuzillard credit (lines 1-21), agent-team-as-design section with direct-channel diagram, CLI command table and verified examples, Evaluation section with the restricted-configuration statement, Installation/Scientific-Background/Architecture/Supported-Data/Development/License sections renamed and re-linked, all links made absolute.

## Decisions Made
- Delivered both plan tasks in a single Write operation and a single git commit. The plan's own task split documents that Task 2 begins from "README.md (current state after Task 1)" — i.e. the two halves were always meant to be edited sequentially within one file, and the acceptance criteria for both tasks apply to the finished file as a whole (e.g. the whole-file `grep -ci lucy` check in Task 2 only passes once Task 1's rewrite is also in place). Committing the file mid-rewrite would have produced an intermediate commit with one half in the old name and the other in the new name, which is a worse state than either task's own acceptance bar. All of Task 1's and Task 2's individual acceptance criteria were verified separately against the finished file (see Issues Encountered) before the single commit was made.
- "ailsa pick" CLI table row kept both HSQC/HMBC as part of "1D, 2D, HSQC, HMBC" per the plan's prescribed wording, and the representative-invocations block states explicitly that `ailsa lsd generate` does not exist and that the per-run LSD input file is built by the LSD-engineer agent, not a CLI command (D-14).

## Deviations from Plan

None - plan executed exactly as written. Both tasks' required content, fixed phrases, and link-absoluteness rules were implemented as specified; the only adaptation (documented above under Decisions Made) was packaging the two tasks into one commit rather than two, since splitting them would have produced an internally inconsistent intermediate state in the same file.

## Issues Encountered

None. All automated verification commands from the plan's `<verify>` blocks and `<acceptance_criteria>` lists were run against the finished file and passed:
- Lines 1-210 and whole-file case-insensitive "lucy" count: 0.
- `Nuzillard` appears in the first 30 lines; `AI + LSD + Agents` appears once.
- Forbidden CLI strings (`lsd generate`, `--dept135`, `--c13`, `TeamCreate`): 0 occurrences.
- `/ailsa:case` ≥ 2 (4 found), `ailsa-devils-advocate` ≥ 1 (1 found).
- `acquired`, `formerly`, `hub-and-spoke`: 0 occurrences each (whole file).
- Team section (## The CASE Agent Team .. ## Running a CASE Elucidation) contains all three fixed phrases: "specialists that coordinate with each other", "direct review loop", "ask the NMR chemist" — each found once.
- Diagram section (### How a run unfolds .. ## Running a CASE Elucidation) contains arrow characters (◄/►, 2 found) and the word "requests" (1 found).
- No relative markdown links (0 found via the `]\([^)]+\)` extraction regex filtered for non-http(s)/non-#anchor targets).
- `ailsa-derep.db` and `pip install ailsa` each appear ≥ 1.
- Benchmark figures verbatim: `177 / 256` (1), `189 / 256` (1), `1.4 · 10⁻⁶` (1).
- Evaluation section contains all three restricted-configuration fixed phrases: "restricted configuration", "without the agent team", "without statistical detection" — each found once.
- `BENCHMARK.md#how-a-benchmark-run-executes` link present (1).
- No-better-claim regex (same pattern used by the 105-09 phase gate): 0 matching lines.
- `nuzillard.github.io/LSD` ≥ 2 (4 found), `doi:10.1002/mrc.4612` = 1, `@software{ailsa` = 1.
- `mcp` (case-insensitive): 0 occurrences.
- Live CLI verification: `ailsa --help` lists exactly the 16 groups used in the README's command table; `ailsa lsd rank --help`, `ailsa lsd run --help`, `ailsa pick hsqc --help`, `ailsa pick hmbc --help`, `ailsa dereplicate c13 --help` all exit 0 and list every flag used in the README's example commands.

## User Setup Required

None - no external service configuration required. (Note: this phase's 105-04 and 105-09 plans still need to add the `#how-a-benchmark-run-executes` anchor to `docs/BENCHMARK.md` and the gate checks respectively — this plan's link to that anchor is forward-referencing work landing in sibling plans of the same phase, per the phase's wave structure.)

## Next Phase Readiness

README.md now carries the fixed phrases that 105-09's phase-gate grep will check (team-design phrases, restricted-configuration phrases, no hub-and-spoke, no better-claim). Sibling plans 105-03 (ARCHITECTURE.md + BENCHMARK.md), 105-04 (INSTALLATION/SERVER_BOOTSTRAP/NUS-PORTABILITY) and 105-06 (infographic deck) must use the same fixed phrases and the same restricted-configuration framing so the phase reads consistently end to end; no blockers identified for those plans from this one's work.

---
*Phase: 105-documentation-and-outside-face*
*Completed: 2026-10-13*

## Self-Check: PASSED

- FOUND: README.md
- FOUND: 2b6af6c (commit present in `git log --oneline --all`)
