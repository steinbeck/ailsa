# Advisory and Results Templates Reference

## Contents

- deliver_advisory: send the advisory to the running team
- present_results: success, incomplete convergence, failure
- delegate_specialist: spawn the diagnostic specialist
- extract_diagnostic_findings: turn its report into an advisory
- quality_convergence_advisory: re-examination by the NMR chemist
- multiplicity_coverage_reopen_advisory: search the missing multiplicity family
- What Not to Do

## Templates

<step name="deliver_advisory">
Deliver advisory constraints to the running team via SendMessage. Do not kill and re-spawn the agent to deliver an advisory.

Before sending, record the intervention note:
`ailsa run note "Intervention: Pattern: <pattern_name>; Counter: <n>/10; Advisory sent: <one line>; Diagnosis: <none, or root cause, primary fix and confidence from DIAGNOSTIC-REPORT.md>" --sender coordinator`.

**Why SendMessage instead of re-spawn:**
- Team retains all context and state (no restart overhead)
- Constraint inventory and progress are preserved
- The devil's advocate (DA) can immediately verify the fix
- No risk of losing team coordination state

**Deliver advisory to the LSD engineer (`lsd-engineer`, primary recipient):**
```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[SUPERVISOR ADVISORY] {advisory_text_from_intervene_step}

  Apply this advisory guidance in your next iteration. Read the generated progress
  log for current state (run `ailsa run render`; it prints the path). Resume from iteration {N+1}.

  Do not restart from scratch. Apply the fix to your existing constraint set.",
  summary="Supervisor advisory: {pattern_name} detected"
)
```

**Notify the devil's advocate (`devils-advocate`) to monitor the fix:**
```
SendMessage(
  type="message",
  recipient="devils-advocate",
  content="[SUPERVISOR] {pattern_name} detected. Advisory sent to lsd-engineer:
           {brief_summary_of_advisory}
           Monitor the next iteration. Verify the fix is applied correctly.
           Report back if the issue persists or new problems arise.",
  summary="Monitor advisory fix for {pattern_name}"
)
```

After delivering advisory, return to monitor_progress step to check if issue resolves.
</step>

<step name="present_results">
When agent achieves convergence (solution_count ≤ 10) or reaches safety cap (~10 iterations), present final results.

Run `ailsa run render`, then read the latest iteration from the generated progress log and any solution files generated under `{work_dir}`.

**Compute elapsed time:**
The first row of the generated progress log is `Run created`, with its UTC time.
Record the current time with `date -u`. Compute elapsed time = current - run created.
Report in the results section below.

**If solution_count ≤ 10 (success):**
Report:
```markdown
## CASE Results

**Compound:** <compound_path>
**Formula:** <formula>
**Iterations:** <N>
**Final solution count:** <count>
**Time to solution:** ~<elapsed_minutes> minutes (<N> iterations)

### Top Candidate Structures

<Present top 1-3 structures from ranking results>

| Rank | SMILES | MAE (ppm) | Confidence |
|------|--------|-----------|------------|
| 1    | <smiles> | <mae> | <confidence> |
| 2    | <smiles> | <mae> | <confidence> |

### Quality Assessment

- Convergence: <describe solution count trend across iterations>
- HMBC correlations used: X/Y
- Ambiguities: <list any documented ambiguities from agent>

### Full Iteration History

See: <CASE-PROGRESS.md path printed by `ailsa run render`>
Declared result: <final_results.md path printed by `ailsa run render` after the declaration>
```

**If solution_count > 10 at safety cap:**
Report with caveats:
```markdown
## CASE Results (Incomplete Convergence)

**Compound:** <compound_path>
**Formula:** <formula>
**Iterations:** <N> (safety cap reached)
**Final solution count:** <count>
**Time to solution:** ~<elapsed_minutes> minutes (<N> iterations, safety cap)

**Warning:** Structure elucidation did not fully converge. Results may be under-determined.

### Top Candidate Structures

<Present top 1-3 structures from ranking results WITH caveat>

| Rank | SMILES | MAE (ppm) | Confidence |
|------|--------|-----------|------------|
| 1    | <smiles> | <mae> | Medium (under-determined) |

### Why Convergence Failed

<Analyze iteration history to explain>

Examples:
- "Solution count plateaued at ~50 despite adding all available HMBC correlations. Structure may require additional NMR data."
- "Multiple zero-solution cycles required constraint removal. Available correlations conflict, suggesting ambiguous assignments."

### Recommendation

Consider:
1. Acquire additional 2D spectra (NOESY, ROESY, COSY)
2. Verify molecular formula via HRMS
3. Manual review of peak assignments

### Full Iteration History

See: <CASE-PROGRESS.md path printed by `ailsa run render`>
Declared result: <final_results.md path printed by `ailsa run render` after the declaration>
```

**If no solutions at end:**
Report failure:
```markdown
## CASE Failed

**Compound:** <compound_path>
**Formula:** <formula>
**Iterations:** <N>
**Final solution count:** 0
**Time to solution:** ~<elapsed_minutes> minutes (<N> iterations, failed)

LSD could not find any valid structures matching the given constraints.

### Likely Causes

<Based on the diagnostics in the generated progress log>

1. Molecular formula incorrect (verify HRMS data)
2. Peak assignments incorrect (review 13C, HSQC, HMBC picking)
3. Over-constrained correlations (1J artifacts included)

### Recommendation

Manual review required. See <CASE-PROGRESS.md path printed by `ailsa run render`> for full diagnostics.
Declared result: <final_results.md path printed by `ailsa run render` after the declaration>
```
</step>

<step name="delegate_specialist">
Delegate to diagnostic specialist agent for deep root cause analysis.

**This step executes when:** counter for detected pattern == 2 (routed from track_and_decide).

**Note:** The diagnostic specialist is spawned via Task() without team_name -- it operates independently from the team for objectivity. It reads team artifacts (the generated progress log CASE-PROGRESS.md, the LSD files under `{work_dir}`) but does not participate in team communication.

**Identify failure type from detected pattern:**
- ZERO_SOLUTION_LOOP -> failure_type = "0 solutions"
- SOLUTION_EXPLOSION -> failure_type = "1000+ solutions"
- ELIM_THRASHING -> failure_type = "0 solutions" (ELIM usually causes 0)
- CONSTRAINT_CHURNING -> failure_type = "other"

**Extract latest LSD filename:**
Run `ailsa run render` and keep the progress log path it prints. Read the generated progress log, find the most recent iteration note and take its `LSD file:` path.

**Spawn diagnostic specialist via Task tool:**
```
Task(
  agent_type="ailsa-diagnostic",
  model="opus",
  instructions="Analyze LSD failure for compound at <compound_path> (read-only).
  Work folder: {work_dir} (absolute). Write every file there and use absolute paths in every command.

  Read:
  - <progress log path> (the generated progress log, CASE-PROGRESS.md: iteration history with the notes of every agent)
  - {work_dir}/<latest_iteration>/compound.lsd (latest LSD file)
    Note: The LSD file header contains a JSON constraint inventory block between
    ; === CONSTRAINT INVENTORY v1 === and ; === END CONSTRAINT INVENTORY ===
    Extract this inventory in Step 1 — it tracks hmbc_batches, deff_not_patterns,
    syme_pairs, bond_constraints, list_prop_constraints, elim_value, and detection results.
    The inventory history reveals what changed between iterations (drops, additions).

  Failure type: <failure_type>

  Run systematic diagnostic checks per your agent definition.
  Document all checks (PASS and FAIL).
  Identify root cause with evidence.

  Write structured report to {work_dir}/DIAGNOSTIC-REPORT.md.
  Include: findings, root cause, recommended fixes with LSD command examples.
  Rate all findings and recommendations as HIGH/MEDIUM/LOW confidence.
  "
)
```

**After specialist Task completes**, proceed to extract_diagnostic_findings step.
</step>

<step name="extract_diagnostic_findings">
Read and parse DIAGNOSTIC-REPORT.md to extract root cause and primary fix for specialist-informed advisory generation.

**Check report exists:**
Verify file exists at {work_dir}/DIAGNOSTIC-REPORT.md.

If DIAGNOSTIC-REPORT.md is missing:
- Log: "Diagnostic specialist completed but {work_dir}/DIAGNOSTIC-REPORT.md not found"
- Fall back to basic advisory from the intervene step
- Counter still increments (specialist delegation was attempted)
- Proceed to deliver_advisory step with basic advisory

**If report exists, extract from it:**

1. **Root cause:** Locate "## Root Cause" section header. Extract "Primary:" line content. This is root_cause_primary.

2. **Primary fix:** Locate "## Recommended Fixes" section header. Find the first subsection marked "(PRIMARY)". Extract "Action:" content (may include a code block with LSD commands). This is fix_action.

3. **Verification:** From the same PRIMARY fix subsection, extract "Verification:" content. This is fix_verification.

**Generate specialist-informed advisory:**
```
Diagnostic specialist identified root cause: <root_cause_primary>

See {work_dir}/DIAGNOSTIC-REPORT.md for full analysis.

Fix: <fix_action>
<include LSD command examples from fix if present>

Verification: <fix_verification>

<optional pattern-specific guidance, e.g., for ELIM_THRASHING: "Do not add ELIM again until this fix is verified.">
```

**Key difference from basic advisory:** Specialist-informed advisory is specific (exact atom, exact command, exact verification) because the specialist ran systematic checks with quantitative evidence. Basic advisory is procedural (check these conditions, verify these things).

Proceed to deliver_advisory step with the specialist-informed advisory.
</step>

<step name="quality_convergence_advisory">

## Advisory: Quality Convergence Failure

**Deliver to:** the NMR chemist (`nmr-chemist`, reactivation advisory) via SendMessage.

**When to use:** QUALITY_CONVERGENCE_FAILURE detected (count_quality == 0). All top-3
solutions are `IMPLAUSIBLE`/`QUESTIONABLE` despite a converged solution count.

**Advisory text:**

```
[SUPERVISOR ADVISORY - QUALITY CONVERGENCE FAILURE]

All top solutions are IMPLAUSIBLE or QUESTIONABLE. The LSD constraint logic appears
sound (solutions converged), but the 13C interpretation going into LSD may be wrong.

Re-examination checklist (perform in order, stop when a concrete defect is found):

1. DBE balance: count accounted DBE (rings + C=C + C=O). Is the total < formula DBE?
   - If deficit: check the SNR annotation from your `ailsa pick 1d --format json` output.
     Any peaks in 160-220 ppm with SNR 3-20 that were not assigned?
   - If yes: that is a candidate missed carbonyl. Note it and proceed to step 3.

2. Intensity-symmetry: were any aromatic CH peaks flagged as 2C-equivalence candidates
   (intensity ≥ 1.6× class median)?
   - If yes and they were not passed to `ailsa detect aromatic-cosy`: re-run
     `ailsa detect aromatic-cosy` with the correct grouped shifts. Send updated
     HMBC equivalence groups to lsd-engineer for the next iteration.
   - If yes and they were already passed: confirm lsd-engineer used grouped notation
     `HMBC (C1 C2) H` syntax in the LSD file (carbon side grouped; a grouped proton side,
     `HMBC C (H1 H2)`, aborts LSD with error 116).

3. Multiplicity spot-check: for any suspect peak (DBE candidate or near-equivalent),
   confirm DEPT-135 sign is consistent with the assignment.

After re-examination:
  - If a concrete defect is found: describe it in your [DETECTION-COMPLETE] message.
    lsd-engineer will rebuild the LSD file incorporating the correction.
  - If no defect found: respond "Re-examination complete: no correctable peak-picking
    defect found." The coordinator will close with honest termination.

Budget: this is the only re-examination cycle. Do not initiate a further re-pick
unless a concrete suspicion exists (empty expected-region despite DBE deficit with
SNR 3-20 evidence). A blind re-pick at lower threshold is not warranted — the SNR
floor is already at k=3.
```

**SendMessage target:** `nmr-chemist`, not `lsd-engineer`: the defect is in picking, not constraints.
**After delivering advisory:** Return to monitor_progress. Do not trigger a full new LSD run yet — wait for the NMR chemist to respond with [DETECTION-COMPLETE] or "no defect found."

</step>

<step name="multiplicity_coverage_reopen_advisory">

## Advisory: Multiplicity Coverage Gap (reopen)

**Deliver to:** the LSD engineer (`lsd-engineer`) via SendMessage.

**When to use:** the case.md `coverage_gate` step returned `FAIL` — a `[MULTIPLICITY-AMBIGUOUS]`
run is about to accept but a viable multiplicity family (`viable_families ⊄ searched_families`)
or the model X of a DA `[MULT-EVIDENCE-FOR] model=X` message was never searched. This advisory is
triggered by coverage, not by MAE: do not wait for a poor MAE, because a structure of the wrong
multiplicity class can score a low MAE.

**Advisory text (what, not how — name the missing family/model and the search requirement; do not
dictate the MULT lines):**

```
[SUPERVISOR ADVISORY - MULTIPLICITY COVERAGE GAP]

The run cannot accept yet: a viable aliphatic multiplicity family was identified but never
searched. Coverage check (the latest `Multiplicity coverage:` note in the run record) is the
source of truth.

Missing from the searched set: <family/model name(s), each with its CH₃/CH₂/CH partition,
and/or a DA-mandated model X from [MULT-EVIDENCE-FOR]>.

Required action:
- Search each missing family/model in its own iteration_NN_<family>/ dir, fully constrained
  (same HSQC/HMBC/ring-exclusion/BOND/COSY/fragment/inventory constraints; differ only in the
  MULT block). Read your existing constraint set; do not reconstruct it from scratch, because
  constraints rebuilt from memory get dropped.
- A family counts as searched once its LSD run produces an [ITERATION-COMPLETE] — even if you
  skip solutions.smi conversion for size (searched, not ranked). Do not drop a large family.
- After the missing run(s) complete, rebuild the deduplicated union_solutions.smi with them;
  the coordinator then has the solution analyst rank the union and re-enters the coverage gate.

This is a coverage requirement, independent of MAE/plausibility: a low-MAE leading model does
not close a missing family. A devil's advocate [MULT-EVIDENCE-FOR] flag is closed only by an
actual search of that model, not by argument or a convergence narrative.

Do not restart from scratch. Add the missing family(ies) alongside the families already searched.
```

**SendMessage target:** `lsd-engineer` (the coverage defect is a missing search, not a picking
defect). Optionally notify the devil's advocate (`devils-advocate`) to confirm each
[MULT-EVIDENCE-FOR] model is now in the searched set.
**After delivering advisory:** Return to monitor_progress. On the missing family/model's
[ITERATION-COMPLETE], record the updated searched_families in a new `Multiplicity coverage:` note,
push the solution analyst the union ranking as the coverage gate describes, and on its new
[RANKING-COMPLETE] re-enter the coverage_gate. Do not proceed to identity_gate until coverage_gate
passes.

</step>

<anti_patterns>

## What Not to Do

**Do not duplicate agent knowledge in Task instructions:**
- The specialist agents each have their own domain knowledge
- Task(team_name) prompts should provide only task-specific details (compound path, formula)
- Agent definitions contain the domain expertise

**Do not use directive interventions:**
- Advisory says what to fix (e.g., "sp2 count is odd")
- Directive prescribes how to fix it (e.g., "Change line 15 from X to Y")
- Agent retains autonomy to decide implementation

**Do not use a global intervention counter:**
- Track per-pattern counters separately: {ELIM_THRASHING: 2, ZERO_SOLUTION_LOOP: 0, ...}
- Different patterns have different root causes
- Global counter masks which specific failure mode is recurring

**Do not attempt dereplication in the coordinator:**
- CASE is de novo structure elucidation (starts from scratch)
- Dereplication is a completely separate workflow (/ailsa:dereplicate)
- The two workflows stay completely separate

**Do not re-spawn the team to deliver an advisory:**
- Killing and re-spawning the agent with advisory text does not work with teams
- Use SendMessage to deliver advisory to the running team
- Team retains context, constraint inventory, and coordination state
- Re-spawning creates isolated agents outside the team

**Do not call TeamDelete before shutdown_request:**
- TeamDelete fails if teammates are still active
- Send shutdown_request to all 4 teammates first, every time
- Wait for shutdown confirmations before cleanup

**Do not delegate to the diagnostic specialist on the first loop detection:**
- First detection (counter = 0) -> basic diagnosis only
- First recurrence (counter = 1) -> basic diagnosis again
- Second recurrence (counter = 2) -> delegate to specialist
- The specialist has extensive deep diagnostic knowledge that is overkill for common issues (odd sp2, missing H) caught by basic diagnosis

</anti_patterns>
