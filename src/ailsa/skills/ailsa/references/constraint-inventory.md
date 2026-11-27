# Constraint inventory

Every LSD file carries a machine-readable record of its constraints in a comment block at the top
of the file. It prevents constraint loss between iterations: each new file starts from the
previous file's record and commands, not from memory. The LSD engineer writes the block at the
step that writes each iteration's LSD file; the devil's advocate (DA) checks it against the
commands. Every LSD file contains a constraint inventory block.

## Contents

- Fields
- Where the block goes
- First iteration: build the inventory
- Later iterations: update, never rebuild
- One write for inventory and commands

## Fields

The source of truth is `schemas/constraint_inventory_v2.json` (repo root, JSON Schema Draft
2020-12). The table summarises it; the schema file is authoritative.

| Field | Type | Purpose |
|-------|------|---------|
| `version` | int (always 2) | Format version, the constant 2 |
| `iteration` | int (1-based) | Current HMBC iteration number |
| `formula` | string | Molecular formula |
| `timestamp` | ISO string | When this file was written |
| `mult_count` | int | Number of MULT atom definitions |
| `hsqc_count` | int | Number of HSQC correlation lines |
| `hmbc_batches` | array of objects | Per-batch HMBC tracking: `{batch, count, correlations[]}` |
| `hmbc_total` | int | Sum of all HMBC correlation counts across all batches |
| `grouped_hmbc` | string array | Parenthesised HMBC entries: `"(5 6) 10"` |
| `bond_constraints` | string array | BOND pairs: `"1 14"` |
| `cosy_equiv_pairs` | string array | COSY aromatic-CH equivalence pairs (tagged `; equiv-pair`), for example `"4 7"`; equivalence-derived COSY lines only, not peak-data COSY |
| `list_prop_constraints` | string array | LIST/PROP descriptions |
| `elim_value` | int or null | Deprecated alias; use `elim_budget`. Kept for compatibility with old iterations. |
| `elim_budget` | int | Current ELIM N value (0 = no ELIM command written; N > 0 = `ELIM N 0` present in the LSD file). Update it when ELIM is escalated. |
| `deff_not_patterns` | string array | Deprecated; set to `[]`. Ring exclusion is emitted as DEFF F1/F2 + FEXP (tracked by `ring_exclusion_enabled`). Kept so older inventories still validate; `DEFF NOT` lines themselves abort LSD (`error 150`) and are never written. |
| `ring_exclusion_enabled` | boolean | True when the DEFF F1 + F2 + FEXP ring exclusion block is present |
| `deff_fexp` | object or null | Fragment goodlist tracking: status, smiles, filename, commands, conflict_reason |
| `detection_results` | object | Raw output from `ailsa detect` commands |
| `applied_from_detection` | string array | Detection results translated into constraints |
| `pending_from_detection` | string array | Detection results not yet applied (with reason) |

`elim_budget` replaces retired pyLSD-era inventory fields (a pyLSD mode flag, an ELIM annotation
flag and a 4J suspect array). The retired fields are no longer required; new LSD files use only
`elim_budget`. Existing files with the retired fields remain schema-valid (the fields are
optional).

## Where the block goes

The inventory block goes at the top of the file, before any MULT definition. Use the `;` prefix
(LSD comment syntax). JSON characters (`{`, `}`, `"`, `[`, `]`) are safe in LSD comments, as a
parser test confirmed.

```
; === CONSTRAINT INVENTORY v2 ===
; {
;   "version": 2, "iteration": 2, "formula": "<formula>", "timestamp": "YYYY-MM-DDThh:mm:ssZ",
;   "mult_count": 15, "hsqc_count": 10,
;   "hmbc_batches": [
;     {"batch": 1, "count": 5, "correlations": ["1 13", "2 6", "3 4", "10 11", "4 8"]},
;     {"batch": 2, "count": 5, "correlations": ["1 9", "3 13", "3 9", "5 9", "11 10"]}
;   ],
;   "hmbc_total": 10, "grouped_hmbc": [],
;   "bond_constraints": ["1 14"], "cosy_equiv_pairs": [],
;   "list_prop_constraints": [], "elim_budget": 0,
;   "deff_not_patterns": [],
;   "ring_exclusion_enabled": true,
;   "deff_fexp": {
;     "status": "applied",
;     "fragment_smiles": "<fragment SMILES>",
;     "fragment_atoms": 7,
;     "fragment_avgdev": 0.45,
;     "fragment_filename": "fragment_abc123def456.lsd",
;     "deff_command": "DEFF F3 \"fragment_abc123def456.lsd\"",
;     "fexp_command": "FEXP \"F3 AND NOT F1 AND NOT F2\"",
;     "search_result_count": 3,
;     "conflict_reason": null
;   },
;   "detection_results": {
;     "hybridisation_queries": ["132.5 sp2"],
;     "neighbours_queries": ["180.56 O mandatory 95.8%"],
;     "hhb_result": "no HHB detected",
;     "grouping_detected": ["[44.90, 45.03] span 0.13 ppm"]
;   },
;   "applied_from_detection": ["BOND 1 14 from neighbours 180.56 O mandatory"],
;   "pending_from_detection": ["COSY-equivalence BOND/COSY for grouped [44.90, 45.03] -- NOT YET APPLIED"]
; }
; === END CONSTRAINT INVENTORY ===
; ... MULT, DUPL/MAXS, HSQC, HMBC, BOND/LIST/PROP ...
DEFF F1 "ring3"
DEFF F2 "ring4"
DEFF F3 "fragment_abc123def456.lsd"
FEXP "F3 AND NOT F1 AND NOT F2"
```

The HMBC correlations follow below the inventory block as standard `HMBC X Y` lines (no explicit
bond range). If ELIM escalation was applied, the ELIM command comes after the last HMBC
correlation, before the DEFF/FEXP commands.

## First iteration: build the inventory

After writing all MULT, HSQC, the first HMBC batch, BOND and the ring exclusion (DEFF F/FEXP) to
the file:

1. Count each constraint type from what was just written.
2. Build the inventory JSON with all fields populated.
3. Set `ring_exclusion_enabled: true` and `deff_not_patterns: []` in the inventory. Verify that
   DEFF F1 "ring3", DEFF F2 "ring4" and exactly one FEXP line containing `NOT F1 AND NOT F2`
   appear in the LSD file. This is the primary defence against dropped ring exclusion.
4. Populate `detection_results` from the NMR chemist's detection message.
5. Classify each detection result as `applied_from_detection` or `pending_from_detection`.
   - 5a. Run the fragment search: `ailsa fragment search --shifts "<13c_shifts>" --format json --top 1`
     - If result_count > 0: run
       `ailsa fragment to-lsd "<smiles>" --output-dir {work_dir}/iteration_01/ --format json` and
       populate deff_fexp with status "applied" and all fields.
     - If result_count == 0: set deff_fexp to
       ```
       {"status": "none", "fragment_smiles": null, "fragment_atoms": null, "fragment_avgdev": null, "fragment_filename": null, "deff_command": null, "fexp_command": null, "search_result_count": 0, "conflict_reason": null}
       ```
     - DEFF F3 joins the filter block and the one FEXP line becomes
       `FEXP "F3 AND NOT F1 AND NOT F2"` (F3 = fragment goodlist, reserved above the ring
       exclusion filters F1 and F2).
   - 5b. Record `elim_budget`, the current ELIM N value (0 when no ELIM command is written).
     Update this value when ELIM is escalated.
6. Write the inventory block at the top of the LSD file, before the MULT lines.
7. Write the inventory and all LSD commands in a single Write operation.

## Later iterations: update, never rebuild

Do not rebuild the inventory from scratch. This is the read-previous, never-reconstruct rule
applied to the inventory itself: what is rebuilt from memory gets dropped.

1. Read the previous iteration's LSD file (the LSD engineer's read-previous rule requires it
   anyway).
2. Extract the inventory JSON from between the `; === CONSTRAINT INVENTORY v2 ===` and
   `; === END CONSTRAINT INVENTORY ===` delimiters.
3. Copy all fields verbatim from the previous inventory as the starting point.
4. Update only these fields:
   - Increment `iteration`.
   - Append the new HMBC batch to `hmbc_batches` and increment `hmbc_total`.
   - Update `timestamp`.
   - Update `elim_budget` if ELIM was escalated (copy forward the current N value from the LSD
     file).
   - If an advisory says to add or remove constraints: update the relevant fields and the
     corresponding LSD commands.
   - Review `pending_from_detection`: apply any pending items that should now become
     constraints (move them to `applied_from_detection`).
   - Copy deff_fexp from the previous inventory. If the previous status was "applied", carry
     forward the DEFF F3 line and the merged FEXP line (the `deff_command` field gives the actual
     Fn index). Re-run the fragment search for logging. If the previous status was "discarded",
     keep the "discarded" status.
5. Write the updated inventory block at the top of the new LSD file.
6. Write all LSD commands below it (copied from the previous file, plus the new batch).

## One write for inventory and commands

The constraint inventory and the LSD commands are written as a single Write operation. The
inventory counts must match the actual commands in the same file. Do not write the inventory
separately from the commands.
