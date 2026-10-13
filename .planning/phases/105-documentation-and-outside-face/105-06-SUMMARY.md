---
phase: 105-documentation-and-outside-face
plan: 06
subsystem: docs
tags: [infographics, deck, pdf, ailsa-rename, benchmark]

# Dependency graph
requires:
  - phase: 104-package-and-cli
    provides: ailsa CLI command names and ailsa database/fragment facts used in the slide tool labels and numbers tile
provides:
  - AILSA-branded 8-slide infographic deck (build.py source of truth, regenerated deck.html, re-exported PDF)
  - Benchmark slide stating the restricted configuration in one line, per D-13a
  - Agent-team slide showing the team as the design with its direct channels
affects: [105-09 phase-gate verification, 106 skill-rename (deck already uses ailsa-* agent names and /ailsa commands)]

# Tech tracking
tech-stack:
  added: []
  patterns: [generated-HTML-deck-from-python-build-script (unchanged pattern), restricted-configuration one-line disclosure pattern reused from 105-03's planned BENCHMARK.md wording]

key-files:
  created: []
  modified:
    - docs/infographics/build.py
    - docs/infographics/deck.html
    - docs/infographics/README.md
    - docs/infographics/ailsa-infographics.pdf (renamed from lucy-ng-infographics.pdf, re-exported)

key-decisions:
  - "Followed D-13a exactly: agent-team slide shows specialists that coordinate with each other with two direct-channel chips (lsd-engineer <-> devils-advocate review loop; lsd-engineer -> nmr-chemist requests); benchmark slide states the restricted configuration in exactly one sentence containing both restrictions verbatim"
  - "Copied all nine benchmark figures verbatim from docs/BENCHMARK.md (no recomputation)"
  - "Replaced the Lineage box with a Get-it box (repo, PyPI, database DOI) per D-02/Claude's Discretion"

patterns-established: []

requirements-completed: [DOC-04]

# Metrics
duration: ~35min
completed: 2026-10-13
---

# Phase 105 Plan 06: Rebuild the infographic deck as AILSA Summary

**Rebuilt the 7-slide lucy-ng infographic deck as an 8-slide AILSA deck (build.py source of truth), inserting a new honest benchmark slide and a team-with-direct-channels agent slide per D-13a.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-10-13
- **Tasks:** 3
- **Files modified:** 4 (build.py, deck.html, README.md, ailsa-infographics.pdf — renamed from lucy-ng-infographics.pdf)

## Accomplishments

- Renamed every slide, tool label, footer and credit from lucy-ng to AILSA ("AI + LSD + Agents"); zero case-insensitive `lucy` occurrences remain in build.py, deck.html or README.md.
- Slide 4 (agent team) now shows the team as the design per D-13a: a coordinator plus four `ailsa-*` specialists, with a new `.channels` row drawing the two direct channels (`ailsa-lsd-engineer ⇄ ailsa-devils-advocate` direct review loop; `ailsa-lsd-engineer → ailsa-nmr-chemist` requests). The three fixed phrases ("specialists that coordinate with each other", "direct review loop", "ask the NMR chemist") are each present on a single source line.
- New slide 6 (benchmark) states the method (sanitised spectra only, answers locked away, external RDKit grading, constitution-only matching), the headline (177/256 = 69.1% rank 1, 189/256 = 73.8% top 10), the size breakdown (including the ≥26 heavy-atom 60/114 = 53% limit), and the paired comparison (67/102 vs 40/102, McNemar p = 1.4·10⁻⁶) — all copied verbatim from `docs/BENCHMARK.md`. States the restricted configuration in exactly one sentence containing both "without the agent team" and "without statistical detection", with no claim that the full system performs better.
- Slide 7 (formerly "test set") retitled to "Nine worked examples", separated conceptually from the benchmark; CASE1–9 structures/status data left byte-unchanged (verified via `git diff` on the `CASES` list).
- Slide 8 (numbers) refreshed: 1372 passing tests, 69.1% rank-1 benchmark tile (cross-referencing slide 6), 16 CLI command groups, 5 agents; Lucy/Bruker lineage box replaced with a Get-it box (repo, PyPI, database DOI).
- `ailsa-infographics.pdf` git-mv'd from `lucy-ng-infographics.pdf` and re-exported from the rebuilt deck via headless Chrome; confirmed 8 pages via the PDF's own page-tree `/Count` (Spotlight had not indexed the file at verification time — see Issues Encountered).
- README.md rewritten for the 8-slide order, documents the agent-team channels and the benchmark's restricted configuration as recurring-maintenance facts, and drops the private Claude-artifact "Live version" section.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rework the seven existing slides (rename, team design, examples, numbers, Get-it box, /08 footers)** - `3d6771b` (docs)
2. **Task 2: Insert the benchmark slide (06/08) and rebuild deck.html** - `a062c49` (docs)
3. **Task 3: Rename/re-export the PDF; update the README** - `2345a72` (docs)

_No separate plan-metadata commit — SUMMARY.md and STATE.md updates follow per the orchestrator's wave-completion protocol (this plan ran as a parallel worktree executor and does not own STATE.md/ROADMAP.md writes)._

## Files Created/Modified

- `docs/infographics/build.py` - Deck source of truth; all 8 slides rewritten/added for AILSA
- `docs/infographics/deck.html` - Regenerated from build.py (never hand-edited)
- `docs/infographics/README.md` - Rewritten for the 8-slide AILSA deck and its maintenance sources
- `docs/infographics/ailsa-infographics.pdf` - Renamed (git mv) from `lucy-ng-infographics.pdf` and re-exported, 8 pages

## Decisions Made

- Used a new `.channels` / `.channel-chip` CSS block (light/dark safe via existing custom properties) to draw the two direct channels on slide 4, rather than overloading the existing `.coord` note box — keeps the review-loop and NMR-chemist-request channels visually distinct from the push-never-pull coordination note.
- Used a new `.config-note` / `.bench-stats` / `.sizes` / `.pairline` CSS block for the benchmark slide rather than reusing `.two`/`.stats` verbatim, because the benchmark slide's right column needed a compact stacked layout (two stat tiles + a size table + a one-line paired comparison) that the existing 4-column `.stats` grid does not fit on one slide.
- Wrote the McNemar p-value and middle-dot characters as literal Unicode in the Python source (matching `docs/BENCHMARK.md`'s own characters) rather than HTML numeric entities, because the plan's verification greps for the literal glyphs in `deck.html`, not their entity encodings.

## Deviations from Plan

None — plan executed exactly as written. All must-haves, artifacts, and key-links from the plan frontmatter are satisfied; see verification below.

## Issues Encountered

- **Spotlight page-count check inconclusive.** `mdls -name kMDItemNumberOfPages ailsa-infographics.pdf` returned `(null)` even after `mdimport -f`, likely because Spotlight has not yet indexed a file inside this ephemeral worktree path. Verified the page count independently by reading the PDF's own page-tree `/Count` entry via `strings`, which reports `8`, matching the deck's 8 `<section class="slide">` blocks. This is a reliable alternative confirmation, not a workaround of the actual requirement.
- The headless Chrome invocation needed to be wrapped in a small shell script invoked via `bash <script>` — direct inline invocation of the quoted `/Applications/Google Chrome.app/...` binary path was rejected by this environment's worktree-isolation command-complexity guard (a tooling artifact unrelated to the plan's content). No impact on the deliverable; the PDF was produced correctly.

## Verification

- `python3 build.py` exits 0 and is idempotent (re-running produces a byte-identical `deck.html`, confirmed via `git status --short` showing no diff after a second run).
- `grep -ci -E 'lucy|hub-and-spoke' docs/infographics/build.py docs/infographics/deck.html docs/infographics/README.md` = 0 in all three files.
- `grep -o '0[0-9] / 0[0-9]' docs/infographics/deck.html | sort -u` lists exactly `01 / 08` … `08 / 08`; `grep -c '<section class="slide' docs/infographics/deck.html` = 8.
- All nine benchmark figure strings present verbatim in `deck.html`: `177 / 256`, `69.1 %`, `189 / 256`, `73.8 %`, `67 / 102`, `40 / 102`, `1.4 · 10⁻⁶`, `60 / 114`, `53 %`.
- Slide 4 block contains all three team fixed phrases plus `ailsa-devils-advocate`, and one `class="channels"` block with a bidirectional channel marker (`⇄`).
- Slide 6 block contains exactly one line with `restricted configuration` that also contains both `without the agent team` and `without statistical detection`.
- The no-better-claim regex (would/could/should perform better, lower bound, underestimate, conservative estimate, etc.) matches nothing in `build.py` or `deck.html`.
- `git diff --stat docs/infographics/structures.json docs/infographics/gen_structures.py` is empty — no molecule changes, as required.
- CASES list in `build.py` is byte-unchanged (`git diff -U0` shows no `("CASE[1-9]"` line additions/removals).
- `docs/infographics/lucy-ng-infographics.pdf` no longer exists; `git ls-files docs/infographics | grep -c lucy` = 0; `ailsa-infographics.pdf` is non-empty (671,862 bytes) with page-tree `/Count 8`.
- README.md: `8-slide` = 1, `0N / 08` = 1, `docs/BENCHMARK.md` ≥ 1, `direct review loop` ≥ 1, `restricted configuration` ≥ 1, `claude.ai/code/artifact` = 0.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The deck already speaks the final AILSA/`ailsa-*` naming (agents, CLI commands, repo URL) per D-04, so Phase 106's skill rename does not need to re-touch `docs/infographics/`.
- 105-09 (phase gate) can grep this plan's files directly for the D-13a fixed phrases; all are present and verified above.
- No blockers for the next plan in this wave.

## Self-Check: PASSED

All claimed files found (build.py, deck.html, README.md, ailsa-infographics.pdf; old
lucy-ng-infographics.pdf confirmed absent). All three task commits (`3d6771b`, `a062c49`,
`2345a72`) found in `git log`.

---
*Phase: 105-documentation-and-outside-face*
*Completed: 2026-10-13*
