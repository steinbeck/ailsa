# Monitoring a CASE run

How the coordinator drives the run after the kick-off: it reacts to each teammate reply, pushes the
next `[BEGIN]` directive, decides when to iterate, rank or stop, and watches the iteration history
for unproductive loops. The monitor_progress, detect_loops and diagnose steps use this file; the
definitions of the five loop patterns are read with it.

The devil's advocate (DA) validates every LSD file before the solver runs and reviews the reported
name after the ranking.

## Contents

- The monitoring loop
- Push iteration 1
- Stall recovery
- Smoke test early exit
- Completion signals and the gates before results
- Iteration management
- Detect loops
- Diagnose

## The monitoring loop

Teammate replies arrive as SendMessage notifications, that is as conversation turns that wake you.
TaskList is read only as a status ledger: the workflow advances because you push the next
`[BEGIN]` directive after each reply, never because a teammate polls.

Before processing any structured message, run validate_message to check its required fields.

**Shift list retention:** when processing [SETUP-COMPLETE] from the NMR chemist, extract and retain
the experimental 13C shift list (comma-separated ppm values). The ranking tasks need it later.

**Loop:** receive structured messages from teammates (they arrive as conversation turns),
optionally read `TaskList()` for status, and read `<compound_path>/analysis/CASE-PROGRESS.md` for
loop detection. On each structured message ([SETUP-COMPLETE], [ITERATION-COMPLETE],
[VALIDATION-PASSED], [VALIDATION-BLOCKED], [RANKING-COMPLETE]): take the `phase_end` timing stamp
first, then write the corresponding section to CASE-PROGRESS.md per write_progress, then take a
`phase_start` stamp for the next step and push its `[BEGIN]` directive to whichever agent owns it,
then continue monitoring. Timing invariant: every `[BEGIN]` you push is preceded by a
`phase_start`; every completion reply you receive gets its `phase_end` before anything else.

**Parse from CASE-PROGRESS.md:** solution count per iteration, constraints added and removed, sp2
checks, H budget status, HMBC correlations used (X/Y), last iteration number.

## Push iteration 1

This push is due right after [SETUP-COMPLETE]. The lsd-iteration-01 task created at spawn does not
start on its own: immediately after writing the Setup section, push the LSD engineer:

```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[BEGIN] lsd-iteration-01 — peak assignments are ready (see analysis/CASE-PROGRESS.md ## Setup). Build the initial LSD file in analysis/iteration_01/ (MULT from HSQC, first 3-5 HMBC), request DA validation, run the solver. Send [ITERATION-COMPLETE] with the solution count the instant the solver exits; do not block it on SMILES conversion (skip conversion if the count is large). Ending your turn after a solver run without [ITERATION-COMPLETE] hangs the whole run.",
  summary="Kick off LSD iteration 1"
)
```

## Stall recovery

This is the self-rescue for a missing [ITERATION-COMPLETE] when you are woken. The primary defence
is the LSD engineer sending [ITERATION-COMPLETE] the instant the solver exits, which every
lsd-iteration directive repeats. As a backstop: whenever you are woken for any reason (another
teammate's message, a user nudge) and an lsd-iteration directive is still outstanding with no
[ITERATION-COMPLETE], do not wait passively again. Check the filesystem directly: if
`analysis/iteration_NN/solncounter` (or a `*.sol` file) exists and no LSD process is running, the
solver has already finished and the engineer stalled before signalling. Read the solution count
from `solncounter` yourself, write the [ITERATION-COMPLETE] section to CASE-PROGRESS.md from the
filesystem, and resume the workflow by pushing the next directive. This turns an indefinite hang
into an immediate recovery.

## Smoke test early exit

If SMOKE_TEST is true, track these checkpoints as they arrive:
- [ ] [SETUP-COMPLETE] received from the NMR chemist (peak picking done)
- [ ] [ITERATION-COMPLETE] received from the LSD engineer (LSD file built and run)
- [ ] [VALIDATION-PASSED] or [VALIDATION-BLOCKED] received from the DA

When all three checkpoints are complete, or any checkpoint fails with an error or a timeout after
5 minutes:
- Create no further iteration tasks.
- Do not proceed to ranking.
- Proceed directly to the smoke_test_report step.

## Completion signals and the gates before results

**Completion signals (normal mode only, when SMOKE_TEST is false):**
- solution_count <= 10 → ranking → coverage_gate (when ambiguous) → identity_gate
- [RANKING-COMPLETE] received → coverage_gate (when ambiguous) → identity_gate (post-solution
  G-IDENT review) → present_results
- 10 iterations reached → ranking → coverage_gate (when ambiguous) → identity_gate →
  present_results with caveats
- the DA flags an issue → detect_loops

**Do not go straight from [RANKING-COMPLETE] to present_results or terminate_team.** Once
`analysis/final_results.md` exists, the run is not done until (a), when a `[MULTIPLICITY-AMBIGUOUS]`
record exists, the pre-accept coverage_gate step has passed, and (b) the post-solution
identity_gate step has run (the DA's independent G-IDENT cross-check of name and structure). The
coverage_gate runs first, because it can reopen the run to search a missing family; only once it
passes does identity_gate run. Skipping identity_gate silently drops the independent advisory
layer, so a recalled name that does not match the structure goes out unchallenged; skipping
coverage_gate silently accepts a run in which a viable multiplicity family was never searched.

## Iteration management

**Relay the DA decision.** After writing the DA section to CASE-PROGRESS.md, relay the approval
decision to the LSD engineer.

If [VALIDATION-PASSED] was received:
```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[DA-APPROVED] Iteration {N} — Validation passed. Proceed with solver run.
           DA findings: {brief summary from [VALIDATION-PASSED] message}",
  summary="DA approved iteration {N} — proceed with solver"
)
```

If [VALIDATION-BLOCKED] was received:
```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[DA-BLOCKED] Iteration {N} — Validation blocked. Critical issues:
           {issues from [VALIDATION-BLOCKED] message}
           Fix these before running solver.",
  summary="DA blocked iteration {N} — fix required"
)
```

**Create the next tasks.** After receiving [ITERATION-COMPLETE] from the LSD engineer and
[VALIDATION-PASSED] or [VALIDATION-BLOCKED] from the DA, and after writing both sections to
CASE-PROGRESS.md:

1. Extract solution_count from the [ITERATION-COMPLETE] message.
2. Run detect_loops.
3. **If no loop, solution_count > 10 and iterations < 10 (safety cap):**

   Use the shift list retained from [SETUP-COMPLETE]. The coordinator wrote it to the NMR
   chemist's subsection of `## Setup` in CASE-PROGRESS.md; read it from there if needed.

   Create the next iteration task:
   ```
   TaskCreate(
     subject="lsd-iteration-{next_iter:02d}",
     description="Build LSD file for iteration {next_iter} of {formula} at {compound_path}.
                  Read previous: analysis/iteration_{current_iter:02d}/compound.lsd
                  Use constraint inventory to copy all constraints forward.
                  Add next HMBC batch (3-5 correlations, best remaining from CASE-PROGRESS.md Setup).
                  Send validation request to the devil's advocate.
                  Wait for approval before running solver.
                  Run LSD from analysis/iteration_{next_iter:02d}/.
                  Send [ITERATION-COMPLETE] to coordinator.",
     activeForm="LSD iteration {next_iter}"
   )
   ```

   Then push it at once; the LSD engineer is idle and does not pick it up on its own:
   ```
   SendMessage(
     type="message",
     recipient="lsd-engineer",
     content="[BEGIN] lsd-iteration-{next_iter:02d} — build iteration {next_iter} now: read analysis/iteration_{current_iter:02d}/compound.lsd, carry all constraints forward, add the next HMBC batch, request DA validation, then run the solver. Send [ITERATION-COMPLETE] with the solution count the instant the solver exits; do not block it on SMILES conversion (skip conversion if the count is large). Ending your turn after a solver run without [ITERATION-COMPLETE] hangs the whole run.",
     summary="Kick off LSD iteration {next_iter}"
   )
   ```

   **Parallel task creation (when solution_count is 10-50 and iterations >= 2):** also create an
   HMBC selection task for the NMR chemist:
   ```
   TaskCreate(
     subject="hmbc-selection-{next_iter:02d}",
     description="Select next HMBC batch (3-5 correlations) for iteration {next_iter}.
                  Review CASE-PROGRESS.md for already-used correlations.
                  Apply selection criteria: isolated carbons, unique protons, strong intensity.
                  Send selected batch to lsd-engineer via SendMessage.",
     activeForm="Selecting HMBC batch {next_iter}"
   )
   ```

   Then push it at once to the NMR chemist:
   ```
   SendMessage(
     type="message",
     recipient="nmr-chemist",
     content="[BEGIN] hmbc-selection-{next_iter:02d} — select the next 3-5 HMBC correlations now (avoid already-used ones in CASE-PROGRESS.md) and send the batch to lsd-engineer.",
     summary="Kick off HMBC selection {next_iter}"
   )
   ```

4. **If solution_count <= 10:**

   Read the shift list from the NMR chemist's subsection of `## Setup` in CASE-PROGRESS.md (the
   13C peak positions written from [SETUP-COMPLETE]).

   Create the ranking task with the shifts embedded:
   ```
   TaskCreate(
     subject="ranking-iteration-{current_iter:02d}",
     description="Rank LSD solutions from iteration {current_iter}.
                  LSD input: analysis/iteration_{current_iter:02d}/compound.lsd
                  solutions.smi path: analysis/iteration_{current_iter:02d}/solutions.smi
                  Experimental 13C shifts: {shift_list}
                  Run (decides): ailsa lsd rank --assigned analysis/iteration_{current_iter:02d}/compound.lsd
                  Cross-check: ailsa lsd rank analysis/iteration_{current_iter:02d}/solutions.smi --shifts '{shift_list}'
                  Assess chemical plausibility of top candidates.
                  Write analysis/final_results.md with full report.
                  Send [RANKING-COMPLETE] to coordinator.",
     activeForm="Ranking LSD solutions"
   )
   ```

   Then push it at once to the solution analyst. Embed the shift list and the path in the message,
   so that the analyst never needs the TaskList:
   ```
   SendMessage(
     type="message",
     recipient="solution-analyst",
     content="[BEGIN] ranking — rank solutions now. LSD input: analysis/iteration_{current_iter:02d}/compound.lsd (rank atom by atom with --assigned; this decides) ; solutions.smi: analysis/iteration_{current_iter:02d}/solutions.smi ; experimental 13C: {shift_list} (nearest-line cross-check). Assess plausibility, write analysis/final_results.md, send [RANKING-COMPLETE].",
     summary="Kick off ranking"
   )
   ```

5. **If iterations >= 10 (safety cap) and solution_count > 10:** create the ranking task (same as
   above), push the [BEGIN] ranking directive to the solution analyst, and proceed to
   present_results with a caveat.

Every task you create has its `[BEGIN]` directive pushed before you return to monitoring. Do not
end a turn on a bare `TaskCreate`: an idle agent does not pick up a task on its own, so an
un-pushed task stalls the run.

## Detect loops

Check the parsed iteration history against the five loop patterns: ELIM Thrashing, Zero-Solution
Loop, Solution Explosion, Constraint Churning, Quality Convergence Failure. Their definitions and
detection criteria are read with this file. Two criteria apply in addition:

- **ELIM thrashing as runaway escalation.** `elim_budget > 3` in consecutive
  `[ITERATION-COMPLETE]` messages without a plausible solution is runaway ELIM escalation. At N=3
  with 0 plausible solutions, the problem is a constraint conflict, not a 4J issue.
- **Quality Convergence Failure guard.** Do not fire it when solution_count = 0; the Zero-Solution
  Loop covers that case.

If no loop pattern is detected, check convergence:
- **solution_count <= 10:** success, proceed to present_results.
- **iterations >= 10 and solution_count > 10:** safety cap reached, proceed to present_results with
  caveats.
- **solution_count > 10 and iterations < 10:** the agent is still progressing; let it continue.

If a loop pattern is detected, proceed to the diagnose step.

## Diagnose

For the detected loop pattern, perform a basic diagnosis to identify the root cause.

**ELIM escalation (runaway N):**
1. Read the latest LSD file from the most recent iteration.
2. Confirm elim_budget > 3 by checking the `[ITERATION-COMPLETE]` history.
3. Count MULT commands with hybridisation = 2 (sp2 atoms); verify the count is even.
4. Sum all hydrogen counts from the MULT commands; verify the sum matches the formula.
5. Check the latest HMBC correlations against the HSQC positions for 1J artefacts: an HMBC (C, H)
   within ±1.5 ppm (carbon) and ±0.3 ppm (proton) of any HSQC correlation is a 1J artefact.
6. If all checks pass at N=3 and there are still 0 solutions, this is a constraint conflict, not a
   4J issue: escalate to the diagnostic specialist.

**Zero-Solution Loop:**
1. Identify which iteration first returned 0 solutions.
2. Identify the constraints added in that iteration.
3. Check whether any HMBC correlations match HSQC positions (1J artefacts, ±1.5 ppm C, ±0.3 ppm H).
4. Check whether carbons in that batch are within 3 ppm of each other (ambiguous assignment).

**Solution Explosion:**
1. Check whether an ELIM command is present in the latest LSD file.
2. Check whether heteroatom constraints (BOND, LIST, PROP) are present in the LSD file.
3. Review the recent HMBC correlations: do they connect new fragments, or are they redundant
   connections?

**Constraint Churning:**
1. Review the last 5 iterations for systematic versus random correlation selection.
2. Check whether correlations were selected by the criteria (isolated carbons, unique protons,
   strong intensity).
3. Check whether correlations were selected randomly without a clear strategy.

Document the diagnostic findings for the intervention.
