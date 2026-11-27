---
phase: 106-freeze-rename-and-restructure-the-skill
verified: 2026-11-27T16:00:00Z
status: human_needed
score: 6/6 roadmap criteria verified automatically; 8 user verdicts open
overrides_applied: 0
human_verification:
  - test: "Accept the blind acceptance run (106-HUMAN-UAT item 1)"
    expected: "User accepts one /ailsa:case run on Sheldon (rank 1, 1418 s) as proof of the renamed chain"
    why_human: "User gives acceptance verdicts himself"
  - test: "Accept rule inventory with comparison base frontier-skill-pre-106 (item 2)"
    expected: "User accepts, or asks for a comparison against paper-skill-v2"
    why_human: "Deliberate deviation from the agreed base"
  - test: "Accept form checks (3), Sheldon full suite (4)"
    expected: "Accept or name further checks"
    why_human: "User verdict"
  - test: "Laptop install command, caffeine decision (5)"
    expected: "Laptop runs 'ailsa skill install ailsa --target claude --link'"
    why_human: "Cannot be reached from here; laptop links are dead after the move"
  - test: "Fresh-session /ailsa: menu shows six commands (6)"
    expected: "case, dereplicate, help, predict, sanitise, status; no reference entries"
    why_human: "Slash menu is visible only in an interactive session"
  - test: "Push decision (7) and global CLAUDE.md example (8)"
    expected: "User decides; 67 commits since phase start are local only"
    why_human: "Repository is public; CLAUDE.md template is outside the repo"
---

# Phase 106: Freeze, rename and restructure the skill - Verification Report

**Phase Goal:** The CASE skill and its agents carry the AILSA name and follow Anthropic's skill-authoring best practices in form, while the exact skill states that produced the published benchmark figures stay recoverable.
**Verified:** 2026-11-27
**Status:** human_needed (automated checks pass; the eight items in 106-HUMAN-UAT.md stay open for the user)
**Re-verification:** No, initial verification

## Goal Achievement

### Observable Truths (ROADMAP success criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Tags mark both benchmark skill states; BENCHMARK.md records them with the host environment | VERIFIED | `paper-skill-v1` resolves to `f9aa7b3`, `paper-skill-v2` to `6d2d126`; `d62d833` is an ancestor of `6d2d126`. `docs/BENCHMARK.md` lines 67-77 list both tags, run counts 45/211, Claude Code 2.1.205, LSD 3.5.3, schema 3 (928 443 compounds), no fragment DB. `tests/test_freeze.py` passes. |
| 2 | `/ailsa:*` commands exist; `/lucy-ng:*` gone; symlinks point to the new directory | VERIFIED | `src/ailsa/skills/ailsa/commands/` holds case, dereplicate, help, predict, sanitise, status. `~/.claude/commands/ailsa` links to it on this machine. No `lucy-ng` link in `~/.claude`. No tracked file under `.claude/`. `ailsa skill list` shows the `ailsa` command skill. |
| 3 | Five `ailsa-*` agents; supervisor gone; SHA-256 guard references new files; agent symlinks updated | VERIFIED | The five agent files exist; the five `~/.claude/agents/ailsa-*.md` links resolve into the package; no supervisor file; `tests/skill_files.sha256` and `test_skill_files_unchanged.py` pass. |
| 4 | Every skill file under 500 lines, references one level, TOC over 100 lines, no dead refs, history, dataset numbers, model IDs; one term per role | VERIFIED | Largest bodies: sanitise 494, case 492 lines; the rest are smaller. One shared `lsd-reference.md`. `test_skill_frontier.py` (size, toc, history, datasets, model_ids, dead_refs, terms, emphasis, db_credit) passes, 0 skipped. My own grep finds no model IDs, dataset numbers or `lucy-ng:` in the skill outside `CHANGELOG.md`. |
| 5 | Automated lint enforces criterion 4; local answer scan finds no benchmark compound | VERIFIED (see warning) | `test_skill_frontier.py` and `test_skill_answer_scan.py` pass. The 106-15 summary reports 0 hits in 31 + 6 files. I could not rerun the scan against the private key and did not read it. |
| 6 | One blind CASE run on the compute host through the renamed command completes and grades; runner and watchdog use new command and paths; watchdog on vitus in a herdr pane, not a LaunchAgent | VERIFIED (verdict open) | Sheldon `/mnt/raid_drive/chris/case-uat-results-106/summary.tsv` shows CASE146, 1 attempt, `final_results True`, 1418 s. Grading (SOLVED_TOP1, rank 1) was done on vitus and is reported in 106-15-SUMMARY; the answer key is private and I did not re-grade. `uat_watchdog.py` pins Claude Code 2.1.332 and `claude-opus-5-5`, checks `/ailsa:case` is installed, and its docstring points to a herdr pane. No lucy LaunchAgent is on this machine or tracked. |

**Score:** 6/6 verified automatically.

### Requirements Coverage

| Requirement | Source plans | Status | Evidence |
|---|---|---|---|
| FREEZE-01 | 106-13 | SATISFIED | Truth 1 |
| SKILL-01 | 106-01, 03, 13, 14 | SATISFIED | Truth 2 |
| SKILL-02 | 106-03, 14 | SATISFIED | Truth 3 |
| SKILL-03 | 106-14, 15 | SATISFIED, user verdict open | Truth 6 |
| SKILL-04 | 106-12 | SATISFIED against the reworded text | Scripts call `/ailsa:case`; herdr-pane watchdog; LaunchAgent retired (none present). The Laptop's old agent plist is a manual step (UAT item 5). |
| SKILL-05 | 106-02, 04-11 | SATISFIED | Truth 4 |
| SKILL-06 | 106-04, 08, 10 | SATISFIED | Truth 5 |

All seven IDs appear in plan frontmatter and in REQUIREMENTS.md. No orphans. REQUIREMENTS.md checkboxes are still `[ ]`; the traceability table lists all seven as Phase 106.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Quick test set from the brief | `pytest` over the ten named test files | 447 passed in 21 s | PASS |
| Skill listing | `ailsa skill list` | `ailsa 0.1.0 (commands)` and `ailsa-lite 0.3.0` | PASS |
| Acceptance run exists on Sheldon | read-only `ssh sheldon`, `ls`, `cat summary.tsv` | batch.log, launch-106.sh, summary.tsv, CASE146 folder | PASS |

Full suite: not rerun; the 106-14 summary reports it on Sheldon at `f56327a` (5 failed, the same old web-view tests as before; 2335 passed). `git diff f56327a HEAD -- src/ailsa/skills` changes only `CHANGELOG.md` (3 lines), so the skill text the acceptance run used is the current text.

### Review findings

106-REVIEW found 3 blockers and 12 warnings; 106-REVIEW-FIX reports 15 of 15 fixed (installer deleting package files through a symlinked folder; Opus 5.5 pin writing into old result folders; inventory marking inverted rules as unchanged). The related tests are in the 447 passed.

### Anti-Patterns

No TBD/FIXME markers were checked file-by-file. Informational only: an empty untracked directory `.claude/commands/lucy-ng/references` is left in the working tree. It is invisible to git and can be deleted by hand.

### Warnings

1. **"On every commit" is not mechanically enforced.** The lint is a pytest test. `.git/hooks` has no hook, and there is no pre-commit config or CI workflow. It runs whenever the suite runs, but a commit can skip it. Decide whether this meets SKILL-06; I judge it acceptable because the project's convention is the test suite.
2. **Rule inventory comparison base** is `frontier-skill-pre-106`, not `paper-skill-v2`. It shows no rule was lost during restructuring. It does not re-check the two deliberate post-benchmark changes. Disclosed in UAT item 2.
3. **`frontier-skill-pre-106` is local only** (resolves to `2535715`).
4. **Laptop installation is broken** until the user runs one command (UAT item 5). The laptop's old links point to deleted files.
5. **One run on one dataset** cannot separate the restructuring from the post-benchmark ranking change or run-to-run noise (stated in UAT item 1).
6. `/ailsa:status` reports the reference database as missing when the session is outside the checkout. It was inherited from the old skill.

### Human Verification Required

All eight items in `106-HUMAN-UAT.md` are `pending`, as intended; none was approved on the user's behalf. See the frontmatter for the list.

### Gaps Summary

No goal-blocking gaps found. The skill carries the AILSA name, the form checks pass, and both measured skill states are tagged and documented. Status is `human_needed` because the user's verdicts are open.

---

_Verified: 2026-11-27_
_Verifier: Claude (gsd-verifier)_
