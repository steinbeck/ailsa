---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 05
subsystem: skill
tags: [skill, restructure, multiplicity, solution-analyst, nmr-chemist]
requires: ["106-04"]
provides:
  - "references/multiplicity-ambiguity.md: one shared protocol, named by the NMR chemist, LSD engineer, devil's advocate, case.md and INDEX.md"
  - "NMR chemist and solution analyst pass every lint check (PENDING 15 -> 13)"
affects: [106-06, 106-07, 106-08, 106-11]
key-files:
  created: [src/ailsa/skills/ailsa/references/multiplicity-ambiguity.md]
  modified:
    - src/ailsa/skills/ailsa/agents/ailsa-nmr-chemist.md
    - src/ailsa/skills/ailsa/agents/ailsa-solution-analyst.md
    - src/ailsa/skills/ailsa/agents/ailsa-lsd-engineer.md
    - src/ailsa/skills/ailsa/agents/ailsa-devils-advocate.md
    - src/ailsa/skills/ailsa/commands/case.md
    - src/ailsa/skills/ailsa/INDEX.md
    - tests/skill_files.sha256
    - tests/test_skill_frontier.py
decisions:
  - "The multiplicity reference ends with a short 'Who uses the record' section (coordinator ledger and coverage gate, LSD engineer per-family runs, DA multiplicity gate), as the plan asked for all readers; it restates rules that stay in their owners' files"
  - "Section numbers dropped from the headings of both agents; cross-references name the heading"
requirements-completed: [SKILL-05]
duration: 12min
completed: 2026-11-27
---

# Phase 106 Plan 05: NMR chemist, solution analyst and the shared multiplicity reference Summary

The aliphatic multiplicity-ambiguity protocol now lives in one reference that all four readers
name. The NMR chemist (450 -> 399 lines) and the solution analyst (328 -> 349 lines, plus contents
list and database paragraph) pass the full lint. Both inventory checks exit 0.

## Commits

- `6e0d468` refactor: NMR chemist restructured, `references/multiplicity-ambiguity.md` (102 lines,
  with contents list) created, three pointers repointed (LSD engineer, devil's advocate, case.md;
  only the pointer text changed in those files), INDEX.md entry, PENDING minus one, manifest.
- `5439738` refactor: solution analyst restructured, reference database paragraph with the
  credit sentence, PENDING minus one, manifest.

## Verification

- Quick run (seven skill test files): 138 passed, 117 skipped (pending files), 1 xfailed; no
  skipped test for the two agents or the new reference. Ruff clean on the test file.
- `PENDING` has 13 entries. Neither agent file is in it.
- Inventory, private folder: whole tree 1614 same, 24 reworded, 4 LOST. All 4 LOST belong to the
  two old files and have the verdict `found`. Reasons entries: 48 for the NMR chemist (2 with
  `reason_known=no`), 25 for the solution analyst (1 with `reason_known=no`).
- `grep -cE "CASE[0-9]"` on the solution analyst: 0; `zenodo.6561449`: 1.
- `grep -rln "references/multiplicity-ambiguity.md"` lists the NMR chemist, LSD engineer, devil's
  advocate, case.md and INDEX.md.

## Deviations from Plan

1. **Acceptance grep for `nmr-chemist\.md` cannot print nothing.** Its only hit is INDEX.md line
   25, the link `agents/ailsa-nmr-chemist.md`. `test_index` requires INDEX.md to link every file,
   so the line stays. No `Section 5b` remains anywhere.
2. **[Rule 2, D-03] Concrete accession code removed.** The solution analyst gave a real COCONUT
   accession as an example. An accession names a compound, so it now reads "a code of the form
   `CNPxxxxxxx`".
3. **[D-02] One anecdote sentence dropped.** In the solution analyst, the sentence saying that a
   blind test put the right structure first with atom-by-atom ranking was removed. The reason
   stays (a wrong structure borrows experimental lines of other atoms), and so does the rule (the
   atom-by-atom ranking decides).
4. **[D-03] Example family names gone.** The worked example with two named multiplicity
   families (a benchmark story) is gone. The record template uses `<family name>` with atom-number
   multiplicities. case.md and the LSD engineer still use those two family names in their
   examples; their own plans remove them.
5. **Maintainer reload notes dropped** (HTML comments with history) in both agents. The same fact
   (a fresh session is needed after an edit) stays in the repo CLAUDE.md. Verdicts are entered in
   advance as `dropped-history`, because the identical notes in other files still match today.
6. **Inventory artefact.** Taking out an emphasis word can leave a sentence with no normative
   word, and then the segmenter does not count it as a rule unit. It shows up as LOST although the
   text is still there. That accounts for all 4 LOST rows, each recorded as `found` with its new
   file:line. In the multiplicity reference, one sentence was changed to an imperative ("list
   both") so that it keeps the form of an instruction.

## Notes for Phase 109

- The multiplicity trigger reads "(a) non-edited HSQC and/or (b) unreliable APT/DEPT". It also
  says `multiplicity_edited: false` is "necessary but not sufficient", which implies (b) alone does
  not trigger. Kept exactly as it was. The meaning needs a decision.
- Three rules with `reason_known=no`: always run hybridisation/neighbour detection in the listed
  ranges; always run the hetero-hetero-bond check for 2+ heteroatoms; the literal
  `(tentative, unverified)` marker plus confidence note.

## Known Stubs

None.

## Self-Check: PASSED

The reference file and both agent files exist. Commits `6e0d468` and `5439738` exist. Reasons and
verdicts are only in the private inventory folder, and nothing from it is staged. STATE.md and
ROADMAP.md are untouched.
