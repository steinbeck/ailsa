---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 02
subsystem: tooling
tags: [skill, rule-inventory, restructure-check]
requires: ["106-01"]
provides:
  - "scripts/skill_rule_inventory.py (build / todo / check) mapping old skill rules to the new tree"
  - "private inventory folder ~/Dropbox/develop/data/skill-rule-inventory-106 (inventory.tsv, pairs.tsv), baseline all same"
affects: [106-05, 106-06, 106-07, 106-08, 106-09, 106-10, 106-11, 106-15]
key-files:
  created: [scripts/skill_rule_inventory.py, tests/test_skill_rule_inventory.py]
requirements-completed: [SKILL-05]
completed: 2026-11-27
---

# Phase 106 Plan 02: Rule inventory tool Summary

A standard-library tool segments the old skill files into rule units (list items, table rows, normative sentences, code blocks), matches each to its best unit in the new tree (Jaccard plus a capped three-unit containment), and reports LOST rules and emphasis rules without a recorded reason. Old text is written only outside the repository; `--out` inside the work tree exits 2.

## Tasks

1. `feat(106-02)` commit `8c6fb14`: tool and 11 synthetic tests (12 after the fix), ruff clean, no `CASE<digit>` literal in either file.
2. Controls on the real old text (tag `frontier-skill-pre-106`, supervisor excluded): 1642 rule units from 15 files. Positive control (old tree against itself): same 1642, reworded 0, LOST 0, `check --lost-only` exit 0. Negative control (one list item deleted from the solution-analyst agent file, line 100): LOST 1, exit 1, exactly that id. Private default folder initialised (baseline all `same`); `git status` shows no inventory file.

Old units per file: devils-advocate 225, diagnostic 322, lsd-engineer 240, nmr-chemist 144, solution-analyst 88, case 240, dereplicate 19, lucy-ng (index) 13, predict 22, sanitise 150, status 17, references: advisory-templates 69, loop-patterns 41, nmr-basics 18, progress-format 34. Hints on the baseline: D01 6, D03 18, deadref 9, history 54, emphasis 406 (the 406 need reasons entries).

## Baseline deviation (for Plan 15 / the HUMAN-UAT verdict)

The inventory baseline is the phase-start tag `frontier-skill-pre-106`, not `paper-skill-v2` as decision D-06 says, because the skill files changed after `paper-skill-v2` in two deliberate commits (`9377d45` atom-by-atom ranking, `6a80d9e` LSD facts tested against LSD 3.4.9); Plan 15 carries this deviation into `106-HUMAN-UAT.md` for the user's verdict.

## Deviations from Plan

**1. [Rule 1 - Bug] Matcher too lenient on deleted rules** (commit `9670bcf`)
- Found during: Task 2 negative control. The first deleted item still matched as reworded through tokens scattered over neighbouring units; a 40-rule deletion sample showed 2 of 40 deleted rules even scoring `same` through such containment.
- Fix: containment-only scores are capped at 0.84 (`CONTAIN_CAP`), so only real Jaccard similarity can certify `same`; scattered matches become `reworded` and go to the meaning review. Test added.
- Residual: with deletion of single rules, about one in four becomes LOST and most of the rest `reworded` (the skill text repeats its vocabulary heavily). `same` after deletion now only arises from near-duplicate rules elsewhere (verdict `merged-duplicate`). So `reworded` rows must not be waved through: Plan 11 meaning review is the real gate for them.

**2.** `# ruff: noqa: E501` in both new files (long argparse/csv lines), instead of reflowing.

## Known Stubs

None.

## Self-Check: PASSED

Both files, commits `8c6fb14` and `9670bcf`, and the private `inventory.tsv` exist; STATE.md and ROADMAP.md untouched.
