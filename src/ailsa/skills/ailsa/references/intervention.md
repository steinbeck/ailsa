# Intervention and escalation

What the coordinator does once diagnose has found the likely root cause of a loop pattern: write an
advisory that tells the agent what to fix, count the interventions per pattern, hand over to the
diagnostic specialist or end the run honestly, and escalate to the user after 10 failed cycles of
the same pattern.

## Contents

- Intervene: advisory templates by pattern
- Track and decide
- Escalate

## Intervene: advisory templates by pattern

Based on the diagnosis, generate an advisory intervention that tells the agent what to fix, not how
to fix it.

**ELIM escalation (runaway N):**
```
Runaway ELIM escalation detected. At N=3 with 0 plausible solutions, this is a constraint conflict — not a 4J issue.

Do not escalate ELIM beyond N=3. Instead:

1. Verify sp2 count is even (current count: <N>)
   - Re-examine DEPT-135 spectrum to verify sp2 assignments
   - Common sp2 atoms: carbonyl C, carbonyl O, aromatic C

2. Verify hydrogen budget matches formula
   - Sum of MULT H-counts: <N>
   - Formula H-count: <N>
   - If mismatch, review HSQC peak assignments

3. Check HMBC correlations for 1J artifacts
   - Compare against HSQC positions (±1.5 ppm C, ±0.3 ppm H)
   - Exclude flagged artifacts

Escalate to diagnostic specialist — do not continue ELIM escalation.
```

**Zero-Solution Loop:**
```
Zero-solution loop detected (3 consecutive iterations with 0 solutions).

Diagnose:
1. Remove last HMBC batch (iteration <N> constraints)
2. Confirm solutions return
3. Test each correlation individually to find the conflict
4. Check if any carbons are within 3 ppm (could be misassigned due to digital resolution)
5. Check for 1J artifacts (compare HMBC to HSQC positions)

Only re-add correlations after resolving the conflict.
```

**Solution Explosion:**
```
Solution explosion stalled (3 iterations, <10% reduction each, still >100 solutions).

Check:
1. Verify recent HMBC correlations connect new fragments (not already-connected atoms)
2. Add heteroatom constraints:
   - Use BOND for known positions (e.g., carbonyl O bonded to specific C)
   - Use LIST/PROP for ambiguous positions
3. Check quaternary carbons — if 0 HMBC correlations, add shift-based constraints
4. ELIM is the final zero-solution recovery mechanism. If ELIM N=3 yields 0 plausible solutions, escalate to diagnostic specialist — this is a constraint conflict, not a 4J issue. Do not remove ELIM as a first response to solution explosion; large solution sets are expected with ELIM and handled by ranking.

Focus on high-leverage constraints that separate structural classes.
```

**Constraint Churning:**
```
Constraint churning detected (high add/remove activity without convergence).

Reset to last known-good state (iteration <N> with <X> solutions).

Follow the incremental HMBC strategy:
1. Select 3-5 high-confidence correlations per batch:
   - Isolated carbon shifts (>3 ppm from nearest neighbor)
   - Unique proton assignments
   - Strong peak intensities (top quartile)
2. Add batch, run LSD, evaluate effectiveness
3. If reduction >= 30%, continue with next batch
4. If reduction < 10%, re-evaluate selection criteria

Do not add/remove randomly. Be systematic.
```

Proceed to the track_and_decide step with the generated advisory.

## Track and decide

Count the interventions for this specific pattern and decide whether to give a basic advisory,
delegate to the diagnostic specialist, or escalate.

**Per-pattern intervention counters.** Keep a separate counter for each pattern:
- ELIM_THRASHING: count_elim
- ZERO_SOLUTION_LOOP: count_zero
- SOLUTION_EXPLOSION: count_explosion
- CONSTRAINT_CHURNING: count_churning
- QUALITY_CONVERGENCE_FAILURE: count_quality

After an intervention is generated, increment the counter for this pattern only.

**Decision logic:**
- **Counter for this pattern == 0 or 1:** basic intervention (the diagnose and intervene steps
  produce the advisory; proceed to the deliver_advisory step).
- **Counter for this pattern == 2:** delegate to the diagnostic specialist (proceed to the
  delegate_specialist step).
- **Counter for this pattern >= 3 and < 10:** use the specialist-informed advisory if
  `{work_dir}/DIAGNOSTIC-REPORT.md` exists, otherwise fall back to the basic advisory (proceed to
  the deliver_advisory step).
- **Counter for this pattern >= 10:** escalate to the user (proceed to the escalate step).

Threshold = 2: the basic diagnosis handles the common issues (odd sp2 count, missing H); the
specialist escalation prevents wasted cycles on complex root causes. Per-pattern counters avoid
masking which failure mode recurs.

**Decision for QUALITY_CONVERGENCE_FAILURE:**
- count_quality == 0: deliver the assumption re-examination advisory (proceed to the
  deliver_advisory_and_results step with the quality_convergence_advisory template).
- count_quality >= 1: honest termination. Do not escalate to the diagnostic specialist: the
  diagnostic specialist is LSD-focused, and a quality convergence failure is a peak-picking issue.
  Send to coordinator: "Assumption re-examination complete. No correctable peak-picking defect
  found after 1 re-examination cycle. Additional experiments may be needed."

## Escalate

After 10 failed intervention cycles for the same pattern, escalate to the user with a structured
report.

**Escalation report format:**

```markdown
## CASE Escalation Required

**Compound:** <compound_path> | **Formula:** <formula> | **Pattern:** <pattern_name> | **Attempts:** 10

### What Was Detected
<Loop pattern description per detect_loops definitions>

### Diagnostics Attempted
<List diagnostic approaches across the 10 cycles>

### Current State
- Solution count: <count> | HMBC used: X/Y | Iterations: <N> | LSD: <latest_filename>

### Coordinator Recommendation
<Pattern-specific recommendation based on diagnostic findings>

### Next Steps
Manual review required. See the generated progress log (<CASE-PROGRESS.md path printed by `ailsa run render`>) for full iteration history.
```

**After presenting the escalation report:** go to terminate_team, which declares the run
`handed_to_human` with the pattern and the 10 failed cycles as the termination reason, closes and
renders the record and shuts the team down. Then stop: the user has to investigate.
