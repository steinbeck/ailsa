# Pre-solver validation checks

The checks the devil's advocate (DA) runs on an LSD file before the solver may run. The first
group catches failure modes that occurred in earlier live runs; the structural integrity checks
apply to every file in every iteration. Run all of them on every validation.

Each check carries its severity: `CRITICAL` blocks the solver run, `WARNING` is flagged and the
run may proceed with a justification, `INFO` is logged. The shell snippets assume the file is
`compound.lsd` in the iteration directory.

## Contents

- Checks for known failure modes
- Ring exclusion block present
- Signal grouping applied
- COSY equivalence pairs cross the ring
- Grouped HMBC notation kept
- PROP used where documented
- Detection constraints present
- Structural integrity checks
- sp2 count parity
- H budget balance
- Correlation order
- One HSQC line per atom
- HMBC reference validity
- Badlist completeness
- Ranking prerequisites
- ELIM usage
- Fragment file existence
- Single filter expression
- Aromatic ring expectation

## Checks for known failure modes

Each of these checks catches a failure that earlier live runs produced. Run all of them on every
validation, in every iteration.

### Ring exclusion block present (`CRITICAL`)

Why: a ring exclusion block written in iteration 1 and not carried forward lets solutions with
strained three- and four-membered rings survive.

Check that `DEFF F1`, `DEFF F2` and exactly one `FEXP` line are present. If any of them is
missing: `CRITICAL`. Two or more FEXP lines: `CRITICAL` (LSD aborts with `error 402`; all filters
belong in one expression).

```bash
grep -c "^DEFF F" compound.lsd   # Must be >= 2
grep -c "^FEXP" compound.lsd     # Must be exactly 1
```

The minimum block in native form:

```
DEFF F1 "ring3"
DEFF F2 "ring4"
FEXP "NOT F1 AND NOT F2"
```

With a fragment goodlist, `DEFF F3 "<fragment file>"` is added and the line reads
`FEXP "F3 AND NOT F1 AND NOT F2"`.

`DEFF NOT` is not LSD syntax: `DEFF NOT C1CC1` aborts the run (`error 150`), and `ailsa lsd run`
passes the file to LSD unchanged. Any `DEFF NOT` line is `CRITICAL`, also in a file carried over
from an older iteration: replace it with the native block above.

### Signal grouping applied (`WARNING`)

Why: grouping detection can find close signals (for example 29.5 and 29.8 ppm) that never reach the
LSD file as COSY equivalence constraints or grouped HMBC notation.

If the NMR chemist reported signal groups, check that the grouped atoms have either:
- a COSY equivalence line (`COSY atom1 atom2  ; equiv-pair`), or
- grouped HMBC notation (`HMBC (N M)`).

### COSY equivalence pairs cross the ring (G-COSY-EQUIV, `CRITICAL`)

Why: within-group pairs (for example `COSY a b` and `COSY c d`, where a and b share one shift
group and c and d share another) instead of cross-ring pairs (`COSY a c` and `COSY b d`) put the
wrong class of topological constraint on the ring. The aromatic ring then never emerges from LSD,
and the team is pushed to explicit ring BONDs, which are a last-resort escalation.

When `COSY` lines tagged `; equiv-pair` are present, check that each pair joins atoms from
different chemical-shift groups (cross-ring), not from the same chemical-shift group
(within-group).

```bash
# Cross-ring COSY pairs derived authoritatively by:
ailsa detect aromatic-cosy "<shifts>" --multiplicities "<mults>"
# Verify COSY lines in compound.lsd match the tool output (not hand-derived alternatives)
```

`ailsa detect aromatic-cosy` is the authoritative source of aromatic equivalence pairs. If the file
has `; equiv-pair` COSY lines and no call to `ailsa detect aromatic-cosy` is documented in
CASE-PROGRESS.md or in the LSD engineer's `[ITERATION-COMPLETE]` message, flag `CRITICAL`: "COSY
equivalence pairs must be derived with ailsa detect aromatic-cosy (not hand-assigned). Within-group
pairs (both atoms at same chemical shift) cause LSD error 283 when ring BONDs are present."

Trigger: any COSY pair tagged `; equiv-pair` whose two atoms map to the same chemical-shift group
(the same ppm from HSQC): `CRITICAL`.

### Grouped HMBC notation kept (`CRITICAL`)

Why: a later iteration can revert grouped notation such as `HMBC (6 7) 2` to `HMBC 6 2`, which
turns an ambiguous correlation into an assignment to one carbon.

Count the grouped HMBC lines (`HMBC (`) in both files. If iteration N has fewer than iteration
N-1: `CRITICAL`.

### PROP used where documented (`INFO`)

Why: the progress log can announce a PROP constraint (for example "PROP constraint for O
neighbor") while the LSD file uses BOND instead.

If CASE-PROGRESS.md mentions PROP, check that the LSD file contains PROP, or that the reason for
BOND is documented. BOND instead of PROP is valid if justified.

### Detection constraints present (`WARNING`)

Why: neighbourhood detection can run and still leave only the BOND for C=O in the file, with no
PROP or LIST for the other mandatory neighbours it found.

If the NMR chemist reported mandatory neighbours beyond the carbonyl (for example C-O at 50-90
ppm), check that the corresponding PROP/LIST constraints exist in the LSD file.

## Structural integrity checks

Apply these to every LSD file regardless of the iteration number.

### sp2 count parity (`CRITICAL`)

Count all atoms with hybridisation 2 (the second number in MULT is 2). The count is even, because
each double bond joins two sp2 atoms.

```bash
grep "^MULT" compound.lsd | awk '$4 == 2' | wc -l
```

If the count is odd: flag `CRITICAL` with the list of atoms that are sp2.

### H budget balance (`CRITICAL`)

Sum the hydrogen counts of all MULT lines (the last number), including heteroatom H (`O 3 1` = 1 H,
`N 3 1` = 1 H), and compare the sum with the H count of the molecular formula.

If they differ: flag `CRITICAL` with both counts. Hint: check whether a heteroatom OH or NH is
missing.

### Correlation order (`WARNING`)

Check that all HSQC lines come before the first HMBC line.

```bash
# Get line numbers of last HSQC and first HMBC
grep -n "^HSQC" compound.lsd | tail -1  # last HSQC line
grep -n "^HMBC" compound.lsd | head -1  # first HMBC line
```

If the first HMBC line comes before the last HSQC line: flag `WARNING`. HSQC first is the house
convention; LSD accepts either order, so do not block the run for it.

### One HSQC line per atom (`CRITICAL`)

```bash
sed 's/;.*//' compound.lsd | awk '/^HSQC/ {print $2}' | sort | uniq -d   # any output = CRITICAL
```

A second `HSQC X X` for the same atom aborts the run (`error 234`).

### HMBC reference validity (`CRITICAL`)

Every HMBC correlation references atoms defined by MULT, and every proton it references is defined
by HSQC. A reference to an undefined atom: `CRITICAL`.

This includes exchangeable OH/NH protons, where the H-side index is a heteroatom, not a carbon:
`HSQC 17 17` on a hydroxyl oxygen is legal and required.

```bash
# every H-side atom of an HMBC line must carry its own HSQC declaration.
# strip `;` comments first -- they are standard in LSD files and would
# otherwise be read as the last field.
sed 's/;.*//' compound.lsd | awk '/^HMBC/ {print $NF}' | sort -u > /tmp/h_used
sed 's/;.*//' compound.lsd | awk '/^HSQC/ {print $3}'  | sort -u > /tmp/h_declared
comm -23 /tmp/h_used /tmp/h_declared   # any output = CRITICAL
```

The H-side is always the last field, so grouped C-side forms such as `HMBC (5 6) 10` are handled
correctly.

A missing declaration aborts the solver outright (`exit 255, error 250`) instead of degrading
gracefully, so run this check before release, not after a failed solve.

### Badlist completeness (`WARNING`)

For natural products, expect `DEFF F1 "ring3"`, `DEFF F2 "ring4"` and one FEXP line:
`grep -c "^DEFF F" compound.lsd` is at least 2. If not: flag `WARNING`. A `DEFF NOT` line is
`CRITICAL` (see the ring exclusion check above).

### Ranking prerequisites (`WARNING`)

The atom-by-atom ranking (`ailsa lsd rank --assigned`) needs two things in every file:
- `DUPL 1` (and `MAXS 20000`): `grep -c "^DUPL 1" compound.lsd` is 1. Without it LSD keeps
  one arbitrary atom assignment per structure.
- every carbon's MULT comment starts with its measured 13C shift:
  `grep -E "^MULT +[0-9]+ +C " compound.lsd | grep -vcE ";[[:space:]]*-?[0-9]+(\.[0-9]+)?"` is 0.

If either fails: flag `WARNING` ("atom-by-atom ranking prerequisites missing").

### ELIM usage (`WARNING`)

- ELIM is expected after all HMBC lines are added and 0 plausible solutions remain. N=1 is normal
  when 4J is suspected, and `elim_budget` > 0 is normal in later iterations.
- ELIM present in iteration 1 before all HMBC lines are added: flag `WARNING` ("ELIM should only
  be added after all HMBC are included and 0 plausible solutions remain — escalate per the ELIM
  Escalation procedure").
- ELIM N > 3: flag `WARNING` ("Excessive ELIM N; confirm N=1, N=2, N=3 were tried first per the
  ELIM Escalation procedure").

### Fragment file existence (`CRITICAL`)

This applies when the LSD file contains a `DEFF F3` (or higher) line, the goodlist fragment
reference. The ring filters `DEFF F1 "ring3"` and `DEFF F2 "ring4"` are copied into the directory
by `ailsa lsd run` and are not checked here.
1. Extract the file name from between the double quotes of the DEFF line.
2. Check that the file exists in the same directory as compound.lsd.
3. If the file is missing: flag `CRITICAL` -- "DEFF references fragment file '<filename>' but file
   does not exist in <iteration_dir>/".
4. If the file exists: check that it contains SSTR commands (a basic sanity check).

If there is no `DEFF F3` (or higher) line, check the inventory's `deff_fexp.status`:
- "applied": flag `CRITICAL` -- "Inventory claims fragment applied but no fragment DEFF command
  found in LSD file".
- "discarded", "none" or null: OK (no fragment expected).

### Single filter expression (`CRITICAL`)

If a fragment `DEFF F3` (or higher) is present:
1. `grep -c "^FEXP" compound.lsd` is exactly 1. Two FEXP lines (for example `FEXP "F3"` next to
   `FEXP "NOT F1 AND NOT F2"`): flag `CRITICAL` -- "LSD accepts one FEXP line (error 402); merge
   into `FEXP "F3 AND NOT F1 AND NOT F2"`".
2. The FEXP line names every defined filter: F3 (or the fragment's Fn) as well as
   `NOT F1 AND NOT F2`. A defined filter missing from the expression is inactive: flag
   `CRITICAL`.

Do not flag where the DEFF and FEXP lines stand in the file: LSD reads them anywhere before EXIT.

### Aromatic ring expectation (`WARNING`, after ranking)

This applies when the NMR chemist's `[SETUP-COMPLETE]` message reports "aromatic ring expected"
(at least 4 carbons in 110-160 ppm) and ranking results are available for this compound, from the
current or a previous iteration.

Data source: to see whether the NMR chemist flagged an aromatic expectation, read
`<compound_path>/analysis/CASE-PROGRESS.md` and look for the `Aromatic expectation:` field in the
NMR chemist's subsection of `## Setup`. The coordinator writes it there from the
`[SETUP-COMPLETE]` message.

Check whether the `ailsa lsd rank --format json` output has any solution with
`has_aromatic_ring: true`, or whether its `warnings` array contains an aromatic mismatch message.

If an aromatic ring is expected and all solutions are non-aromatic: flag `WARNING` — "Aromatic ring
expected from NMR but all solutions are non-aromatic. The solution analyst should flag it for 4J
HMBC removal."

This check is defence in depth: the solution analyst is the primary responder, through its
aromatic ring verification. Do not flag it as `CRITICAL`; use `WARNING` only. Do not block the
solver run for it: it is a post-ranking observation, not a pre-run validation. It applies only
when ranking results exist, so not in iteration 1 before any ranking has occurred.
