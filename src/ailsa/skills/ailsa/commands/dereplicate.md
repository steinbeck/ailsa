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

The reference database holds 928K compounds: COCONUT natural products with predicted 13C shifts
and NMRShiftDB entries with measured 13C shifts.
COCONUT 13C shifts: from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0 — predicted, not measured.
</objective>

<process>

<step name="parse_arguments">
Parse user-provided arguments. Two input modes are supported:

**Mode 1 -- Bruker path + formula:**
```
/ailsa:dereplicate <compound_path>/2 <formula> -n 10
```

**Mode 2 -- Shift list + formula:**
```
/ailsa:dereplicate --shifts "<shift1>,<shift2>,<shift3>" <formula> -n 10
```

- Default `-n` to 10 if not provided by the user
- If no arguments given, show usage:

```
Usage: /ailsa:dereplicate <bruker_path> <formula> [-n N]
       /ailsa:dereplicate --shifts "<shifts>" <formula> [-n N]

Examples:
  /ailsa:dereplicate <compound_path>/2 <formula>
  /ailsa:dereplicate --shifts "<shift1>,<shift2>" <formula> -n 5
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
  1. "Check formula spelling — common mistakes: lowercase letters (element symbols start with a capital: `C<n>H<m>`, not `c<n>h<m>`), missing element counts (`C<n>H<m>O` vs `C<n>H<m>O1`)"
  2. "Try related formulas — if unsure about heteroatom count, try ±1 oxygen or nitrogen (e.g., `C<n>H<m>O`, `C<n>H<m>O2`)"
  3. "The compound may not be in the database — COCONUT covers about 895K natural products and NMRShiftDB about 33K experimental entries. Synthetic compounds and rare natural products may be absent."
  4. "Consider running full CASE instead: /ailsa:case — this determines structure from NMR data without requiring database lookup"

**If error (database not found, invalid formula, etc.):**
Report the error and suggest corrective action:
- Database missing: "Run: ailsa database download"
- Invalid formula: show the error message from the CLI
</step>

</process>
