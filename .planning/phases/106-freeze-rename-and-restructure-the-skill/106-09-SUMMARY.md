---
phase: 106-freeze-rename-and-restructure-the-skill
plan: 09
subsystem: skill
tags: [skill, restructure, coordinator, references, model-disclosure, headless]
requires: ["106-08"]
provides:
  - "commands/case.md: coordinator core of 492 lines, 17 steps in run order, passes every lint check (PENDING 10 -> 9)"
  - "references/timing.md, monitoring.md, intervention.md, coordinator-gates.md, smoke-test.md: the moved step procedures, each read at its step"
  - "D-01 applied: spawn calls without a model argument; reported models recorded in Team Models, no comparison"
affects: [106-10, 106-11, 106.2]
key-files:
  created:
    - src/ailsa/skills/ailsa/references/timing.md
    - src/ailsa/skills/ailsa/references/monitoring.md
    - src/ailsa/skills/ailsa/references/intervention.md
    - src/ailsa/skills/ailsa/references/coordinator-gates.md
    - src/ailsa/skills/ailsa/references/smoke-test.md
  modified:
    - src/ailsa/skills/ailsa/commands/case.md
    - src/ailsa/skills/ailsa/references/progress-format.md
    - src/ailsa/skills/ailsa/INDEX.md
    - tests/skill_files.sha256
    - tests/test_skill_frontier.py
decisions:
  - "The step stubs put the section name after the Read line (`Read file: ... (section \"Diagnose\")`) to keep the core under 500 lines at the repo's 100-character wrap"
  - "References name core steps, never other references: the pointers from the coverage gate to the advisory templates and the loop patterns moved into the core stub, which reads advisory-templates.md itself"
  - "The headless caveat sits directly before the kick-off it governs (D-04 reorder); its content is unchanged"
  - "The progress-log heading for the G-IDENT entry stays `### Devils-Advocate (G-IDENT post-solution)` in backticks, matching the log's other devil's advocate headings until Plan 10 settles them"
requirements-completed: [SKILL-05]
duration: 25min
completed: 2026-11-27
---

# Phase 106 Plan 09: Coordinator split Summary

The coordinator went from 978 to 492 lines and passes the full lint. Timing, monitoring,
intervention, the two gates before the results and the smoke-test report are now five one-level
references. Each step keeps a stub in the core with its Read line, so the step order stays
visible: 17 steps, as before. Under D-01 the spawn calls carry no model argument. Each specialist
reports its runtime model in its first message, and the coordinator records those models and its
own. The intended model, the comparison and the mismatch warning are gone. The team flow, the
headless caveat and the web-view launch keep their content, and the web-view test passes
unchanged. No rule was lost.

## Commits

- `8bc80b5` refactor: coordinator steps moved into references. `timing.md` (98 lines; the
  finalize script is byte-identical), `monitoring.md` (285), `intervention.md` (154),
  `coordinator-gates.md` (93), `smoke-test.md` (27). The core keeps a stub per moved step, and
  the five references are added to INDEX.md and the manifest.
- `3ada517` refactor: coordinator restructured, model reported not compared. The core has a
  contents list of the steps in run order, D-01 is applied in `case.md` and in the Team Models
  block of `progress-format.md`, the emphasis is rewritten, and the history is removed. PENDING
  minus one, manifest.

## Verification

- Quick run (seven skill test files): 317 passed, 81 skipped (pending files), 1 xfailed. The lint
  for `case.md` (11 checks) and for the five references (50 checks) passes with no skip. Ruff is
  clean on the test file.
- `PENDING` has 9 entries, and `commands/case.md` is not among them. The answer scan passes with
  the coordinator no longer pending.
- Acceptance greps on `case.md`: 492 lines, 17 `<step name=` (the old file had 17), 14 Read lines
  into `references/`. `model=|MODEL MISMATCH|claude-opus` gives 0 in `case.md` and 0 in
  `progress-format.md`. `[MODEL]` appears 3 times, `Team Models` 2 times, "headless" 5 times, and
  `subagent_type="ailsa-` 4 times. `tests/test_case_md_wv07.py`: 5 passed, unchanged.
- Emphasis words by the lint's pattern outside code: 48 in the pre-plan file, 0 in the core and in
  all five references. The wide count (code included) went from 78 to 1, and that 1 is the
  `[RESEND-REQUIRED]` message tag, which stays as it is.
- Inventory check for the old coordinator (full, not lost-only) exits 0: 123 same, 110 reworded,
  7 LOST, all with verdicts (3 `found`, 2 `dropped-D01`, 1 `dropped-D03`, 1 `merged-duplicate`).
  The reasons file has 69 entries, 1 of them with `reason_known=no`. The tree-wide lost-only check
  and the full checks of all five agents are clean.
- I checked each of the 19 to 21 rows with the matcher's `negation?` flag by hand (the count moved
  between rebuilds). Every prohibition kept its polarity: "Do not attempt dereplication", "does not
  start on its own", "Create no further iteration tasks", "The run does not accept", and so on. The
  flag came from a wrong best match, not from a changed rule.

## Deviations from Plan

1. **[Rule 3, blocking] Line budget.** At the repo's wrap of about 100 characters, the first full
   rewrite came to 563 lines. To get under 500 without moving any planned core content out:
   - the stubs became three to six lines, with the section name after the Read line;
   - the paragraph in write_progress that repeated the kick-off's header rules (create the header
     at run start, the reason, the Dashboard field) now points to the kick-off, where all of
     those rules stand (verdict-free, matched as reworded);
   - each message type's required fields became one list item;
   - the shutdown list and the team-directory list became shorter.
2. **D-03 in parse_arguments.** The two example formulas became placeholders. The smoke-test
   defaults are removed: the default path pointed at a directory that is not in the repository,
   so the default never worked (the prerequisite check stops on a missing directory), and the
   default formula belonged to it. The smoke test now resolves `<compound_path> <formula>` like a
   normal run.
3. **D-03 in the ledger.** The two example multiplicity families became "each family with its
   CH₃/CH₂/CH partition", because the pair matched a benchmark story. Plan 05 had already removed
   the same pair from the shared multiplicity protocol.
4. **Carry-over from Plan 08: the devil's advocate triggers.** In the old DA file, the two
   dataset-numbered triggers were both G-IDENT triggers. The DA spawn prompt and the identity-gate
   push now state them as rules (an isomer name the data do not resolve; a recalled name whose ring
   linkage or symmetry does not match the drawn structure). The dead "Section 5" pointer became
   the gate's name. The multiplicity gate is named as G-MULT in the ledger and in the coverage
   gate, so both of the DA's gates are referred to by name and no dataset number remains.
5. **One-level references.** In `coordinator-gates.md`, the coverage gate no longer names the
   advisory templates or the loop-pattern file. The core stub names both and reads
   `advisory-templates.md` itself, because the gate runs before deliver_advisory_and_results.
   `intervention.md` names the template step (quality_convergence_advisory) instead of the file.
6. **No restatement of the loop patterns.** `monitoring.md` keeps only the two detection criteria
   that differ from `loop-patterns.md`: ELIM thrashing as runaway escalation (`elim_budget > 3`),
   and the guard that keeps Quality Convergence Failure from firing at zero solutions. The other
   quick criteria were word-for-word copies; the inventory matches each of them to the loop-pattern
   file, and none is LOST.
7. **Reorder in iteration management.** Relaying the DA decision now comes before "create the next
   tasks". The DA approves before the solver runs, and the old order suggested otherwise. The
   content is unchanged.
8. **`model=` literal.** The acceptance grep forbids `model=` in `case.md`, so the ledger names the
   DA's evidence message by its tag only. `coordinator-gates.md` keeps the full
   `[MULT-EVIDENCE-FOR] model=X` format.
9. **History removed:** the three reload notes (maintainer notes), the phase, ticket and decision
   IDs in the HTML comments and in the gate headings, the dataset numbers in the gate rationale,
   and the `skill/SKILL.md` section pointers in four advisory templates. The instructions behind
   those pointers stay. "UAT harness" became "benchmark harness".
10. **Terms.** "Orchestrator" became coordinator everywhere, including the Team Models line. The
    escalation report heading became "Coordinator Recommendation", and the smoke-test table rows
    use the role names. Teammate addresses are unchanged in code.
11. **Reasons added (D-02), from the old text or earlier reasons files:** the LSD engineer prompt
    ("constraints rebuilt from memory get dropped", Plan 06's reason), the sidecar search ("the
    conventions differ"), the push protocol ("what keeps a run from stalling"), the timing
    arithmetic (Python does it, so durations are not computed by hand), and the coverage gate's
    MAE rule (a wrong-class structure can score a low MAE), which replaces the dataset story.
12. **Inventory upkeep.** One devil's advocate row (its reload note) turned LOST because its best
    match, the coordinator's reload note, was removed. It got the verdict `dropped-history`, the
    same classification as in Plan 08.

## Notes for Phase 109

- detect_loops sends `solution_count <= 10` straight to present_results. The completion signals
  route the same case through ranking and both gates. Both are kept.
- On honest termination, track_and_decide says "Send to coordinator", but the coordinator is the
  reader. Kept as written.
- escalate ends with "stop", and terminate_team says it also runs after escalate. Both are kept.
- The ELIM pattern has two definitions: "ELIM added 2+ times" in the loop patterns and "runaway
  escalation, `elim_budget > 3`" in monitoring. Both are kept.
- No reason is recorded for "do not pass `--port` or `--open`" to the web-view call, neither in the
  old text nor in the commit that added it (`reason_known=no`). Phase 106.2 removes the block
  anyway.
- The HMBC-selection message says "avoid already-used ones" for what is really a prohibition.
  This was not an emphasised rule, so it is kept verbatim.

## Known Stubs

None. The step stubs in `case.md` are the intended form: each holds its Read line.

## Self-Check: PASSED

The five references and `case.md` exist. Commits `8bc80b5` and `3ada517` exist. Reasons and
verdicts are only in the private inventory folder, and nothing from it is staged. STATE.md and
ROADMAP.md are untouched.
