---
description: "Match 13C NMR spectrum against compound database. Use when: is this compound in the database, identify known compound, dereplication, match spectrum, compare shifts to database"
argument-hint: "<bruker_path_or_shifts> <formula> [-n N]"
allowed-tools:
  - Bash
---

<objective>
Run 13C dereplication by calling the ailsa CLI, matching an observed spectrum
against the compound database. Accept either a Bruker experiment path or a
comma-separated shift list, plus a molecular formula. Present ranked matches.
</objective>

<process>

<step name="parse_arguments">
Parse user-provided arguments. Two input modes are supported:

**Mode 1 -- Bruker path + formula:**
```
/ailsa:dereplicate data/compound/2 C14H16 -n 10
```

**Mode 2 -- Shift list + formula:**
```
/ailsa:dereplicate --shifts "139.94,138.51,137.16" C14H16 -n 10
```

- Default `-n` to 10 if not provided by the user
- If no arguments given, show usage:

```
Usage: /ailsa:dereplicate <bruker_path> <formula> [-n N]
       /ailsa:dereplicate --shifts "<shifts>" <formula> [-n N]

Examples:
  /ailsa:dereplicate data/compound/2 C14H16
  /ailsa:dereplicate --shifts "139.94,138.51" C10H12O2 -n 5
```
</step>

<step name="run_dereplication">
Execute the CLI command with `--format json` for structured output:

```bash
ailsa dereplicate c13 [parsed arguments] --format json
```

Capture both stdout (JSON results) and stderr (any errors).
</step>

<step name="present_results">
Parse the JSON output and present to the user:

**If `is_match` is true:**
Report "MATCH FOUND" with the top compound name, SMILES, and score.

**If `is_match` is false:**
Show top N candidates in a table:

```
# Dereplication Results for [formula]

No exact match found. Top candidates:

| Rank | Name         | SMILES       | Score |
|------|------------- |--------------|-------|
| 1    | compound_a   | CCC...       | 0.95  |
| 2    | compound_b   | CCO...       | 0.87  |
...
```

**If 0 matches returned (no compounds with this formula in database):**
- Report: "No compounds with formula [formula] found in the database (928K compounds from COCONUT + NMRShiftDB)."
- Suggest troubleshooting steps:
  1. "Check formula spelling — common mistakes: lowercase letters (use C14H16 not c14h16), missing element counts (C14H16O vs C14H16O1)"
  2. "Try related formulas — if unsure about heteroatom count, try ±1 oxygen or nitrogen (e.g., C14H16O, C14H18O2)"
  3. "The compound may not be in the database — COCONUT covers ~400K natural products and NMRShiftDB ~30K experimental entries. Synthetic compounds and rare natural products may be absent."
  4. "Consider running full CASE instead: /ailsa:case — this determines structure from NMR data without requiring database lookup"

**If error (database not found, invalid formula, etc.):**
Report the error and suggest corrective action:
- Database missing: "Run: ailsa database download"
- Invalid formula: show the error message from the CLI
</step>

</process>
