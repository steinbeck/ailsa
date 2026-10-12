---
phase: 105
slug: documentation-and-outside-face
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-10-06
---

# Phase 105 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Docs-only phase: the "tests" are deterministic shell/Python checks, not pytest
> (see 105-RESEARCH.md § Validation Architecture).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — shell/grep checks + `python build.py` exit status |
| **Config file** | none |
| **Quick run command** | old-name allow-list grep on the file(s) touched by the task |
| **Full suite command** | allow-list grep over all in-scope files + relative-link check + `cd docs/infographics && python build.py` + CLI-example check |
| **Estimated runtime** | ~10 seconds (excluding `ailsa --help` snapshot) |

---

## Sampling Rate

- **After every task commit:** allow-list grep on the touched files
- **After every plan wave:** full suite
- **Before `/gsd:verify-work`:** full suite green, plus the manual prose checks below
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

To be filled by the planner per task. Requirement → check mapping:

| Requirement | Behavior | Test Type | Automated Command | File Exists | Status |
|-------------|----------|-----------|-------------------|-------------|--------|
| DOC-01 | README shows AILSA + expansion, LSD/Nuzillard in the first 50 lines, no old name, no Lucy lineage | grep | `rg -n -i 'lucy' README.md` → empty; `head -50 README.md \| grep -c Nuzillard` ≥ 1; `grep -c 'AI + LSD + Agents' README.md` ≥ 1 | ❌ W0 | ⬜ pending |
| DOC-02 | No living doc names the old project/CLI/commands; CLAUDE.md and docs/* renamed | grep | `rg -n -i 'lucy' README.md CLAUDE.md docs/*.md docs/infographics/README.md docs/infographics/build.py rdmo-project-description.txt scripts/faulon-bridge/README.md scripts/figshare_upload.py scripts/zenodo_upload.py` → only allow-listed lines (figshare file name `lucy-ng-derep.db.zip`, if referenced at all) | ❌ W0 | ⬜ pending |
| DOC-02 (accuracy, D-14) | Every retained `ailsa …` example uses an existing subcommand and existing flags; no MCP content | semi-automated | for each `ailsa <group> <cmd>` in README/docs: `ailsa <group> <cmd> --help` exits 0 and lists the used flags; `rg -n -i 'mcp' docs/INSTALLATION.md docs/ARCHITECTURE.md` → empty | ❌ W0 | ⬜ pending |
| DOC-02 (links) | Relative links in README/docs resolve after removals (D-11) | grep/fs | extract `](path)` targets without `http`, test each exists on disk | ❌ W0 | ⬜ pending |
| DOC-03 | figshare record shows new title/description; base DOI and file unchanged | manual checkpoint + curl | `curl -s https://api.figshare.com/v2/articles/31073554` → `title` contains AILSA; `files[0].id == 61078393` | n/a | ⬜ pending |
| DOC-04 | Deck rebuilds under the new name, 8 slides, consistent counters, current numbers | smoke | `cd docs/infographics && python build.py` exit 0; `grep -c -i 'lucy' deck.html` == 0; `grep -o '/ 0[0-9]' deck.html \| sort -u` → exactly `/ 08`; `grep -c '177' deck.html` ≥ 1 | ❌ W0 | ⬜ pending |
| D-13a (team as design) | README team section, ARCHITECTURE agent layer and deck team slide present the agent team with its direct channels | grep -F | each extract contains `specialists that coordinate with each other`, `direct review loop`, `ask the NMR chemist` (extracts: README `## The CASE Agent Team`..`## Running a CASE Elucidation`; ARCHITECTURE `## The CASE agent layer`; build.py `SLIDE 4 · AGENT TEAM`..`SLIDE 5`) | ❌ W0 | ⬜ pending |
| D-13a (restricted configuration) | Wherever the 69 % appear, the restricted configuration is stated | grep -F | README `## Evaluation`..`## Installation`, BENCHMARK `## How a benchmark run executes` section, build.py `SLIDE 6 · BENCHMARK`..`SLIDE 7` each contain `restricted configuration`, `without the agent team`, `without statistical detection` (slide 6: exactly one such line); every in-scope file containing `69.1` contains `restricted configuration`; INSTALLATION + SERVER_BOOTSTRAP contain `do not form a team` and `current schema` | ❌ W0 | ⬜ pending |
| D-13a (hub-and-spoke confined) | Hub-and-spoke only describes how benchmark runs executed | grep | `grep -l -i hub-and-spoke` over in-scope files → nothing or only docs/BENCHMARK.md, and all BENCHMARK matches lie inside `## How a benchmark run executes` | ❌ W0 | ⬜ pending |
| D-13a (no better-claim) | No sentence claims the full team system performs better than the benchmark figure | regex + positive control | `grep -n -i -E '(would\|could\|should\|will\|likely) (perform\|score\|do\|solve)[a-z]* (even )?(better\|higher\|more)\|perform(s\|ed)? (even )?better\|higher with the (agent )?team\|(full\|complete) (system\|team\|configuration) (achieves\|scores\|would\|performs\|solves)\|better with the (agent )?team\|lower bound\|underestimat\|conservative estimate' README.md docs/BENCHMARK.md docs/ARCHITECTURE.md docs/infographics/build.py docs/infographics/deck.html` → empty; planted sentence in a scratch copy fires | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Positive control for the old-name grep: plant `lucy-ng` in a scratch copy of one file and confirm the grep reports it (proves the pattern is not silently broken).
- [ ] Positive control for the no-better-claim regex: plant "With the agent team the full system achieves a higher rate." in a scratch copy of README.md and confirm the regex reports it.
- [ ] `ailsa --help` and per-group `--help` snapshot captured once to a scratch file, used by every doc-writing task.
- [ ] Relative-link check (filesystem only, no network).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Lucy lineage gone, no "formerly lucy-ng" note | DOC-01 (D-01/D-02) | prose — grep covers the word, not paraphrases | read README intro and deck slide 8 credits |
| Agent team described as the design; benchmark's restricted configuration stated honestly | D-13a (supersedes D-13) | prose correctness beyond the fixed-phrase greps | read README "The CASE Agent Team" + diagram, ARCHITECTURE "The CASE agent layer" and deck slide 4: team of specialists with the direct review loop (LSD engineer and devil's advocate) and requests to the NMR chemist, no hub-and-spoke star. Read README Evaluation, BENCHMARK "How a benchmark run executes" + Results, deck slide 6: wherever the 69 % appear, the restricted configuration is stated — no team (`claude -p` forms no teammates, specialists ran one at a time under the coordinator) and no statistical detection (outdated reference DB schema on the compute host). No claim that the full system performs better (Phase 110 measures that). Hub-and-spoke appears only as the description of how benchmark runs executed. Setup docs keep the agent-team flag as a requirement of the design. |
| Benchmark slide honest about the large-molecule limit, no compound identities | DOC-04 (D-06) | prose + public-repo rule | read the slide; compare figures with docs/BENCHMARK.md |
| figshare edit done by the user | DOC-03 (D-09) | no API token | user confirms; then run the curl check |
| Deletion list approved before any `git rm` | D-11/D-15 | user decision | user approves the list |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
