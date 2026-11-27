---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 06
subsystem: skill
tags: [skill, restructure, lsd-reference, constraint-inventory, lsd-engineer]
requires: ["106-05"]
provides:
  - "references/lsd-reference.md and references/lsd-search.md: one shared LSD reference (one copy per fact), the union of the LSD engineer's and the diagnostic agent's command references"
  - "references/constraint-inventory.md: inventory format and build/update rules"
  - "LSD engineer passes every lint check (PENDING 13 -> 12)"
affects: [106-07, 106-08, 106-11]
key-files:
  created:
    - src/ailsa/skills/ailsa/references/lsd-reference.md
    - src/ailsa/skills/ailsa/references/lsd-search.md
    - src/ailsa/skills/ailsa/references/constraint-inventory.md
  modified:
    - src/ailsa/skills/ailsa/agents/ailsa-lsd-engineer.md
    - src/ailsa/skills/ailsa/INDEX.md
    - tests/skill_files.sha256
    - tests/test_skill_frontier.py
decisions:
  - "The merged reference had 517 lines, so it is split by topic: lsd-reference.md (syntax, commands, filter block, running LSD, checklist) and lsd-search.md (DUPL/MAXS, fragment goodlist, per-family search)"
  - "Ring exclusion stays with the filter block in lsd-reference.md, not in lsd-search.md as the plan listed: the one-FEXP rule ties the ring filters and the fragment filter together"
  - "The ELIM section is named 'ELIM escalation: tolerance for 4J correlations' so the name 'ELIM Escalation procedure' used by the devil's advocate, the solution analyst and case.md still points at it"
requirements-completed: [SKILL-05]
duration: 18min
completed: 2026-11-27
---

# Phase 106 Plan 06: Shared LSD reference and LSD engineer Summary

The LSD engineer's and the diagnostic agent's LSD command references are now one shared reference
in two files, one copy per fact. The constraint inventory has its own reference. The LSD engineer
went from 700 to 345 lines and passes the full lint. It reads three references at named workflow
steps. The diagnostic file keeps its copy until Plan 07.

## Commits

- `f632935` refactor: shared LSD reference merged from two copies (`lsd-reference.md` 390 lines,
  `lsd-search.md` 137 lines, both with a contents list). Section 1 of the LSD engineer is now a
  pointer. INDEX.md entries, manifest.
- `5322045` refactor: LSD engineer restructured, `constraint-inventory.md` (161 lines, contents
  list) created, ELIM heading renamed, PENDING minus one, INDEX.md entry, manifest.

## Verification

- Quick run (seven skill test files): 180 passed, 108 skipped (pending files), 1 xfailed. No skip
  for the LSD engineer or the three new references. Ruff is clean on the test file.
- `PENDING` has 12 entries; the LSD engineer is not among them.
- `ITERATION-COMPLETE` appears 18 times in the engineer. `CASE<n>` and `Phase <n>` appear 0 times
  in all four touched skill files.
- Inventory check for the old engineer file exits 0: 135 same, 104 reworded, 1 LOST. The LOST row
  is the completion-signal rule; its heading and reason paragraph are separate units in the new
  text, so it has the verdict `found`. Whole tree: 1509 same, 128 reworded, 5 LOST, all with
  verdicts. The reasons file has 68 entries, 9 of them with `reason_known=no`.
- 23 engineer rows carry the matcher's `negation?` flag. I checked each by hand. In every case the
  matcher paired the rule with a neighbouring unit, and the prohibition is present with the same
  polarity elsewhere in the new text.
- Diagnostic coverage check: in a scratch copy of the tree I cut the diagnostic's section 1 and
  rebuilt the inventory into a scratch folder. 7 diagnostic units came out LOST: six bare syntax
  lines and one filler example, all present in `lsd-reference.md`. Their verdicts
  (`merged-duplicate`) are already recorded for Plan 07.

## Disagreements between the two copies and how they were resolved

Line numbers refer to the old files (engineer = `lucy-lsd-engineer.md`, diagnostic =
`lucy-diagnostic.md`, tag `frontier-skill-pre-106`).

1. **Form of an equivalence COSY line.** Diagnostic 253 and the engineer's own table at 150 write
   it without a range. The engineer's rules at 178 and 200-204 require the explicit `3 3` range.
   The engineer's rule wins: the LSD manual says a COSY line with an explicit bond range is never
   eliminated, even with ELIM present. The table now shows the range.
2. **What PROP is for.** Diagnostic 204 lists "heteroatom attachment with ambiguous position".
   Engineer 139 allows LIST/ELEM/PROP for heteroatoms only when direct HMBC connectivity is
   established. The engineer's rule wins. PROP's uses are listed without the heteroatom case, and
   the text says the evidence rule decides heteroatom PROPs.
3. **ELIM's second field.** Diagnostic 276: "0 = no limit; recommended". Engineer 196: "P2=0
   always". The engineer's stronger form is kept. The manual confirms that 0 means no limitation.
4. **Error 250.** Diagnostic 101 quotes the error text; engineer 100 gives `exit 255`. These are
   complementary, not contradictory, and both are kept.
5. **Proton numbering in HSQC.** Diagnostic 91 says the proton number is "typically" the atom
   number. The engineer always writes `HSQC X X`. The manual calls identical numbers "generally
   useful (but not mandatory)". The skill convention (same number, one line per atom) stays.

## Deviations from Plan

1. **Split into two files.** The union came to 517 lines, so step 3 of Task 1 applied. Unlike the
   plan's list, ring exclusion stayed in `lsd-reference.md` (see decisions). Every fact appears in
   only one of the two files. The file-layout skeleton in `lsd-reference.md` lists the DUPL/MAXS
   lines; the rule and its reason are only in `lsd-search.md`.
2. **One fact added from outside the two section-1 copies.** Grouped HMBC notation may group only
   the carbon side; a grouped proton side aborts LSD with error 116. This comes from diagnostic
   530, advisory-templates 270 and commit `6a80d9e`. The plan names "grouped notation" as a topic,
   and the engineer's copy had only the example line.
3. **[Rule 1] ELIM heading renamed** to "ELIM escalation: tolerance for 4J correlations". The
   devil's advocate, the solution analyst and case.md cite the "ELIM Escalation procedure" by name.
   Their files are not touched.
4. **D-03 removals.** The dataset numbers and the compound story in the per-family section are
   gone; family names became A and B with atom numbers only. Also removed: the dataset, date,
   control compound and control formula in the HSQC verification note; the formula and fragment
   SMILES in the inventory example (now placeholders); and the diagnostic's formula example at 79.
5. **History removed:** dates (98, 110, 340), the multiplicity heading tag (213), the reload note
   (215-220, recorded in advance as `dropped-history`), plan and research pointers (279, 281,
   288), the fix tag (125, 139, 400), the bug number (606), the ISO timestamp in the inventory
   example, and the diagnostic's "Pitfall 1" pointer (289).
6. **Cross-file pointers.** The reference no longer points to the NMR chemist's Pitfall 6
   (engineer 137); the reason is stated inline, because a reference does not send readers on. In
   the core, the Pitfall 7 pointer (448) became a named reference ("the NMR chemist's pitfall on
   H-budget mismatch").
7. **Reasons added (D-02).** Batched HMBC lets a conflicting batch be traced and removed (from the
   adaptive loop and zero-solution recovery in the old text). The fragment file sits in the
   iteration folder so that its relative DEFF path resolves (from the old ring-filter paragraph).
   "Inject one fragment only" was changed back to "Do not inject more than one fragment" to keep
   the prohibition's polarity.
8. **Size.** The core is 345 lines, against a target of about 250. The message template, the
   workflow with its read lines and the HMBC strategy keep their full content.

## Notes for Phase 109

- The boundary says the LSD engineer does not rank or run `ailsa lsd rank`. The adaptive loop
  ("rank all solutions via ailsa lsd rank") and the union ranking in `lsd-search.md` tell it to.
  Both are kept as they were.
- Ring-BOND escalation says "log the decision in CASE-PROGRESS.md", but the engineer does not write
  that file. Kept as written.
- Diagnostic: "a protonated carbon without its HSQC line is treated as quaternary". MULT carries
  the H count, so this is probably about a missed HSQC peak that leads to a MULT with 0 H. Kept
  as written.
- `ailsa lsd run` produces `solutions.smi` automatically, yet large sets are "not converted". Kept.
- Constraint inventory, first iteration: "after writing ... to the file", then "a single Write
  operation". Kept.
- Workflow step 11 still says "determine the solver mode from the constraint inventory", although
  only one mode is left.
- Nine rules have `reason_known=no`: P2 is always 0; ranking runs across the union, not per family;
  ring exclusion goes into every file; no ELIM on the first run; inventory counts match the
  commands; the inventory is not written separately; the primary path runs first; ring-BOND
  forcing only as a documented escalation; ring-BOND as the only forcing mechanism, with no SKEL.

## Known Stubs

None.

## Self-Check: PASSED

The three reference files and the agent file exist. Commits `f632935` and `5322045` exist. Reasons
and verdicts are only in the private inventory folder, and nothing from it is staged. STATE.md and
ROADMAP.md are untouched.
