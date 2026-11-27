---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 07
subsystem: skill
tags: [skill, restructure, diagnostic, lsd-reference, references]
requires: ["106-06"]
provides:
  - "references/diagnose-zero-solutions.md: the five checks when LSD returns no solution"
  - "references/diagnose-solution-explosion.md: the five checks when LSD returns 1000+ solutions"
  - "references/diagnostic-report.md: DIAGNOSTIC-REPORT.md template and file name"
  - "diagnostic specialist passes every lint check (PENDING 12 -> 11) and reads the shared LSD reference"
affects: [106-08, 106-10, 106-11]
key-files:
  created:
    - src/ailsa/skills/ailsa/references/diagnose-zero-solutions.md
    - src/ailsa/skills/ailsa/references/diagnose-solution-explosion.md
    - src/ailsa/skills/ailsa/references/diagnostic-report.md
  modified:
    - src/ailsa/skills/ailsa/agents/ailsa-diagnostic.md
    - src/ailsa/skills/ailsa/INDEX.md
    - tests/skill_files.sha256
    - tests/test_skill_frontier.py
decisions:
  - "Nothing was added to lsd-reference.md: every fact of the diagnostic's inlined LSD copy was already in the shared reference (merged in Plan 06)"
  - "The equivalence-COSY fix example in the solution-explosion procedure now carries the explicit 3 3 range, the same resolution Plan 06 applied to the shared table"
  - "The report reference has no separate field-meaning section: the template's placeholders carry the meanings, and the confidence and priority definitions stay once, in the core's workflow steps 3 and 4"
requirements-completed: [SKILL-05]
duration: 12min
completed: 2026-11-27
---

# Phase 106 Plan 07: Diagnostic specialist split Summary

The diagnostic specialist, the largest skill file at 1 122 lines, now has a 288-line core that
passes the full lint. It no longer has its own LSD copy: it reads the shared `lsd-reference.md` at
the start of the diagnosis. The two systematic procedures and the report template are three
one-level references, each read at the workflow step that needs it. No rule was lost.

## Commits

- `2430cae` refactor: diagnostic procedures and report template as references. The inlined LSD
  section is dropped. The zero-solution procedure (258 lines), the solution-explosion procedure
  (271 lines) and the report template (120 lines) become references, each with a contents list.
  Read lines were added at steps 1, 2 and 5. INDEX.md entries, manifest.
- `8ebdeaf` refactor: diagnostic specialist restructured. Core of 288 lines with a contents list
  and a table naming the four references and the step that reads each. PENDING minus one,
  manifest.

## Verification

- Quick run (seven skill test files): 222 passed, 99 skipped (pending files), 1 xfailed. The lint
  for the agent and the three new references: 41 passed, no skip. Ruff is clean on the test file.
- `PENDING` has 11 entries; the diagnostic agent is not among them. The agent has 288 lines,
  `lsd-reference.md` is unchanged at 390.
- `grep "skill/\|SKILL\.md"` over the agent and the three references finds nothing. The agent has
  4 `references/...` read lines. In the four touched skill files, a grep for dataset numbers,
  dates, the bug tags, the old role name and the vendor finds nothing.
- Inventory check for the old diagnostic file exits 0: 154 same, 156 reworded, 12 LOST, all with
  verdicts (7 `merged-duplicate` recorded in Plan 06, 4 `found`, 1 `dropped-deadref`). In the
  whole tree, the lost-only check is clean: 1341 same, 284 reworded, 17 LOST. The reasons file has
  28 entries, 1 of them with `reason_known=no`.
- LSD coverage (step 2 of Task 1): after cutting the inlined section, only the 7 rows that Plan 06
  had already recorded came out LOST. The matcher paired many reworded units with unrelated
  neighbours, so I checked every fact of the old section by hand against `lsd-reference.md`. Each
  one is there (MULT, HSQC, HMBC, BOND/LIST/ELEM/PROP, equivalence, ELIM with its four warnings).
- 16 diagnostic rows carry the matcher's `negation?` flag. I checked each by hand. Every
  prohibition or negative fact has a counterpart with the same polarity, in the shared reference,
  in the two procedure references or in the core.

## Deviations from Plan

1. **No addition to the shared LSD reference.** Step 2 of Task 1 expected the facts missing from the
   shared file to come out LOST. None did: Plan 06 had already merged the union.
2. **[Rule 1, consistency] Equivalence COSY with range.** The symmetry fix example and the
   report's fix line in `diagnose-solution-explosion.md` now write `COSY 5 6 3 3`. The old example
   had no range, while the old diagnostic's own ELIM warning and the shared reference both say to
   write `COSY X Y 3 3` (Plan 06, disagreement 1).
3. **D-03.** The formula in the hydrogen-budget example became a placeholder ("`<formula>` with
   16 H"). The two example paths that used a real dataset name became
   `<dataset>` and `<dataset>/analysis/iteration_NN/compound.lsd`. The symmetry example names a
   generic "para-disubstituted benzene ring" only.
4. **History removed.** The test date on the HSQC/HMBC order note now reads "as tested against
   LSD itself". Also removed: the three bug tags in the inventory field list, the dated example
   file name (now `DIAGNOSTIC-REPORT-<timestamp>.md`), the nine `skill/...` pointers, the
   "Section 2.x" cross-references (now named) and the pointer to example reports that do not exist.
5. **Reason added (D-02).** `deff_not_patterns` "never decrease" now says why: a decrease means the
   ring-exclusion constraints were lost between iterations.
6. **Terms.** "Orchestrator" became coordinator everywhere, including the report's metadata field.
   The core's "advise the CASE agent" became "advise the team", because the single-agent term
   predates the team. The report template keeps its `CASE agent:` field unchanged.
7. **D-01.** The report's model line is now `**Specialist model:** <model reported by the
   specialist>`.
8. **Role line.** "You are called on escalation only" was added to the role. This is the agent's
   documented status (INDEX.md, plan), not a new rule.

## Notes for Phase 109

- The diagnostic (and the spawn prompt in `advisory-templates.md`) names inventory block "v1"
  and the fields `syme_pairs`, `elim_value` and `deff_not_patterns`. The LSD engineer writes v2,
  with `cosy_equiv_pairs` and `elim_budget`, and keeps `deff_not_patterns` empty (deprecated). The
  "should increase, never decrease" check therefore looks at a field that is always empty. Kept
  as written.
- The heteroatom check and option 2 of the quaternary check (solution-explosion procedure)
  recommend BOND or LIST/PROP constraints for unconstrained heteroatoms. The shared reference's
  evidence rule, which the DA's gate enforces, allows hard heteroatom constraints only with direct
  evidence or under the carbonyl exception. Kept as written.
- Step 1 still lists SYME among the commands to parse, although SYME is not native. Read as
  "detect a SYME line that should not be there". Kept.
- Rules 1-3 and anti-patterns 1-3 say the same things twice. Both lists are kept.
- One rule has `reason_known=no`: the warning when ELIM appears in iteration 1, before all HMBC
  lines are added. This matches Plan 06's entry for "no ELIM on the first run".

## Known Stubs

None.

## Self-Check: PASSED

The three reference files and the agent file exist. Commits `2430cae` and `8ebdeaf` exist.
Reasons and verdicts are only in the private inventory folder, and nothing from it is staged.
STATE.md and ROADMAP.md are untouched.
