# Loop Detection Patterns Reference

## Contents

- ELIM Thrashing
- Zero-Solution Loop
- Solution Explosion
- Constraint Churning
- Quality Convergence Failure
- Multiplicity Coverage Gap

<loop_detection_reference>

## Loop Patterns

Detailed definitions for the detect_loops step:

### ELIM Thrashing
**Definition:** Adding or removing ELIM repeatedly without diagnosing the root cause.

**Detection criteria:**
- ELIM added 2+ times across iterations
- OR: ELIM added, removed, then added again

**Common root causes:**
- sp2 count is odd (most common)
- Hydrogen budget mismatch
- 1J artifacts in HMBC
- Close carbons causing ambiguous assignment

### Zero-Solution Loop
**Definition:** Three or more consecutive iterations returning 0 solutions without changing approach.

**Detection criteria:**
- 3+ consecutive iterations with solution_count = 0
- Same approach (e.g., keep adding HMBC without removing any)

**Common root causes:**
- Conflicting HMBC correlations (1J artifacts)
- Incorrect carbon assignment (close peaks, overlapping signals)
- Incorrect molecular formula
- Close carbons within 3 ppm (digital resolution limit)

### Solution Explosion
**Definition:** Three or more consecutive iterations with solution count > 100 and < 10% reduction each.

**Detection criteria:**
- Last 3 iterations all have solution_count > 100
- Each iteration reduces count by less than 10% compared to previous

**Common root causes:**
- ELIM present (increases solution space)
- Added correlations are redundant (connecting already-connected atoms)
- Missing heteroatom constraints (O, N positions unspecified)
- Quaternary carbons with 0 HMBC correlations (not constraining structure)

### Constraint Churning
**Definition:** Adding and removing constraints randomly without convergence over 5+ iterations.

**Detection criteria:**
- Last 5 iterations show >10 constraints added AND >5 constraints removed
- Most recent iteration has solution_count > 50

**Common root causes:**
- Random correlation selection (not criteria-based)
- Not following incremental HMBC strategy
- Molecular formula incorrect (no strategy will converge)

### Quality Convergence Failure
**Definition:** Solutions converge to a small count but all top-K candidates are
`IMPLAUSIBLE` or `QUESTIONABLE` per the solution analyst's verdict.

**Detection criteria (primary — check first):**
- The solution analyst's most recent [RANKING-COMPLETE] record lists Chemical plausibility
  as "IMPLAUSIBLE" or "QUESTIONABLE" for all top-3 candidates.
- A [RANKING-COMPLETE] record for the current iteration must exist (guard against
  false fire before ranking has run).

**Detection criteria (OR trigger):**
- best MAE in latest [RANKING-COMPLETE] > 4.0 ppm AND solution_count ≤ 20.

**Common root causes:**
- A key peak was missed in initial 13C picking (e.g., weak quaternary carbonyl masked
  by a solvent-dominated max-relative threshold)
- DBE deficit: missing carbonyl → forced extra ring → correct structure excluded
- Para-symmetry not detected: 2C-equivalent aromatic peaks not passed to
  detect_aromatic_cosy_pairs → emergent ring mechanism never activated
- Incorrect molecular formula

**Why this is different from the first four patterns:**
ELIM Thrashing, Zero-Solution Loop, Solution Explosion and Constraint Churning detect LSD-level
symptoms (zero solutions, explosion, churning, ELIM thrash).
This pattern fires when LSD is healthy but the **interpretation going into LSD was wrong
from the start**. A solution_count of ≤ 20 looks like success to the other patterns —
this is the characteristic false-convergence trap for this pattern.

**Budget:** exactly one re-examination cycle. After that, honest termination.
Do not escalate to the diagnostic specialist: it is LSD-focused, not pick-focused.

### Multiplicity Coverage Gap

**Definition:** A `[MULTIPLICITY-AMBIGUOUS]` run is about to accept while a viable aliphatic
multiplicity family — or a model mandated by the devil's advocate (DA) — was never actually
searched. This is the coverage analogue of Quality Convergence Failure: it reopens the converged
run, but its trigger is missing coverage, not a poor MAE/plausibility.

**Trigger (coverage, not MAE):**
- A `[MULTIPLICITY-AMBIGUOUS]` record exists AND `viable_families ⊄ searched_families`
  (some enumerated family has no `iteration_NN_<family>/` run), **OR**
- A DA `[MULT-EVIDENCE-FOR] model=X` (G-MULT) was emitted and model X is not in
  `searched_families`.

**Data source:** the `Multiplicity coverage:` notes in the run record, read in the generated
progress log; the latest such note is the ledger (viable_families / searched_families /
DA-mandated models / gate verdict). This pattern is evaluated by the
case.md `coverage_gate` step, not by detect_loops' MAE/count heuristics.

**Counting rule — searched, not ranked:** a family counts as searched once it has its own
constrained LSD run + `[ITERATION-COMPLETE]`. A family whose `solutions.smi` conversion was
skipped because the count was large (the anti-stall rule) still counts as searched — do not drop
it from coverage just because it produced no ranked `solutions.smi`. Do not key this off MAE.

**Action — reopen:** push the LSD engineer (via the multiplicity-coverage reopen advisory, which
names what to search, not how) to run the missing family(ies)/model(s), each in its own
`iteration_NN_<family>/` dir with its own full MULT constraints. When their `[ITERATION-COMPLETE]`s
arrive, update searched_families, have the solution analyst rank the deduplicated union (a new
`[RANKING-COMPLETE]`), and re-enter the coverage gate on that message.
Do not accept until `viable_families ⊆ searched_families` AND every DA-mandated model is searched.

**Why this is different from the other patterns:** the first four are LSD-level symptoms; Quality
Convergence Failure fires on poor quality (MAE/plausibility) of a converged run. Multiplicity
Coverage Gap fires when the run looks *fully healthy* — converged, low-MAE, plausible — but a
whole multiplicity class was never in the search space: a structure of the wrong class can score a
low MAE and a plausible verdict while the true class was never searched. MAE cannot see a class
that was never searched; only coverage can.

**Budget:** Reopen as many times as needed to cover every viable family + DA-mandated model
(bounded by the NMR chemist's hard family cap, ≤3–4). The gate is deterministic — it terminates
once coverage is complete.

</loop_detection_reference>
