# Advisory and Results Templates Reference

<step name="deliver_advisory">
Deliver advisory constraints to the running team via SendMessage. This REPLACES the earlier pattern of killing and re-spawning the agent.

**Why SendMessage instead of re-spawn:**
- Team retains all context and state (no restart overhead)
- Constraint inventory and progress are preserved
- Devils-advocate can immediately verify the fix
- No risk of losing team coordination state

**Deliver advisory to lsd-engineer (primary recipient):**
```
SendMessage(
  type="message",
  recipient="lsd-engineer",
  content="[SUPERVISOR ADVISORY] {advisory_text_from_intervene_step}

  Apply this advisory guidance in your next iteration. Read CASE-PROGRESS.md
  for current state. Resume from iteration {N+1}.

  Do NOT restart from scratch. Apply the fix to your existing constraint set.",
  summary="Supervisor advisory: {pattern_name} detected"
)
```

**Notify devils-advocate to monitor the fix:**
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
When agent achieves convergence (solution_count ≤ 10) OR reaches safety cap (~10 iterations), present final results.

Read the latest iteration from CASE-PROGRESS.md and any solution files generated.

**Compute elapsed time:**
Parse the `**Started:** <timestamp>` line from the CASE-PROGRESS.md file header.
Record current time. Compute elapsed time = current - started.
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

See: <compound_path>/analysis/CASE-PROGRESS.md
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

See: <compound_path>/analysis/CASE-PROGRESS.md
```

**If NO solutions at end:**
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

<Based on CASE-PROGRESS.md diagnostics>

1. Molecular formula incorrect (verify HRMS data)
2. Peak assignments incorrect (review 13C, HSQC, HMBC picking)
3. Over-constrained correlations (1J artifacts included)

### Recommendation

Manual review required. See CASE-PROGRESS.md for full diagnostics.
```
</step>

<step name="delegate_specialist">
Delegate to diagnostic specialist agent for deep root cause analysis.

**This step executes when:** counter for detected pattern == 2 (routed from track_and_decide).

**Note:** The diagnostic specialist is spawned via Task() WITHOUT team_name -- it operates independently from the team for objectivity. It reads team artifacts (CASE-PROGRESS.md, LSD files) but does not participate in team communication.

**Identify failure type from detected pattern:**
- ZERO_SOLUTION_LOOP -> failure_type = "0 solutions"
- SOLUTION_EXPLOSION -> failure_type = "1000+ solutions"
- ELIM_THRASHING -> failure_type = "0 solutions" (ELIM usually causes 0)
- CONSTRAINT_CHURNING -> failure_type = "other"

**Extract latest LSD filename:**
Read CASE-PROGRESS.md, find most recent iteration, extract the LSD file reference.

**Spawn diagnostic specialist via Task tool:**
```
Task(
  agent_type="lucy-diagnostic",
  model="opus",
  instructions="Analyze LSD failure for compound at <compound_path>.

  Read:
  - <compound_path>/analysis/CASE-PROGRESS.md (iteration history with per-agent sections)
  - <compound_path>/analysis/<latest_iteration>/compound.lsd (latest LSD file)
    Note: The LSD file header contains a JSON constraint inventory block between
    ; === CONSTRAINT INVENTORY v1 === and ; === END CONSTRAINT INVENTORY ===
    Extract this inventory in Step 1 — it tracks hmbc_batches, deff_not_patterns,
    syme_pairs, bond_constraints, list_prop_constraints, elim_value, and detection results.
    The inventory history reveals WHAT changed between iterations (drops, additions).

  Failure type: <failure_type>

  Run systematic diagnostic checks per your inlined knowledge.
  Document ALL checks (PASS and FAIL).
  Identify root cause with evidence.

  Write structured report to <compound_path>/analysis/DIAGNOSTIC-REPORT.md.
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
Verify file exists at <compound_path>/analysis/DIAGNOSTIC-REPORT.md.

If DIAGNOSTIC-REPORT.md is missing:
- Log: "Diagnostic specialist completed but analysis/DIAGNOSTIC-REPORT.md not found"
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

See analysis/DIAGNOSTIC-REPORT.md for full analysis.

Fix: <fix_action>
<include LSD command examples from fix if present>

Verification: <fix_verification>

<optional pattern-specific guidance, e.g., for ELIM_THRASHING: "Do NOT add ELIM again until this fix is verified.">
```

**Key difference from basic advisory:** Specialist-informed advisory is SPECIFIC (exact atom, exact command, exact verification) because the specialist ran systematic checks with quantitative evidence. Basic advisory is PROCEDURAL (check these conditions, verify these things).

Proceed to deliver_advisory step with the specialist-informed advisory.
</step>

<step name="quality_convergence_advisory">

## Advisory: Quality Convergence Failure

**Deliver to:** nmr-chemist (reactivation advisory) via SendMessage.

**When to use:** QUALITY_CONVERGENCE_FAILURE detected (count_quality == 0). All top-3
solutions are IMPLAUSIBLE/QUESTIONABLE despite a converged solution count.

**Advisory text:**

```
[SUPERVISOR ADVISORY - QUALITY CONVERGENCE FAILURE]

All top solutions are IMPLAUSIBLE or QUESTIONABLE. The LSD constraint logic appears
sound (solutions converged), but the 13C INTERPRETATION going into LSD may be wrong.

Re-examination checklist (perform in order, stop when a concrete defect is found):

1. DBE balance: count accounted DBE (rings + C=C + C=O). Is the total < formula DBE?
   - If deficit: check the SNR annotation from your `lucy pick 1d --format json` output.
     Any peaks in 160-220 ppm with SNR 3-20 that were not assigned?
   - If yes: that is a candidate missed carbonyl. Note it and proceed to step 3.

2. Intensity-symmetry: were any aromatic CH peaks flagged as 2C-equivalence candidates
   (intensity ≥ 1.6× class median)?
   - If yes AND they were NOT passed to `lucy detect aromatic-cosy`: re-run
     `lucy detect aromatic-cosy` with the correct grouped shifts. Send updated
     HMBC equivalence groups to lsd-engineer for the next iteration.
   - If yes AND they were already passed: confirm lsd-engineer used grouped notation
     `HMBC (C1 C2) H` syntax in the LSD file (carbon side grouped; a grouped proton side,
     `HMBC C (H1 H2)`, aborts LSD with error 116).

3. Multiplicity spot-check: for any suspect peak (DBE candidate or near-equivalent),
   confirm DEPT-135 sign is consistent with the assignment.

After re-examination:
  - If a concrete defect is found: describe it in your [DETECTION-COMPLETE] message.
    lsd-engineer will rebuild the LSD file incorporating the correction.
  - If no defect found: respond "Re-examination complete: no correctable peak-picking
    defect found." The coordinator will close with honest termination.

Budget: THIS IS THE ONLY re-examination cycle. Do not initiate a further re-pick
unless a concrete suspicion exists (empty expected-region despite DBE deficit with
SNR 3-20 evidence). A blind re-pick at lower threshold is not warranted — the SNR
floor is already at k=3.
```

**SendMessage target:** nmr-chemist (NOT lsd-engineer — the defect is in picking, not constraints).
**After delivering advisory:** Return to monitor_progress. Do not trigger a full new LSD run yet — wait for nmr-chemist to respond with [DETECTION-COMPLETE] or "no defect found."

</step>

<step name="multiplicity_coverage_reopen_advisory">

## Advisory: Multiplicity Coverage Gap (reopen)

<!--
RELOAD NOTE: this reference is a repo `.claude/` skill file symlinked into `~/.claude`. This is a
MARKDOWN PROMPT EDIT — a FRESH Claude Code session is REQUIRED to reload. NOT unit-testable this
session; functional validation is the blind CASE4 re-run (UAT-01 / Phase 89).
-->

**Deliver to:** lsd-engineer via SendMessage.

**When to use:** the case.md `coverage_gate` step returned FAIL — a `[MULTIPLICITY-AMBIGUOUS]`
run is about to accept but a viable multiplicity family (`viable_families ⊄ searched_families`)
or a Devils-Advocate `[MULT-EVIDENCE-FOR] model=X` was never searched. This is COVERAGE-triggered,
NOT MAE-triggered — do not wait for a poor MAE.

**Advisory text (WHAT not HOW — name the missing family/model and the search requirement; do NOT
dictate the MULT lines):**

```
[SUPERVISOR ADVISORY - MULTIPLICITY COVERAGE GAP]

The run cannot accept yet: a viable aliphatic multiplicity family was identified but never
searched. Coverage check (CASE-PROGRESS.md ## Multiplicity Coverage) is the source of truth.

Missing from the searched set: <family/model name(s), e.g. "ethyl (2×CH₃+CH₂+CH₂)" and/or a
DA-mandated model X from [MULT-EVIDENCE-FOR]>.

Required action:
- Search EACH missing family/model in its OWN iteration_NN_<family>/ dir, fully constrained
  (same HSQC/HMBC/ring-exclusion/BOND/COSY/fragment/inventory constraints; differ ONLY in the
  MULT block). Read your existing constraint set — do NOT reconstruct from scratch.
- A family counts as SEARCHED once its LSD run produces an [ITERATION-COMPLETE] — even if you
  skip solutions.smi conversion for size (SEARCHED-not-RANKED). Do not drop a large family.
- After the missing run(s) complete, the coordinator re-runs the deduped union rank and
  re-enters the coverage gate.

This is a COVERAGE requirement, independent of MAE/plausibility: a low-MAE leading model does
NOT close a missing family. A Devils-Advocate [MULT-EVIDENCE-FOR] flag is closeable ONLY by an
actual search of that model — never by argument or convergence narrative.

Do NOT restart from scratch. Add the missing family(ies) alongside the families already searched.
```

**SendMessage target:** lsd-engineer (the coverage defect is a missing search, not a picking
defect). Optionally notify devils-advocate to confirm each [MULT-EVIDENCE-FOR] model is now in
the searched set.
**After delivering advisory:** Return to monitor_progress. On the missing family/model's
[ITERATION-COMPLETE], update searched_families in the ledger, re-run the union rank, and
re-enter the coverage_gate. Do not proceed to identity_gate until coverage_gate PASSES.

</step>

<anti_patterns>

## What NOT to Do

**Never duplicate agent knowledge in Task instructions:**
- The specialist agents each have their own domain knowledge
- Task(team_name) prompts should provide ONLY task-specific details (compound path, formula)
- Agent definitions contain the domain expertise

**Never use directive interventions:**
- Advisory says WHAT to fix (e.g., "sp2 count is odd")
- Directive prescribes HOW to fix it (e.g., "Change line 15 from X to Y")
- Agent retains autonomy to decide implementation

**Never use a global intervention counter:**
- Track per-pattern counters separately: {ELIM_THRASHING: 2, ZERO_SOLUTION_LOOP: 0, ...}
- Different patterns have different root causes
- Global counter masks which specific failure mode is recurring

**Never attempt dereplication in this orchestrator:**
- CASE is de novo structure elucidation (starts from scratch)
- Dereplication is a completely separate workflow (/lucy-ng:dereplicate)
- Absolute separation maintained

**Never re-spawn the team to deliver an advisory:**
- A previous pattern killed and re-spawned the agent with advisory text -- this is INVALID with teams
- Use SendMessage to deliver advisory to the running team
- Team retains context, constraint inventory, and coordination state
- Re-spawning creates isolated agents outside the team

**Never call TeamDelete before shutdown_request:**
- TeamDelete fails if teammates are still active
- Always send shutdown_request to all 4 teammates first
- Wait for shutdown confirmations before cleanup

**Never delegate to specialist on first loop detection:**
- First detection (counter = 0) -> basic diagnosis only
- First recurrence (counter = 1) -> basic diagnosis again
- Second recurrence (counter = 2) -> delegate to specialist
- The specialist has extensive deep diagnostic knowledge that is overkill for common issues (odd sp2, missing H) caught by basic diagnosis

</anti_patterns>
