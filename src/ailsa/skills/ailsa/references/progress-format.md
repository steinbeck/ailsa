# CASE Progress Format Reference

<step name="write_progress">
Write CASE-PROGRESS.md entries as the sole writer. No agent writes this file directly — agents send structured messages and the coordinator writes their contributions.

**File location:** `<compound_path>/analysis/CASE-PROGRESS.md`

**Rule:** Append-only. NEVER overwrite previous content. NEVER let agents write this file.

**Timestamp rule:** Every `(UTC)` field below is a REAL wall-clock timestamp taken with `date -u`
per the case.md `timing` step — an ISO-8601 UTC value like `2026-07-01T09:12:03Z`. NEVER fill a
timestamp from context or `currentDate` (that has no time-of-day). These fields mirror the
append-only `analysis/timing.jsonl` log; the final `## Timing Summary` block + `analysis/timing.json`
are produced from that log at the end of the run.

**Writing triggers and order:**

1. **File header** — write immediately after team spawns (before any agent messages):

```markdown
# CASE Progress Log

**Compound:** <compound_path>
**Formula:** <molecular_formula>
**Started (UTC):** <real ISO-8601 UTC from `date -u`, = the run_start timing stamp>
**Team:** CASE Team v4.0 (coordinator, nmr-chemist, lsd-engineer, solution-analyst, devils-advocate)
**Dashboard:** <webview URL printed by `ailsa webview serve` at run start, or "unavailable — [webview] extra not installed" if the launch failed>

---
```

2. **Setup section** — write after receiving [SETUP-COMPLETE] from nmr-chemist:

```markdown
## Setup

### Team Models
<One line per teammate, from each agent's [MODEL] disclosure line. Format: `**<agent>:** <reported runtime model id> (intended: claude-opus-4-8)`. If reported != intended, prefix the line with `⚠ MODEL MISMATCH —`. Also record the coordinator's own runtime model (the orchestrator inherits the session model; no pin).>
- **coordinator (orchestrator):** <orchestrator's own runtime model id> (inherits session model)
- **nmr-chemist:** <reported> (intended: claude-opus-4-8)
- **lsd-engineer:** <reported> (intended: claude-opus-4-8)
- **solution-analyst:** <reported> (intended: claude-opus-4-8)
- **devils-advocate:** <reported> (intended: claude-opus-4-8)

### NMR-Chemist
**Reported (UTC):** <phase_end stamp for peak-picking, when [SETUP-COMPLETE] arrived>
**DBE:** <from message>
**Spectra found:** <from message>
**Peak counts:** <from message>
**Symmetry:** <from message>
**Multiplicities:** <from message>
**Quality assessment:** <from message>
**Statistical detection:** <from message>
**Grouping:** <from message>
**HHB:** <from message>
**Conflicts with NMR evidence:** <from message>
**Key observations:** <from message>

### LSD-Engineer
**Constraint inventory (iteration 0):** MULT=0, HSQC=0, HMBC=0, ring_excl=enabled, COSY_equiv=0, BOND=0
**Plan:** Build from NMR-Chemist assignments, start with first HMBC batch

---
```

3. **Iteration header** — write when starting iteration N (before agents do work):

```markdown
## Iteration N: <brief description>

### Coordinator
**Phase start (UTC):** <ISO-8601 UTC = the phase_start stamp for lsd-iteration-N>
**Iteration goal:** <brief goal for this iteration>
```

4. **LSD-Engineer section** — append after receiving [ITERATION-COMPLETE] from lsd-engineer:

```markdown
### LSD-Engineer
**Reported (UTC):** <phase_end stamp for this iteration, when [ITERATION-COMPLETE] arrived>
**LSD file:** <from message: LSD file path>
**Solution count:** <from message>
**Fragment search:** <from message>
**Fragment file:** <from message>
**Constraints added:** <from message>
**Constraints removed:** <from message>
**Constraint inventory delta:** <from message>
**sp2 count:** <from message>
**H budget:** <from message>
**HMBC correlations used:** <from message>
**Why:** <from message>
**Constraint effectiveness:** <from message>
**Confidence:** <from message>
```

5. **Devils-Advocate section** — append after receiving [VALIDATION-PASSED] or [VALIDATION-BLOCKED]:

```markdown
### Devils-Advocate
**Reported (UTC):** <phase_end stamp, when [VALIDATION-PASSED/BLOCKED] arrived>
**Validation:** <PASSED or BLOCKED>
**sp2 count:** <from message>
**H budget:** <from message>
**Ring exclusion:** <from message>
**DEFF FEXP:** <from message>
**COSY-equiv:** <from message>
**Grouped notation:** <from message>
**Correlation order:** <from message>
**Fragment ordering:** <from message>
**Concerns:** <from message>
```

If [VALIDATION-BLOCKED]: also append:
```markdown
**CRITICAL issues:** <from message>
**Action required:** <from message>
```

6. **Coordinator solution count** — append after running LSD (or after lsd-engineer reports solution count):

```markdown
### Coordinator
**Solution count:** <count>
**HMBC correlations used:** X/Y
```

7. **Solution-Analyst section** — append after receiving [RANKING-COMPLETE] (only when solution_count <= 10 or as needed):

```markdown
### Solution-Analyst
**Reported (UTC):** <phase_end stamp, when [RANKING-COMPLETE] arrived>
**Solutions:** <from message: total count>
**Top solution:** <from message: rank, SMILES, MAE, matched>
**Strained rings:** <from message>
**Chemical plausibility:** <from message>
**Quality:** <from message>
**Recommendation:** <from message>
```

8. **Diagnostic intervention block** — append when diagnostic specialist completes (between iterations):

```markdown
## Diagnostic Intervention (After Iteration N)

### Orchestrator
**Pattern detected:** <pattern_name>
**Specialist spawned:** ailsa-diagnostic at <ISO-8601 UTC from `date -u`>
**Report:** DIAGNOSTIC-REPORT.md

### Diagnostic Specialist (External)
**Root cause:** <from report>
**Primary fix:** <from report>
**Confidence:** <from report>

### Coordinator
**Advisory received:** <summary>
**Delegation:** <who does what>

---
```

9. **Intra-iteration revision** — if [VALIDATION-BLOCKED] causes a fix-and-revalidate cycle within the same iteration, append revision notes:

```markdown
### LSD-Engineer (revised)
**Fix applied:** <from revised message>
**Updated constraints:** <from message>

### Devils-Advocate (re-validation)
**Validation:** PASSED
<fields from revised validation message>
```

10. **Timing Summary** — the LAST block, appended once at the end of the run (produced by the
case.md `timing` finalize step, not hand-written). The coordinator appends the printed block
verbatim; it is generated from `analysis/timing.jsonl` alongside the machine-readable
`analysis/timing.json`:

```markdown
## Timing Summary

**Run start (UTC):** <ISO-8601>
**Run end (UTC):** <ISO-8601>
**Total wall-clock:** <HH:MM:SS>

| Phase | Agent | Start (UTC) | End (UTC) | Duration |
|-------|-------|-------------|-----------|----------|
| peak-picking | nmr-chemist | <ISO> | <ISO> | <HH:MM:SS> |
| lsd-iteration-01 | lsd-engineer | <ISO> | <ISO> | <HH:MM:SS> |
| ... | ... | ... | ... | ... |
| ranking | solution-analyst | <ISO> | <ISO> | <HH:MM:SS> |
```

`analysis/timing.json` carries the same data as structured JSON (`run_start_utc`, `run_end_utc`,
`total_duration_s`, `total_duration_hms`, and a `phases` array) for aggregation across runs.

**Backward-compatibility note:** The orchestrator's detect_loops step parses these fields from CASE-PROGRESS.md via LLM reading:
- `Solution count: N` — now in ### Coordinator or ### LSD-Engineer sub-sections within ## Iteration N:
- `Constraints added:` — in ### LSD-Engineer
- `sp2 count:` — in ### Devils-Advocate
- `H budget:` — in ### Devils-Advocate
- `HMBC correlations used: X/Y` — in ### Coordinator or ### LSD-Engineer
- `Fragment search:` — in ### LSD-Engineer
- `Fragment file:` — in ### LSD-Engineer

All field names are IDENTICAL to v3.0. Section nesting is one level deeper (### within ##). LLM parsing handles this transparently — no regex changes needed. New v5.0 fields (`Fragment search:`, `Fragment file:`, `DEFF FEXP:`, `Fragment ordering:`) are additive -- no backward-compatibility concern.

**IMPORTANT:** The write_progress step is a REFERENCE, not a sequential step. The coordinator writes CASE-PROGRESS.md entries continuously throughout the workflow as messages arrive. It is referenced from monitor_progress whenever a message is received.
</step>
