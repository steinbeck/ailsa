---
phase: 105-documentation-and-outside-face
verified: 2026-10-14T15:30:42Z
status: passed
score: 15/15 must-haves verified
re_verified: 2026-10-14T16:05:00Z (gap closed by 2760233)
overrides_applied: 0
gaps:
  - truth: "The benchmark slide shows the method, the figures, the paired comparison and the large-molecule limit honestly (D-06), and the deck PDF is a faithful 8-page export of it (105-06, 105-10)"
    status: closed
    resolution: "2760233 puts the four measurement steps of slide 6 in a 2x2 grid; every PDF page now ends with its footer line (pdftotext per page), page 6 inspected as an image"
    reason: >-
      deck.html renders slide 6 correctly on screen, but the committed PDF (the print layout,
      fixed 1280x720) overflows on page 6: the four 'How it is measured' cards are taller than
      the page. Card 03 covers the 'The limit is size' callout (its first line is half hidden,
      its second line - 'generation, not ranking, is what limits it. 25 runs hit the three-hour
      limit and count as failures.' - is not visible), and card 04 ('Constitution only /
      Stereochemistry is not tested') runs past the footer line and covers the slide label.
      Page 6 is the only page with text below the footer (PyMuPDF block scan: footer y=488,
      text down to y=512). The PDF is in sync with deck.html (a fresh headless-Chrome print
      gives identical text on all 8 pages), so the defect is in build.py's print layout, not
      a stale export. The size-limit table row (>= 26 heavy atoms: 60 / 114, 53 %) stays
      visible, but the sentence D-06 asks for ('honest about the large-molecule limit') is
      unreadable in the PDF that people hand around.
    artifacts:
      - path: "docs/infographics/build.py"
        issue: "slide 6 (lines 507-545) does not fit the print page; .step cards plus the config note push the .coord callout and card 04 below the footer"
      - path: "docs/infographics/ailsa-infographics.pdf"
        issue: "page 6 shows overlapping boxes and text past the footer"
      - path: ".planning/phases/105-documentation-and-outside-face/105-check-outside-face.sh"
        issue: "check 6 verifies the PDF exists and is tracked, but not that any page fits its frame"
    missing:
      - "Make slide 6 fit 1280x720 in print (shorten the four card texts or tighten the print CSS for this slide), rebuild deck.html, re-export ailsa-infographics.pdf, and look at page 6"
      - "Add a page-fit check to the gate (no text block below the footer on any PDF page) so the next rebuild cannot reintroduce it"
deferred:
  - truth: "Docs and the deck name the final skill commands /ailsa:* and agents ailsa-*; the skill files still sit under the old directory and agent names, so following INSTALLATION/SERVER_BOOTSTRAP today creates dangling symlinks"
    addressed_in: "Phase 106"
    evidence: "SKILL-01: 'A user runs /ailsa:case, /ailsa:dereplicate, ... the symlinks under ~/.claude/commands point at the new directory'; SKILL-02: agents are ailsa-*; accepted in advance by D-04"
  - truth: "README and deck slide 8 say 'pip install ailsa', which still gives the 0.0.1 name-reservation placeholder"
    addressed_in: "Phase 111"
    evidence: "Phase 111 success criterion 4: 'the deferred PyPI upload of 0.1.0 follows'; D-05; 104-HUMAN-UAT.md pending item"
  - truth: "Whether the public figshare file has the current schema that statistical detection needs (docs tell readers to check the 'Schema version' line)"
    addressed_in: "Phase 108"
    evidence: "Phase 108 goal: 'full reference DB on the compute host (figshare checked)'; ROADMAP open decision 3"
human_verification:
  - test: "Push the Phase 105 commits and open https://github.com/steinbeck/ailsa"
    expected: "The front page shows the AILSA README (no old name), and the links from the live figshare record land on it"
    why_human: "master is 51 commits ahead of the last-fetched origin/master (9a39af4, 2026-10-12), whose README is still the old-name version (82 mentions). The repository is public, so the push needs the user's go-ahead; the verifier must not contact the remote."
---

# Phase 105: Documentation and outside face — Verification Report

**Phase Goal:** Everything a reader sees from outside the code — README, docs, the skill's own
project memory, the figshare record and the infographic deck — presents the project as AILSA,
with LSD credited up front and the old name not mentioned (amended 2026-10-06, D-01).
**Verified:** 2026-10-14T15:30:42Z
**Status:** gaps_found (one partial gap: the PDF export of the benchmark slide)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Roadmap success criteria 1-4 first, then the plan/decision truths that add detail (D-02..D-17).

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | README presents AILSA with *AI + LSD + Agents*; LSD and its author credited up front; old name absent (SC1, DOC-01) | ✓ VERIFIED | README.md line 1 `# AILSA`, line 3 the expansion, lines 8-11 LSD and its author named in the first paragraph, again in "Built on LSD" (l. 42-49) and "Cite LSD first" (l. 462-474). `grep -i lucy README.md` empty; no "formerly", "lineage", "acquired". Gate checks 2 and 9 PASS. |
| 2 | docs/ and CLAUDE.md use the new project, package, CLI and command names; no living document instructs `lucy` (SC2, DOC-02) | ✓ VERIFIED | Gate check 2: 20 outside-facing files free of the old name in any spelling (positive control fires). Check 3: the only tracked files outside `.planning/.claude/src/tests/data` that still contain it are the 7 allow-listed host/runner scripts and `pyproject.toml` alias line (D-12). `tests/nus/test_portability_doc.py` 7 passed. |
| 3 | figshare record carries the new name in title and description; DOI and file unchanged (SC3, DOC-03) | ✓ VERIFIED | Live API (`api.figshare.com/v2/articles/31073554`): title "AILSA reference database: …", version 3, DOI 10.6084/m9.figshare.31073554.v3; description names AILSA (AI + LSD + Agents), credits LSD and its author, shows `ailsa database download`, links github.com/steinbeck/ailsa, no old name. File 61078393 `lucy-ng-derep.db.zip`, 828,954,592 bytes — same id and size as recorded in 105-RESEARCH.md before the edit (name kept by D-10/D-16). Licence CC BY 4.0. |
| 4 | Deck rebuilt under the new name with current headline numbers (SC4, DOC-04) | ✓ VERIFIED | Gate 6a: rebuilding from build.py changes nothing; 6b: 8 slides, counters 01/08..08/08; 6d: no old-name deck file. Slide 8 numbers match sources: 928K / 7.9M / 2.4M / 111K (PROJECT.md), 1372 passing tests (104-05-SUMMARY baseline), 16 CLI groups (live `ailsa --help`), 5 agents. No "8/9 CASE set", no "milestones shipped" tile (D-08). |
| 5 | No Lucy lineage, no acquirer text, no "formerly" note; legacy alias and legacy DB file name undocumented (D-01/D-02/D-03) | ✓ VERIFIED | Lineage box replaced by a "Get it" box (PDF page 8). No mention of the deprecated alias, the legacy DB file name, `~/.lucy` or the old env variables in any in-scope file (case-insensitive grep). |
| 6 | Docs use the final names now (D-04) | ✓ VERIFIED | README, INSTALLATION, SERVER_BOOTSTRAP, CLAUDE.md, deck use `/ailsa:*`, `ailsa-*`, `.claude/commands/ailsa`, github.com/steinbeck/ailsa. The mismatch with the not-yet-renamed skill directory is accepted by D-04 and owned by Phase 106 (see Deferred). |
| 7 | The agent team is described as the design, with the direct review loop and requests to the NMR chemist (D-13a) | ✓ VERIFIED | Read: README "The CASE Agent Team" (team of specialists that coordinate with each other; LSD engineer ⇄ devil's advocate review loop; LSD engineer asks the NMR chemist directly; diagram draws both channels, not a star only); ARCHITECTURE "The CASE agent layer" (same, plus the agent-team flag); deck slide 4 (channel chips for both direct channels); CLAUDE.md skill pointer. Gate 10a PASS. Wording warning on "unattended" below. |
| 8 | The 69 % are stated as measured in the restricted configuration wherever they appear; no claim that the full system does better; "hub-and-spoke" only in BENCHMARK's execution section (D-13a) | ✓ VERIFIED | Read: README Evaluation (l. 244-251: without the agent team because `claude -p` forms none, without statistical detection because of the outdated schema; "What the full configuration … achieves is a separate, not-yet-answered question"); BENCHMARK "How a benchmark run executes" (execution + detection paragraphs, both restrictions named, 173 run folders / 0 team creations / median 6 spawns / 7 messages) and a pointer at the top of Results; deck slide 6 config note (once); slide 8 tile "restricted configuration, see slide 6". Gates 10b, 10d, 11a/11b PASS. |
| 9 | Setup docs: team flag is part of the design; unattended runs do not form a team; statistical detection needs the current-schema database (D-13a) | ✓ VERIFIED | INSTALLATION l. 245-249 and 423-426; SERVER_BOOTSTRAP l. 115-118, 162, 170-173, 212. `ailsa database info` does print "Schema version" (src/ailsa/cli/database.py:184; live output "Schema version: 7"). Gate 10c PASS. |
| 10 | Docs are correct against the current CLI and Python API; no MCP (D-14) | ✓ VERIFIED | `105-check-cli-examples.py`: 155 invocations against 37 live `--help` texts, 0 problems. All 15 distinct `from ailsa …`/`import ailsa` lines in README/docs/CLAUDE.md execute. Gate 4: no MCP in README and the four setup/user docs. Spot runs of README examples (`read 1d`, `analyze symmetry`, `dereplicate c13`, `predict c13`, `pick hsqc`, `lsd check`) all exit 0. One leftover over-claim in ARCHITECTURE (warning below). |
| 11 | Shift-source credit (DOI 10.5281/zenodo.6561449, CC BY 4.0) in every text that describes the reference DB, with COCONUT shifts "predicted, not measured" and NMRShiftDB shifts experimental; no prediction software named (D-17) | ✓ VERIFIED | Present with both statements in README (l. 324, 483), CLAUDE.md (l. 95-96), INSTALLATION (l. 242-243), ARCHITECTURE (l. 340), USER_GUIDE (l. 324), SERVER_BOOTSTRAP (l. 113), rdmo text (l. 27-28), figshare_upload.py (l. 21-27, `references` set), zenodo_upload.py (l. 23-29, `isDerivedFrom`), deck slide 8 tile + Built-on box, and the live figshare description. BENCHMARK does not describe DB contents, so it needs none. No outside-facing text names the prediction software. Gate 12 PASS. |
| 12 | Benchmark slide: blind method, 177/256 = 69.1 %, 189/256 = 73.8 %, size table incl. ≥ 26: 60/114 = 53 %, paired 67/102 vs 40/102 (30 : 3, p = 1.4·10⁻⁶), the large-molecule limit, no compound identity; PDF is an 8-page export (D-06, 105-06, 105-10) | ⚠ PARTIAL (gap) | All figures match docs/BENCHMARK.md exactly and deck.html renders correctly on screen. **The committed PDF's page 6 overflows** (see Gaps): card 03 covers the "The limit is size" callout and card 04 runs past the footer. |
| 13 | Ballast documents removed only after user approval; local thesis PDF neither deleted nor tracked (D-11/D-15) | ✓ VERIFIED | The five approved files and the old deck PDF are neither tracked nor on disk; 105-08-SUMMARY records approval of all five ("None" kept). The local PDF in `background/` exists, is untracked and covered by `.gitignore` `background/*.pdf`. |
| 14 | PyPI upload recorded as deferred until after the repository phase (D-05, renumbered to Phase 111) | ✓ VERIFIED | REQUIREMENTS.md PKG-01 "now Phase 111"; 104-HUMAN-UAT.md "after Phase 111". Gate 8 PASS. |
| 15 | A repeatable, positive-controlled phase gate and CLI audit exist and pass (105-09) | ✓ VERIFIED | Both scripts run by the verifier at HEAD 0cad55c: gate "0 failing check(s)" (both positive controls fire), CLI audit "0 problem(s)". The gate rebuilt deck.html and left the working tree clean. |

**Score:** 14/15 truths verified (1 partial)

### Deferred Items

Not met yet, but explicitly owned by later phases of this milestone. They do not affect the status.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | `/ailsa:*` commands and `ailsa-*` agents named in the docs do not exist yet (skill still under the old directory/agent names); the symlink loops in INSTALLATION/SERVER_BOOTSTRAP find nothing today | Phase 106 | SKILL-01, SKILL-02; accepted in advance by D-04 |
| 2 | `pip install ailsa` (README, deck slide 8) still installs the 0.0.1 name-reservation placeholder | Phase 111 | SC4 "the deferred PyPI upload of 0.1.0 follows"; D-05 |
| 3 | Whether the public figshare file has the current schema that the docs tell readers to check | Phase 108 | Goal "full reference DB on the compute host (figshare checked)"; open decision 3 |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `README.md` | AILSA front page / future PyPI long description | ✓ VERIFIED | 494 lines; fixed phrases present; 41 links all absolute or `#anchor`; 10 repo links name tracked paths |
| `docs/USER_GUIDE.md` | CLI + Python API guide | ✓ VERIFIED | 55 invocations clean; imports resolve; no MCP |
| `docs/ARCHITECTURE.md` | Architecture with the designed team | ✓ VERIFIED | Agent-layer section present; module tree matches `src/ailsa/` (one over-claim, warning) |
| `docs/BENCHMARK.md` | Method, restricted configuration, figures | ✓ VERIFIED | Diff over the phase: only the two renames plus the new section and a Results pointer — no figure touched |
| `docs/INSTALLATION.md`, `docs/SERVER_BOOTSTRAP.md`, `docs/NUS-PORTABILITY.md` | Setup docs under the new name | ✓ VERIFIED | Fixed phrases present; NUS doc test passes |
| `CLAUDE.md` | Developer memory under the new name | ✓ VERIFIED | `# AILSA`, final skill paths, deck section says 8 slides / `ailsa-infographics.pdf`, credit row |
| `docs/infographics/build.py` + `deck.html` | Deck source and generated HTML | ✓ VERIFIED | In sync (rebuild changes nothing) |
| `docs/infographics/ailsa-infographics.pdf` | 8-page export | ⚠ PARTIAL | 8 pages, in sync with deck.html, but page 6 overflows its frame |
| `rdmo-project-description.txt`, `scripts/faulon-bridge/*` | Peripheral docs renamed | ✓ VERIFIED | Converter re-run with `--title "CASE13 AILSA"` reproduces `examples/CASE13.sml` byte for byte |
| `scripts/figshare_upload.py`, `scripts/zenodo_upload.py` | AILSA metadata + credit | ✓ VERIFIED | Title/description match the live record's content; source DOI linked as metadata |
| `105-check-outside-face.sh`, `105-check-cli-examples.py` | Phase gate | ✓ VERIFIED | Both green when run by the verifier |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| README Evaluation | BENCHMARK `#how-a-benchmark-run-executes` | absolute GitHub link + anchor | ✓ WIRED | Gate 5c/5d: anchor matches the heading, path tracked |
| ARCHITECTURE agent layer | BENCHMARK `#how-a-benchmark-run-executes` | relative link | ✓ WIRED | Gate 5b/5c |
| BENCHMARK execution section | ARCHITECTURE `#the-case-agent-layer` | relative link | ✓ WIRED | Gate 5c |
| build.py | deck.html | `python3 build.py` | ✓ WIRED | Gate 6a |
| deck.html | ailsa-infographics.pdf | headless Chrome print | ✓ WIRED (layout defect) | Fresh print gives identical text on all 8 pages; page 6 overflow is in the print layout |
| figshare paste text | live record | user edit in browser | ✓ WIRED | Live description carries every required element; `references` field left empty by the user (noted in 105-07-SUMMARY) |
| setup docs | `ailsa database info` "Schema version" | instruction | ✓ WIRED | Line exists in code and output |

### Data-Flow Trace (Level 4)

Not applicable — documentation phase; no component renders dynamic data. The equivalent check
(the deck's numbers trace to their sources) is under truths 4 and 12.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Outside-face gate | `bash .planning/phases/105-…/105-check-outside-face.sh` | 0 failing checks | ✓ PASS |
| CLI example audit | `python3 .planning/phases/105-…/105-check-cli-examples.py` | 155 invocations, 0 problems | ✓ PASS |
| NUS portability doc test | `/opt/miniconda3/bin/python -m pytest -q tests/nus/test_portability_doc.py` | 7 passed | ✓ PASS |
| README examples run | `ailsa read 1d`, `analyze symmetry`, `dereplicate c13`, `predict c13`, `pick hsqc`, `lsd check` on the local test data | all exit 0 | ✓ PASS |
| Documented imports resolve | exec of the 15 distinct import lines | 0 failures | ✓ PASS |
| Leaf commands without `--format` match the docs' exception list | Click tree walk | `database *`, `fragment build/info`, `lsd check`, `predict build-table`, `visualize correlations` — as README/CLAUDE.md state | ✓ PASS |
| PDF in sync with deck.html | fresh headless-Chrome print, per-page text compare | 8/8 identical | ✓ PASS |
| PDF pages fit their frame | PyMuPDF text-block scan vs footer line | page 6: text at y=480-512 below footer y=488 | ✗ FAIL |
| figshare live record | `curl https://api.figshare.com/v2/articles/31073554` | title/description/file/DOI as required | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` declared or present for this phase; the phase's own gate scripts were run above.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DOC-01 | 105-01, 105-09, 105-10 | README presents AILSA with the expansion; LSD and its author credited up front | ✓ SATISFIED | Truth 1 |
| DOC-02 | 105-01..05, 105-08, 105-09, 105-10 | docs/ and CLAUDE.md use the new names; no living doc instructs `lucy` | ✓ SATISFIED | Truths 2, 5, 6, 10 |
| DOC-03 | 105-07, 105-09, 105-10 | figshare title/description renamed; DOI and file unchanged | ✓ SATISFIED | Truth 3 |
| DOC-04 | 105-06, 105-09, 105-10 | Deck rebuilt under the new name with current numbers | ⚠ SATISFIED for build.py/deck.html; PDF page 6 defective | Truths 4, 12 |

No orphaned requirements: REQUIREMENTS.md maps exactly DOC-01..04 to Phase 105, and every one is claimed by a plan.

### Anti-Patterns Found

No TBD/FIXME/XXX/TODO markers in any file the phase modified.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| docs/infographics/build.py (→ PDF p. 6) | 507-545 | Print layout overflow | 🛑 Gap | Size-limit callout hidden, card 04 past the footer in the shared PDF |
| README.md | 16, 64 | "unattended" used for the agent team, while l. 245 says unattended (`claude -p`) runs form no team | ⚠️ Warning | Same word, two meanings; a careful reader sees a contradiction in exactly the place D-13a wants to be precise. Suggest "without human intervention" in l. 16/64 |
| docs/ARCHITECTURE.md | 42 | "every CLI command can emit structured JSON" | ⚠️ Warning | The same over-claim 105-09 corrected elsewhere (nine leaf commands have no `--format`); D-14 |
| README.md | 106-121 | ASCII diagram borders misaligned (coordinator box: border 54 chars, sides 56; devil's-advocate box: content 2 chars wider than border) | ⚠️ Warning | Ragged boxes on the front page and the future PyPI page; cosmetic |
| docs/infographics/build.py (slide 2) | — | "A multi-agent architecture prevents … the clean-but-wrong answer" stated as fact | ℹ️ Info | An unmeasured efficacy claim; not caught by the no-better-claim regex. The user may want "is designed to catch" |
| CLAUDE.md | 41 | `fragments/` described as "bundled LSD fragment / ring-exclusion filter files" | ℹ️ Info | The ring filters live in `lsd/filters/`; `fragments/` is the fragment-library module (ARCHITECTURE and README describe it correctly) |
| src/ailsa/cli/fragment.py, database.py, webview.py (help text) | — | `ailsa fragment build --help` shows examples with the legacy DB file name; `database info/download`, `fragment info`, `webview serve` help mention legacy names | ℹ️ Info | Code, outside this phase (D-12), but user-visible and not listed in deferred-items.md or any later requirement |
| docs/INSTALLATION.md, docs/SERVER_BOOTSTRAP.md | 245-249, 115-118 | "current schema" without the expected number | ℹ️ Info | A reader cannot tell whether "Schema version: N" is current; the local DB reports 7 |
| scripts/bootstrap_case_host.sh | — | README's recommended "fastest path" script still installs the old CLI alias, old skill paths and the legacy DB file name | ℹ️ Info | Allowed residue (D-12); will break when the alias is removed. No later requirement names this script explicitly — worth adding to the Phase 106 plan |

### Human Verification Required

### 1. Publish the outside face

**Test:** Push the Phase 105 commits and open https://github.com/steinbeck/ailsa (also follow the GitHub link in the live figshare description).
**Expected:** The front page shows the AILSA README; no old name.
**Why human:** Local master is 51 commits ahead of the last-fetched `origin/master` (9a39af4, 2026-10-12), whose README is the old-name version (82 mentions). Until the push, the public face — which the live figshare record now links to — still shows the old name. The repository is public, so pushing needs the user's go-ahead; the verifier did not contact the remote. Fixing the PDF gap first avoids publishing the broken page.

### Gaps Summary

The phase goal is achieved in the repository for README, docs, CLAUDE.md, the peripheral
documents, the figshare record and the deck source/HTML. Every roadmap success criterion holds,
the gate and CLI audit are green when re-run independently, and the prose checks the gate cannot
do (README intro, team-as-design, restricted configuration, BENCHMARK execution section, deck
slides 4/6/8, shift-source credit) read correctly.

One real defect remains: the committed PDF of the deck has a broken page 6. The print layout of
the benchmark slide is taller than the page, so the four method cards overlap the size-limit
callout and push past the footer. The figures themselves are right and the HTML is fine; the
fix is a layout tightening in build.py, a rebuild, a re-export, and ideally a page-fit check in
the gate so it cannot recur. Three wording issues (the double meaning of "unattended" in the
README, one remaining "every CLI command" JSON claim in ARCHITECTURE, the misaligned README
diagram) are warnings, not blockers.

---

_Verified: 2026-10-14T15:30:42Z_
_Verifier: Claude (gsd-verifier)_

## Re-verification after gap closure (2026-10-14)

- **Gap closed:** `2760233` lays out the four "How it is measured" steps of slide 6 as a 2x2 grid.
  Re-exported PDF: 8 pages; for every page the last text line is its footer (`AILSA · … 0N / 08`);
  page 6 viewed as an image: callout and all four steps above the footer, nothing overlaps.
- **Warnings addressed in the same commit:** README lines 16 and 64 now say "without human
  intervention" instead of "unattended"; `docs/ARCHITECTURE.md` names the text-only commands instead
  of claiming JSON output for every command (checked against `ailsa visualize --help`: only
  `correlations`, no `--format`).
- **Re-run:** outside-face gate 0 failing checks at `2760233`; CLI example audit 155 invocations,
  0 problems; `tests/nus/test_portability_doc.py` 7 passed.
- Still open and owned elsewhere: the README diagram alignment (cosmetic), the items under
  "Owned by later phases".
