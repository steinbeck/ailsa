---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 10
subsystem: skill
tags: [skill, restructure, sanitise, db-credit, lint, answer-scan, changelog]
requires: ["106-09"]
provides:
  - "commands/sanitise.md: 494 lines with a contents list, placeholder examples, no answer-scan hit"
  - "commands/dereplicate.md, predict.md, help.md: the COCONUT shift credit sentence"
  - "references/advisory-templates.md, progress-format.md, loop-patterns.md: contents lists, plain rules, no history"
  - "tests/test_skill_frontier.py: PENDING empty, every lint check on every file"
  - "CHANGELOG 0.1.0: the restructure described, no chemistry rule changed"
affects: [106-11, 106-15, 106.2, 109]
key-files:
  created: []
  modified:
    - src/ailsa/skills/ailsa/commands/sanitise.md
    - src/ailsa/skills/ailsa/commands/dereplicate.md
    - src/ailsa/skills/ailsa/commands/predict.md
    - src/ailsa/skills/ailsa/commands/status.md
    - src/ailsa/skills/ailsa/commands/help.md
    - src/ailsa/skills/ailsa/references/nmr-basics.md
    - src/ailsa/skills/ailsa/references/advisory-templates.md
    - src/ailsa/skills/ailsa/references/progress-format.md
    - src/ailsa/skills/ailsa/references/loop-patterns.md
    - src/ailsa/skills/ailsa/CHANGELOG.md
    - tests/skill_files.sha256
    - tests/test_skill_frontier.py
decisions:
  - "Progress-log headings keep their hyphenated form (`### Devils-Advocate`, `### LSD-Engineer`, `### NMR-Chemist`, `### Solution-Analyst`) as format strings in fences and backticks; prose uses the role names. Only the coordinator's own heading in the diagnostic block changed from Orchestrator to Coordinator, matching every other block."
  - "The diagnostic spawn keeps `model=\"opus\"`: it is an alias, not a model ID, and D-01 covers IDs and the comparison only."
  - "One word in sanitise.md's list of generic labels is rephrased, because the private answer key uses that generic word as one dataset's name and the scan matches it as a whole word."
  - "PENDING mechanism kept (empty) so a file added later is skipped visibly and turns the completeness test into a strict xfail."
requirements-completed: [SKILL-05, SKILL-06]
duration: 16min
completed: 2026-11-27
---

# Phase 106 Plan 10: Remaining files and full lint Summary

The last nine files of the frontier skill are restructured and `PENDING` is empty: the lint runs
every check on every file (318 passed, 0 skipped, 0 xfailed), the answer scan finds no benchmark
answer in either packaged skill, and the inventory check over all old files exits 0. The
sanitise command lost its named examples (compound names, a CAS number, an InChI and InChIKey,
SMILES, dataset paths and naming patterns) to placeholders of the same shape, which removes both
of its answer-scan hits. Dereplicate, predict and help now credit the COCONUT shift source and say
which shifts are predicted and which measured. No rule was lost.

## Commits

- `269725a` refactor: sanitise command without real compounds. 499 to 494 lines with a contents
  list; 15 example units replaced by placeholders; the two dataset stories became the reason they
  illustrated; emphasis rewritten. PENDING minus one, manifest.
- `e9e7d83` refactor: small commands carry the DB credit. Credit sentence in dereplicate, predict
  and help; placeholder paths, formulas and shift lists; help lists itself; PENDING minus five,
  manifest.
- `d5d46ad` refactor: last references restructured, lint fully enforced. Advisory templates
  (387 to 395 lines), progress format (209 to 232), loop patterns (134 to 140), each with a
  contents list; PENDING set to `frozenset()`; CHANGELOG 0.1.0 completed; manifest.

## Verification

- Quick run (seven skill test files): 399 passed, 0 skipped, 0 xfailed. `test_case_md_wv07.py`
  passes unchanged (the `**Dashboard:**` field stays). Ruff is clean on the test file.
- `from tests.test_skill_frontier import PENDING; assert not PENDING` exits 0. Every skill file
  except CHANGELOG is under 500 lines.
- Answer scan run directly: frontier skill 31 files, lean skill 6 files, 0 datasets with a hit in
  each. The teaching-set name test passes over both skills.
- `grep -cE "CASE[0-9]"` on sanitise.md gives 0; `## Contents` appears once. `zenodo.6561449` is in
  dereplicate, predict and help; `pip install ailsa` and `data/reference/ailsa-derep.db` are in
  status.
- Capital-letter emphasis over the nine files, code included: 0 hits (`NOT` included).
- Inventory: `check` without `--files` exits 0. Whole tree: 1028 same, 556 reworded, 58 LOST, all
  58 with verdicts. This plan added 24 verdicts and filled 56 reasons rows, 1 of them with
  `reason_known=no`. The verdicts: 16 `dropped-D03` (15 sanitise example units, 1 dereplicate
  example), 6 `dropped-history` (2 reload notes in these references, plus 4 reload notes of the
  coordinator and the devil's advocate whose last match was one of those removed notes), and 2
  `found` (a reworded heading in sanitise, the dereplication separation in the advisory templates).
- The 18 rows with the matcher's `negation?` flag in these files were checked by hand: every
  prohibition kept its polarity ("Do not read or modify these", "Do not key this off MAE", "Do not
  let agents write this file", and so on); the flag came from a wrong best match.

## Deviations from Plan

1. **[Rule 1] Answer-key false positive in sanitise.md.** One dataset's name in the private key is
   a generic English word that the old list of generic labels used three times. The scan matches
   whole words, so the list now describes that label generically; the rule that generic labels
   are not redacted is unchanged.
2. **[Rule 1] Facts corrected while rewriting:** the InChIKey format illustration had one letter
   too many for the 27 characters the same line states (now 14-10-1); dereplicate's database
   figures ("~400K" and "~30K") now match the database (about 895K COCONUT and 33K NMRShiftDB
   entries); the advisory templates parse `**Started (UTC):**`, the field the header actually
   writes; the diagnostic spawn prompt says "per your agent definition" instead of "per your
   inlined knowledge", because that knowledge now lives in references the agent reads.
3. **[Rule 1] help.md frontmatter quoted.** The unquoted description contained `: ` ("Use when:
   which ..."), which is not a valid plain YAML value. help.md also lists `/ailsa:help` itself.
4. **Heading and step renames:** status's `check_lucy` step is now `check_ailsa`; loop patterns'
   heading "Five Loop Patterns" is now "Loop Patterns", since the file defines six; numbered
   pattern references ("Patterns 1-4", "Pattern 5") name the patterns.
5. **One-level references:** loop patterns no longer names the advisory template file; it names
   the multiplicity-coverage reopen advisory, which the coordinator core reads itself.
6. **Reasons added (D-02), from the old text or the commit history:** progress log sole writer
   (concurrent writes corrupt the file, from the planning text of the commit that introduced the
   protocol), append-only (loop detection reads the earlier iterations), no context timestamps
   (no time of day), the coverage advisory (a structure of the wrong multiplicity class can score
   a low MAE, replacing the dataset story), the reopen advisory's "do not reconstruct from scratch"
   (constraints rebuilt from memory get dropped, the reason recorded in an earlier plan), and the
   sanitise rules (binary files fail to read; a sanitisation that skipped the name fields left the
   name in place; the AI re-scan shares the first pass's blind spots).
7. **Kept as is:** the `[SUPERVISOR ADVISORY]` tags and their summary strings (message tags stay
   unchanged), the DA severity label in the progress-log field `**CRITICAL issues:**`, the
   `CCO` example in predict and help (an ethanol SMILES used as the CLI's syntax example, not a
   named, benchmark or teaching-set compound), and INDEX.md (no new reference file).

## Notes for Phase 109

- The diagnostic specialist is still spawned with `model="opus"`, while the four team specialists
  inherit the coordinator's model. Whether the escalation agent should be pinned is open.
- The progress format writes the solution analyst's section "only when solution_count <= 10 or
  as needed"; no reason is recorded for the threshold (`reason_known=no`).
- The progress-log headings still use the hyphenated role forms. Phase 106.2 replaces the log with
  the run record; any rename belongs there.
- The file-header trigger says "immediately after team spawns (before any agent messages)"; the
  coordinator core places it before the first `[BEGIN]` push. Both are kept.

## Known Stubs

None. The CHANGELOG's "counts to follow" and "result to follow" are placeholders for Plan 11 (the
inventory counts) and Plan 15 (the acceptance run), as the plan specifies.

## Self-Check: PASSED

The nine skill files, the CHANGELOG, the manifest and the test file exist and are committed in
`269725a`, `e9e7d83` and `d5d46ad`. Reasons and verdicts are only in the private inventory folder;
nothing from it is staged. STATE.md and ROADMAP.md are untouched.
