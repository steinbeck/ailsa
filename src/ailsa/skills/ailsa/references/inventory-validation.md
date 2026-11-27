# Inventory validation

How the devil's advocate (DA) checks the constraint inventory of an LSD file: extract it with the
CLI, reconcile it with the file and with the previous iteration, check the ELIM budget and the
failure-mode gates G7 and G-PROP-EVIDENCE, and review the detection coverage.

The constraint inventory is a JSON block embedded in `;`-prefixed comment lines at the top of every
LSD file, between the delimiters `; === CONSTRAINT INVENTORY v2 ===` and
`; === END CONSTRAINT INVENTORY ===`. The DA reads the inventory and does not modify it: it is a
read-only agent.

## Contents

- Extract the inventory
- Reconciliation checks
- Check 1: inventory accurate
- Check 2: no regression
- Check 3: content preserved
- Check 4: ELIM budget sanity
- Check 5: failure-mode gates
- G7: file modified after validation
- G-PROP-EVIDENCE: hard heteroatom constraint without evidence
- Detection coverage
- Inventory-based form of the failure-mode checks

## Extract the inventory

Use the CLI validator; do not extract the inventory with grep, sed or awk. The validator also
checks the block against the schema and tells a legacy v1 block, a missing block and a malformed
block apart, as the branches below show.

```bash
# Validate and extract inventory from current LSD file
RESULT=$(ailsa lsd validate-inventory --format json analysis/iteration_NN/compound.lsd)
VALID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['valid'])")

if [ "$VALID" = "True" ]; then
    # Inventory is valid v2 — parse for use in the reconciliation checks
    INVENTORY=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d))")
else
    # Check error type
    ERRORS=$(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(e['message']) for e in d.get('errors',[])]")
    if echo "$ERRORS" | grep -q "Legacy v1 inventory detected"; then
        # WARNING path: do not block the run
        # emit WARNING: "Legacy v1 inventory — using fallback validation"
        # proceed with the legacy grep-based count comparison (constraint diff protocol) as fallback
        echo "WARNING: Legacy v1 inventory — using fallback validation"
    elif echo "$ERRORS" | grep -q "No v2 inventory block found"; then
        # No inventory block at all
        echo "WARNING: No inventory block found — using legacy validation"
        # Fall back to the count-based comparison (legacy constraint diff protocol)
    else
        # Malformed or schema-invalid inventory: BLOCK
        # BLOCK with error details: "Inventory validation failed: $ERRORS"
        echo "BLOCK: Inventory validation failed: $ERRORS"
    fi
fi

# Extract inventory from previous iteration (for the no-regression check)
PREV_RESULT=$(ailsa lsd validate-inventory --format json analysis/iteration_MM/compound.lsd)
PREV_INVENTORY=$(echo "$PREV_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d))")
```

If no inventory block is found: fall back to the count-based constraint diff protocol and flag
`WARNING`: "No constraint inventory found -- using legacy validation."

## Reconciliation checks

For each constraint type, run the checks below with the extracted inventory and the actual LSD
file.

### Check 1: inventory accurate

The inventory counts match the actual LSD file.

| Inventory field | Grep command | Match |
|-----------------|--------------|-------|
| `mult_count` | `grep -c "^MULT" compound.lsd` | Exact |
| `hsqc_count` | `grep -c "^HSQC" compound.lsd` | Exact |
| `hmbc_total` | `grep -c "^HMBC" compound.lsd` | Exact |
| `ring_exclusion_enabled` | `grep -c "^DEFF F" compound.lsd` >= 2 and `grep -c "^FEXP" compound.lsd` == 1 | True when enabled |
| `cosy_equiv_pairs` (array length) | `grep -c "^COSY.*; equiv-pair" compound.lsd` | Exact; counts only equivalence-derived COSY, not peak-data COSY |
| `bond_constraints` (array length) | `grep -c "^BOND" compound.lsd` | Exact |
| `grouped_hmbc` (array length) | `grep -c "^HMBC (" compound.lsd` | Exact |
| `deff_fexp.status == "applied"` | `grep -c "^DEFF F[3-9] " compound.lsd` == 1 and `grep -c "^FEXP" compound.lsd` == 1 | Both present if applied |

If any count differs: flag `CRITICAL` -- "Inventory claims N {type} but file has M. Inventory is
inaccurate."

If `deff_fexp.status` is "none" or "discarded", check that `grep -c "^DEFF F[3-9] " compound.lsd`
is 0 (no stale fragment references; the ring filters F1 and F2 stay).

### Check 2: no regression

The current counts are at least the previous iteration's counts.

| Field | Expected | Alert if |
|-------|----------|----------|
| `mult_count` | Identical | Any change: `CRITICAL` |
| `hsqc_count` | Identical | Any change: `CRITICAL` |
| `hmbc_total` | >= previous | Decrease: `CRITICAL` |
| `ring_exclusion_enabled` | Stays true if it was true | False after true: `CRITICAL` |
| `cosy_equiv_pairs` length | >= previous | Decrease: `CRITICAL` |
| `bond_constraints` length | >= previous | Decrease: `CRITICAL` (unless advisory) |
| `grouped_hmbc` length | >= previous | Decrease: `CRITICAL` |
| `deff_fexp` | Track status changes | Previous "applied", current missing or null: `CRITICAL`. Previous "applied", current "discarded": `INFO` (normal zero-solution fallback; check that `conflict_reason` is populated). Previous "none", current "applied": normal (fragment found). |

### Check 3: content preserved

Every item in the previous iteration's arrays exists in the current ones. For the array fields
(`bond_constraints`, `cosy_equiv_pairs`, `grouped_hmbc`, each batch in `hmbc_batches`), check that
every string in the previous array appears in the current array. A missing item: `CRITICAL`. For
ring exclusion, check that `ring_exclusion_enabled` stays true across iterations and that the three
DEFF F1/F2/FEXP lines are present verbatim.

### Check 4: ELIM budget sanity

Extract `elim_budget` from the constraint inventory (0 if absent).

**G-ELIM-1: excessive ELIM N without documented escalation history.** Take the iteration count
from the inventory and check the `[ITERATION-COMPLETE]` history in CASE-PROGRESS.md. If
`elim_budget > 3` and no earlier `[ITERATION-COMPLETE]` documents the N=1, 2 and 3 attempts:
`WARNING` — "Excessive ELIM N without documented escalation history. Confirm N=1, N=2, N=3 were
tried first per the ELIM Escalation procedure."

**G-ELIM-2: HMBC with an explicit bond range is immune to ELIM.**

```bash
grep -cE "^HMBC [0-9]+ [0-9]+ [0-9]+ [0-9]+" analysis/iteration_NN/compound.lsd
```

If any HMBC line contains an explicit bond range (4 numeric arguments) and `ELIM` is present:
`WARNING` — "HMBC with explicit bond range is immune to ELIM. Use plain `HMBC X Y` (no range) so
ELIM can act on it (LSD manual line 549)."

**G-ELIM-3: ELIM added in the first iteration before all HMBC lines are included.** If ELIM is
present in iteration 1 (inventory `iteration == 1`) and `elim_budget > 0`: `WARNING` — "ELIM should
only be added after all HMBC are included and 0 plausible solutions remain. Escalate per the ELIM
Escalation procedure."

**G-ELIM-4: plain COSY equivalence pairs can be dropped by ELIM.**

```bash
grep -E "^COSY [0-9]+ [0-9]+[[:space:]]*(;|$)" analysis/iteration_NN/compound.lsd | grep -c "equiv-pair"
```

If any aromatic COSY equivalence pair (tagged `; equiv-pair`) is written as plain `COSY X Y` (no
explicit range, only 2 numeric arguments) and ELIM is present: `WARNING` — "Plain `COSY X Y` is
ELIM-droppable. Write `COSY X Y 3 3` to protect aromatic equivalence pairs from elimination (LSD
manual line 521)."

All G-ELIM gates are `WARNING`, not `CRITICAL`. They flag procedural deviations and do not block the
solver run.

### Check 5: failure-mode gates

These gates detect specific failure modes. G7 is a hash check that the LSD engineer performs.

### G7: file modified after validation

Severity `CRITICAL`; the LSD engineer's self-check, not a check the DA runs itself. The DA puts the
file hash into its `[VALIDATION-PASSED]` message, and the LSD engineer verifies the hash before it
invokes the solver.

The DA's part: with `[VALIDATION-PASSED]`, compute the file hash and include it.

```bash
FILE_HASH=$(md5sum analysis/iteration_NN/compound.lsd 2>/dev/null \
  || md5 -q analysis/iteration_NN/compound.lsd 2>/dev/null)
```

Add to the `[VALIDATION-PASSED]` message:

```
File hash at approval: <FILE_HASH>  (md5)
```

The LSD engineer's part, before running the solver: recompute the file hash and compare it with
the hash in the `[DA-APPROVED]` relay message from the coordinator. If the hashes differ, do not
run the solver; send a `CRITICAL` error to the coordinator.

Trigger: the hash at solver invocation differs from the hash at DA approval: `CRITICAL` (the LSD
engineer blocks the run).

Why: the LSD file may be modified after DA approval; this check detects that.

### G-PROP-EVIDENCE: hard heteroatom constraint without evidence

Severity `CRITICAL`.

Trigger: the LSD file contains a hard heteroatom constraint (`PROP X O`, `PROP X N`, or
`BOND X O`/`BOND X N` outside the carbonyl exception for Cq at 160-220 ppm), and the constraint
inventory's `applied_from_detection` entry for it does not cite (i) direct connectivity evidence
(HMBC, HSQC or exchangeable H) or (ii) convergent multi-source corroboration (Cq + 160-220 ppm
shift + C=O context + O in the formula).

Step 1: detect the hard heteroatom constraints.

```bash
grep -E "^PROP [0-9]+ (O|N)" analysis/iteration_NN/compound.lsd
grep -E "^BOND [0-9]+ [0-9]+" analysis/iteration_NN/compound.lsd
```

For BOND lines, cross-reference the MULT definitions to see whether a BOND atom is a heteroatom.
If there is no hard heteroatom constraint, the gate passes.

Step 2: for each hard heteroatom constraint, look up its entry in the inventory's
`applied_from_detection` array (see Extract the inventory above). The constraint passes if the
entry cites one of:
- 'HMBC': a direct 2-3J correlation establishing adjacency to the heteroatom-bearing carbon
- 'HSQC Cq' with '160-220 ppm': Cq confirmed in the carbonyl region (the carbonyl exception; BOND
  C=O is permitted)
- 'exchangeable H': OH or NH confirmed independently

Step 3: sub-checks, each of which triggers `CRITICAL` on its own:

- **(a) constraint_type is 'typical':** the inventory entry cites a detect-neighbours value but the
  constraint_type for that element is 'typical' (about 0.5-0.9, not 'mandatory' >= 0.95):
  `CRITICAL` — "G-PROP-EVIDENCE: constraint_type 'typical' is advisory-only; a borderline
  heteroatom probability is never a sufficient basis for a hard constraint without converging
  direct evidence."
- **(b) Carbon is the dominant neighbour:** the inventory entry shows carbon as the
  highest-frequency element at the queried shift: `CRITICAL` — "G-PROP-EVIDENCE: carbon is the
  dominant neighbour at this shift; heteroatom placement is uncertain. A carbon-dominant shift must
  be left open unless direct connectivity evidence establishes the heteroatom."
- **(c) Renormalised probability:** the constraint inventory records a heteroatom frequency that
  does not match the raw detect-neighbours output for that shift, or cites an 'after X-exclusion'
  or recalculated percentage: `CRITICAL` — "G-PROP-EVIDENCE: renormalized/inflated
  detect-neighbours probability detected. Only raw tool output values are permitted. Recalculating
  by excluding elements is fabrication."

Step 4: without an inventory (legacy fallback), check CASE-PROGRESS.md for a documented
direct-evidence or convergent-evidence citation. If there is none: flag `CRITICAL`.

Message template for the `CRITICAL` finding:

```
G-PROP-EVIDENCE: Hard heteroatom constraint [{constraint}] lacks sufficient evidence. Permitted basis: direct HMBC/HSQC/exchangeable-H OR convergent corroboration (Cq + 160-220 ppm + C=O context). Found only: [{cited_evidence}]. Remove the constraint or supply qualifying evidence.
```

The gate blocks the solver run: an incorrect hard heteroatom PROP or BOND excludes the correct
solution, and 13C ranking cannot recover from it.

Why: the failure mode is an agent that reads a borderline 'typical' heteroatom frequency, inflates
it by renormalisation and emits a hard constraint, while carbon is actually the dominant
neighbour, consistent with a carbon substituent at that shift. An open placement lets LSD generate
all variants, and ranking then discriminates correctly.

## Detection coverage

Review the `pending_from_detection` array in the inventory:
- If an item has been pending for 3 or more iterations (compare the `iteration` numbers between
  inventories): flag `WARNING` -- "Detection result '{item}' pending since iteration N, now
  iteration N+3. Review whether to apply or mark not_applicable."
- This catches signal grouping that was never applied and detection results that were never
  translated into constraints.

## Inventory-based form of the failure-mode checks

The inventory is a structured source of truth for the failure-mode checks (ring exclusion, signal
grouping, grouped HMBC notation, detection constraints). With an inventory, use these
inventory-based checks instead of, or in addition to, the grep-based ones:

- **Ring exclusion block present:** use the inventory's `ring_exclusion_enabled` field as the
  source of truth. Check 1 confirms `grep -c "^DEFF F"` >= 2 and `grep -c "^FEXP"` == 1 when it is
  enabled; Check 2 confirms that `ring_exclusion_enabled` does not revert from true to false. An
  older inventory with a non-empty `deff_not_patterns` means the file still carries `DEFF NOT`
  lines: `CRITICAL` (LSD `error 150`); rewrite them as the native DEFF F1/F2 + FEXP block.
  Without inventory (legacy): the grep-based count comparison of the ring exclusion check.
- **Signal grouping applied:** check the `pending_from_detection` array. Grouping that was detected
  but never applied stays pending and triggers the `WARNING` above after 3 iterations.
  Without inventory (legacy): cross-reference the NMR chemist's detection message with the COSY
  equiv-pair constraints and the grouped HMBC notation in the file.
- **Grouped HMBC notation kept:** use the inventory's `grouped_hmbc` array. Check 2 confirms that
  the count never decreases; Check 3 confirms that each grouped correlation is preserved.
  Without inventory (legacy): compare the counts of `^HMBC (` between iterations.
- **Detection constraints present:** check `applied_from_detection` and `pending_from_detection`.
  If detection ran (non-empty `detection_results`) but both arrays are empty: flag `INFO` "No
  detection results were translated to constraints or marked pending."
  Without inventory (legacy): cross-reference the NMR chemist's detection message by hand.
