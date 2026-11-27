---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 08
subsystem: skill
tags: [skill, restructure, devils-advocate, validation, references, blindness]
requires: ["106-07"]
provides:
  - "references/validation-checks.md: the devil's advocate's pre-solver checks, each named by what it checks, with severity"
  - "references/inventory-validation.md: inventory extraction, reconciliation checks, ELIM budget, the gates G7 and G-PROP-EVIDENCE, detection coverage"
  - "devil's advocate passes every lint check (PENDING 11 -> 10) and the answer scan now covers it"
affects: [106-09, 106-10, 106-11]
key-files:
  created:
    - src/ailsa/skills/ailsa/references/validation-checks.md
    - src/ailsa/skills/ailsa/references/inventory-validation.md
  modified:
    - src/ailsa/skills/ailsa/agents/ailsa-devils-advocate.md
    - src/ailsa/skills/ailsa/INDEX.md
    - tests/skill_files.sha256
    - tests/test_skill_frontier.py
decisions:
  - "Nothing was added to lsd-reference.md: every LSD fact the checks restated was already in the shared reference"
  - "The G-MULT severity class is written as the label `mandatory-search` in backticks, like `CRITICAL`, `WARNING` and `INFO`; the word binding stays in lower case in prose"
  - "The three gate tables (pre-run, post-solution, pre-accept) stay in the core with the two gates that have their own lifecycle; G7 and G-PROP-EVIDENCE run with the inventory checks and their procedures moved to inventory-validation.md"
requirements-completed: [SKILL-05, SKILL-06]
duration: 13min
completed: 2026-11-27
---

# Phase 106 Plan 08: Devil's advocate split Summary

The devil's advocate went from 680 to 399 lines and passes the full lint. Its check list and its
inventory validation are now two one-level references. It reads them with the shared LSD
reference at workflow step 2, so it no longer restates LSD syntax. The gates G-IDENT and G-MULT
stay in the core with their lifecycle, severity and closure rules; their triggers are stated as
rules without dataset numbers or compound names. The worked example that de-blinded a benchmark
dataset is gone, and the answer scan, now enforced for this file, finds nothing. No rule was lost.

## Commits

- `811c843` refactor: devil's advocate checks as references. `validation-checks.md` (268 lines)
  holds the six checks for known failure modes (renamed from the numbered bug headings to what
  each checks) and the eleven structural integrity checks. `inventory-validation.md` (280 lines)
  holds the extraction, the five reconciliation checks with G7 and G-PROP-EVIDENCE, the detection
  coverage and the inventory-based form of the checks. Both have a contents list. Read lines added
  in the agent, INDEX.md entries, manifest.
- `83ef3e6` refactor: devil's advocate restructured. Core of 399 lines with a contents list and a
  table naming the four references and the step that reads each. PENDING minus one, manifest.

## Verification

- Quick run (seven skill test files): 253 passed, 90 skipped (pending files), 1 xfailed. The lint
  for the agent and both references passes with no skip. Ruff is clean on the test file.
- `PENDING` has 10 entries; the devil's advocate is not among them.
- Answer scan (`tests/test_skill_answer_scan.py -rs`): 3 passed, with the devil's advocate no
  longer pending. The teaching-set check in the same module passes as well.
- Emphasis words by the lint's own pattern, outside code and backticks: 104 in the old file, 0 in
  the core and in both references. `CASE<n>`, the numbered bug headings, ticket and decision IDs,
  dates and "Section n" appear 0 times in the three files. `G-IDENT` appears 12 times and `G-MULT`
  7 times in the core; "devil's advocate (DA)" once.
- Inventory check for the old devil's advocate exits 0: 110 same, 110 reworded, 5 LOST, all with
  verdicts (4 `found`, 1 `dropped-D03`). The reasons file has 112 entries, 3 of them with
  `reason_known=no`. In the whole tree the lost-only check is clean (23 LOST, all with verdicts).
- 20 rows carry the matcher's `negation?` flag. I checked each by hand: every prohibition kept its
  polarity ("Do not modify", "Do not fold", "does not close it", "the run does not accept").
- One LSD engineer row came out LOST during this plan. Its best match had been the deleted worked
  example. The rule is in `lsd-search.md:75-77` and got the verdict `found`.

## Deviations from Plan

1. **No addition to the shared LSD reference.** The HSQC order, the duplicate-HSQC abort, the
   heteroatom-proton declaration, ELIM and the single filter expression were all in
   `lsd-reference.md`. The DA's copies were cut down to what it verifies.
2. **[Rule 1, bug] Inventory extraction snippet.** The `else` branch of the shell snippet held
   only comments, which is a bash syntax error. It now also prints
   `BLOCK: Inventory validation failed: $ERRORS`. The behaviour it describes is unchanged.
3. **D-03.** The G-IDENT triggers are rules: "a specific isomer name asserted where the
   regiochemistry is not resolved by the data" and "a recalled trivial name whose ring linkage or
   symmetry does not match the drawn structure", each with a generic illustration. The dataset
   numbers and compound names in the rationale and in the gate table are gone. The G-MULT worked
   example and the defeat story are deleted. The reason is kept in one sentence: a flag argued
   away left the correct family unsearched. The general rule against re-explaining the correlation
   is kept. The correlation in the `[MULT-EVIDENCE-FOR]` template became the placeholder
   `HMBC X→Y`, because the old atom numbers came from the removed example. The generic canonical
   case (a CH₃–CH₂ pairing) stays.
4. **History removed.** The maintenance note and the reload note (both maintainer notes, verdict
   type `dropped-history`), the numbered bug headings and the "Bug n" pointers, the test date on
   the HSQC order and on the filter position, the decision and requirement IDs in the gate headings
   and purpose lines, and the ticket tag in G-PROP-EVIDENCE (also inside its message template).
5. **Cross-file pointers.** The H-budget hint no longer names the NMR chemist's pitfall number; the
   hint itself ("check whether a heteroatom OH or NH is missing") stays. The aromatic check names
   "the NMR chemist's subsection of `## Setup`" instead of the progress-format heading, which may
   be renamed in a later plan. The G7 text names "before running the solver" instead of the LSD
   engineer's step number. Section and check numbers became names.
6. **Reasons added (D-02), all from the old text:** the ring exclusion row in the diff table
   (strained-ring solutions survive), sp2 parity (each double bond joins two sp2 atoms), the
   boundaries (the DA is the independent check between building and solving), and "use the CLI
   validator" (it tells a legacy, a missing and a malformed block apart, as its own branches show).
   The bug stories became one "Why" line per check.
7. **Workflow.** Step 8a became step 9, and steps 9 to 13 became 10 to 14. No other file cites a
   DA step number. Step 6 now says "among them" before its six items. The reference states that
   all eleven structural checks apply to every file, and the old step listed only six.
8. **Terms.** "Orchestrator" became coordinator, "Devils-Advocate" is gone, and teammate names in
   prose became NMR chemist, LSD engineer and solution analyst. The quoted aromatic warning now
   says "The solution analyst should flag it" instead of the hyphenated role name.
9. **Size.** The core has 399 lines, against a target of about 300. The three gate tables, the
   full G-IDENT and G-MULT texts and the two message templates keep their content.
10. **Lifecycle sentence.** The old G-IDENT text said every other gate runs before the solver,
    which was no longer true once G-MULT (pre-accept) existed. It now says "the pre-run gates run
    on `compound.lsd`". No rule changed.

## Notes for Phase 109

- A missing ring exclusion block is `CRITICAL` in the ring exclusion check but `WARNING` in the
  badlist completeness check. Both are kept.
- A decrease in HMBC lines is `WARNING` in the count comparison table but `CRITICAL` in the
  no-regression check. Both are kept.
- The detection-constraints check asks for PROP/LIST for detected mandatory neighbours (for example
  C-O at 50-90 ppm). G-PROP-EVIDENCE blocks a hard heteroatom PROP that rests on detection alone.
  Both are kept.
- G7 relies on the LSD engineer checking the hash before the solver runs. Neither the old nor the
  new LSD engineer file has that step, and the coordinator's `[DA-APPROVED]` relay carries no
  hash. The check is therefore not performed today. Kept as written.
- `case.md` (still pending) tells the DA in its spawn prompt and its G-IDENT request to apply the
  old worked triggers by dataset number and points to a "Section 5". The core now states the two
  triggers as rules, so the plan that restructures `case.md` should point to them by name.
- Three rules have `reason_known=no`: the ELIM warning in iteration 1 (two places, the same rule
  as in Plans 06 and 07) and the `CRITICAL` for a missing fragment file.

## Known Stubs

None.

## Self-Check: PASSED

The two reference files and the agent file exist. Commits `811c843` and `83ef3e6` exist. Reasons
and verdicts are only in the private inventory folder, and nothing from it is staged. STATE.md and
ROADMAP.md are untouched.
