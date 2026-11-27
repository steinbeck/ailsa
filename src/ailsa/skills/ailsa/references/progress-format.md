# CASE Progress Format Reference

## Contents

- Rules: sole writer, append-only, real timestamps
- Writing Triggers: the ten entries in order, from the file header to the timing summary
- Fields Read by Loop Detection
- When to Write

<step name="write_progress">

## Rules

Write CASE-PROGRESS.md entries as the sole writer. No agent writes this file directly — agents send structured messages and the coordinator writes their contributions.

**File location:** `<compound_path>/analysis/CASE-PROGRESS.md`

**Rule:** Append-only. Do not overwrite previous content: loop detection reads the earlier
iterations from this file. Do not let agents write this file: concurrent writes corrupt it.

**Timestamp rule:** Every `(UTC)` field below is a real wall-clock timestamp taken with `date -u`
per the case.md `timing` step — an ISO-8601 UTC value like `2026-07-01T09:12:03Z`. Do not fill a
timestamp from context or `currentDate`: that value has no time of day. These fields mirror the
append-only `analysis/timing.jsonl` log; the final `## Timing Summary` block + `analysis/timing.json`
are produced from that log at the end of the run.

## Writing Triggers

The entries, in the order they are written:

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

2. **Setup section** — write after receiving [SETUP-COMPLETE] from the NMR chemist:

```markdown
## Setup

### Team Models
<One line per teammate, from each agent's [MODEL] disclosure line. Format: `**<agent>:** <reported runtime model id>`. Also record the coordinator's own runtime model.>
- **coordinator:** <coordinator's own runtime model id>
- **nmr-chemist:** <reported>
- **lsd-engineer:** <reported>
- **solution-analyst:** <reported>
- **devils-advocate:** <reported>

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

4. **LSD engineer section** (`### LSD-Engineer`) — append after receiving [ITERATION-COMPLETE] from the LSD engineer:

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

5. **Devil's advocate section** (`### Devils-Advocate`) — append after receiving [VALIDATION-PASSED] or [VALIDATION-BLOCKED]:

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

6. **Coordinator solution count** — append after running LSD (or after the LSD engineer reports solution count):

```markdown
### Coordinator
**Solution count:** <count>
**HMBC correlations used:** X/Y
```

7. **Solution analyst section** (`### Solution-Analyst`) — append after receiving [RANKING-COMPLETE] (only when solution_count <= 10 or as needed):

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

### Coordinator
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

10. **Timing Summary** — the last block, appended once at the end of the run (produced by the
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

## Fields Read by Loop Detection

The coordinator's detect_loops step reads these fields from CASE-PROGRESS.md (an LLM reads them;
no regex parser is involved):
- `Solution count: N` — in the `### Coordinator` or `### LSD-Engineer` sub-sections within `## Iteration N:`
- `Constraints added:` — in `### LSD-Engineer`
- `sp2 count:` — in `### Devils-Advocate`
- `H budget:` — in `### Devils-Advocate`
- `HMBC correlations used: X/Y` — in `### Coordinator` or `### LSD-Engineer`
- `Fragment search:` — in `### LSD-Engineer`
- `Fragment file:` — in `### LSD-Engineer`

Write these field names exactly as shown: loop detection finds the fields by these names. The
sections sit one heading level deep (`###` within `##`); the LLM reading handles this, and no regex
needs changing. The fields `Fragment search:`, `Fragment file:`, `DEFF FEXP:` and
`Fragment ordering:` are additions; nothing that reads the older fields depends on them.

## When to Write

The write_progress step is a reference, not a sequential step. The coordinator writes
CASE-PROGRESS.md entries continuously throughout the workflow as messages arrive. It is referenced
from monitor_progress whenever a message is received.
</step>
