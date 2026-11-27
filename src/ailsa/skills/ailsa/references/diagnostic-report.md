# Diagnostic report

The template for `DIAGNOSTIC-REPORT.md`, which the diagnostic specialist writes as the last step of
a diagnosis. The coordinator reads the report, takes the root cause and the primary fix from it,
and advises the team with specific constraints.

## Contents

- File name and location
- Template

## File name and location

Write the report to the compound's `analysis/` subdirectory:
`<compound_directory>/analysis/DIAGNOSTIC-REPORT.md`.

If several diagnostics are needed for the same compound, use timestamped file names, for example
`DIAGNOSTIC-REPORT-<timestamp>.md`, so that an earlier report is not overwritten.

## Template

The report has this structure.

```markdown
# Diagnostic Report: <Compound Name> LSD Failure

**Compound:** <path>
**Formula:** <molecular_formula>
**Failure Type:** <0 solutions | 1000+ solutions | other>
**Diagnostic Date:** <YYYY-MM-DD HH:MM:SS>
**Diagnostic Agent:** ailsa-diagnostic

---

## Summary

[1-2 paragraph executive summary]
[Root cause in one sentence]
[Confidence level: HIGH/MEDIUM/LOW with reasoning]

---

## Findings

### Finding 1: <Title> (CRITICAL | MAJOR | MINOR)

**What:** [Description]
**Evidence:** [Quantitative data from analysis]
**Impact:** [Why this matters for failure]
**Confidence:** HIGH | MEDIUM | LOW

[Repeat for all findings — typically 2-5 per diagnostic]

---

## Root Cause

**Primary:** [Main cause with mechanism]
**Why it caused failure:** [Detailed explanation]
**Contributing factors:** [Secondary causes or "None"]

---

## Recommended Fixes

### Fix 1: <Title> (PRIMARY | SECONDARY)

**Action:** [Specific steps with LSD commands]
**Verification:** [How to confirm fix worked]
**Confidence:** HIGH | MEDIUM | LOW

[Repeat for all fixes — typically 1-3 per diagnostic]

---

## Supporting Data

### LSD File Analyzed
- Path, MULT count, HSQC count, HMBC count, other commands

### Iteration History Context
- Brief summary from CASE-PROGRESS.md

### Spectral Quality
- S/N, resolution notes

---

## Next Steps

1. [Immediate action]
2. [Verification step]
3. [Follow-up]
4. [Documentation update]

---

## Diagnostic Methodology

**Systematic checks performed:**
1. [Check name] → ✓ PASS | ✗ FAIL [with evidence]
2. [Check name] → ✓ PASS | ✗ FAIL
...

**Time to diagnosis:** [estimate]
**Tools used:** [Read, Bash, etc.]

---

## Metadata

**Diagnostic confidence breakdown:**
- Finding 1: [level] — [reason]
- Root cause: [level] — [reason]
- Fix 1: [level] — [reason]

**Specialist model:** <model reported by the specialist>
**Coordinator:** /ailsa:case
**CASE agent:** <identifier>
```
