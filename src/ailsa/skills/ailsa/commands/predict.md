---
description: "Predict 13C NMR chemical shifts for a SMILES structure. Use when: predict shifts, expected chemical shifts, what shifts would this have, HOSE code prediction, verify a structure"
argument-hint: "<smiles>"
allowed-tools: [Bash]
---

<objective>
Predict 13C NMR chemical shifts for a given SMILES string using the ailsa HOSE-code prediction engine.
</objective>

<process>

<step name="parse_arguments">
Parse the user's input for a SMILES string.

- **Required:** A SMILES string (should be quoted)
- If no arguments provided, show usage:
  ```
  Usage: /ailsa:predict "<smiles>"
  Example: /ailsa:predict "CCO"
  ```
  Then stop.
- Validate the SMILES is a non-empty string before proceeding.
</step>

<step name="run_prediction">
Execute the prediction via CLI:

```bash
ailsa predict c13 "<smiles>" --format json
```

Capture the JSON output. If the command fails, proceed to present_results with the error.
</step>

<step name="present_results">
Parse the JSON output and present results to the user.

**On success:**
- Show a predictions table with columns: Atom Index, Predicted Shift (ppm), Confidence
- Report summary: total atoms predicted, atoms with predictions, average confidence
- Example table format:
  ```
  | Atom | Shift (ppm) | Confidence |
  |------|-------------|------------|
  | 0    | 18.2        | high       |
  | 1    | 57.8        | high       |
  ```

**On error:**
- If database not found: report error and suggest `ailsa database download`
- If SMILES invalid: report the RDKit parse error from CLI output
- If other error: report the error message from CLI output

**If some atoms have no predictions (HOSE code miss):**
- Report which atom indices have no predictions
- Explain: "The HOSE-code database has 7.9M entries but may not cover unusual functional groups or rare substitution patterns."
- Suggest: "Try these alternatives:"
  1. "Use canonical SMILES (RDKit: `Chem.MolToSmiles(mol)`) — non-canonical SMILES may produce different atom numbering"
  2. "Simplify the structure — remove stereochemistry (/ and \ characters) and try again"
  3. "Check for unusual functional groups — the database is built from COCONUT and NMRShiftDB natural products, which may lack synthetic scaffolds"
- Note: "Atoms with 'low' confidence have few database examples. Consider the prediction range rather than the point estimate."
</step>

</process>
