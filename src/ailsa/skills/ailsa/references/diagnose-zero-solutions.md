# Diagnosing zero solutions

The systematic procedure the diagnostic specialist runs when LSD returns no solution. Run all five
checks in order and document every result, PASS or FAIL. Do not stop at the first PASS: the root
cause may sit in a later check or be a combination of factors.

Each check ends with what to write into the report (finding, evidence, impact, fix). Shifts and
atom numbers in the examples are illustrative.

## Contents

- Check 1: the sp2 count is even
- Check 2: the hydrogen budget matches the formula
- Check 3: 1J artefacts (HMBC against HSQC)
- Check 4: HSQC declarations (every HMBC proton declared, no atom twice)
- Check 5: close carbons below the digital resolution

## Check 1: the sp2 count is even

Procedure:
1. Parse all MULT commands from the LSD file.
2. Count the atoms with hybridisation 2 (sp2).
3. Check that the count is even.

```
MULT 1 C 2 0    ; sp2
MULT 2 C 2 1    ; sp2
MULT 3 C 3 2    ; sp3 (not counted)
MULT 4 C 2 1    ; sp2
MULT 5 O 2 0    ; sp2
MULT 6 O 3 0    ; sp3 (not counted)
MULT 7 N 3 0    ; sp3 (not counted)

sp2 count: 1 + 2 + 4 + 5 = 4 atoms (EVEN) ✓ PASS
```

If the count is odd (FAIL). Root cause: no valid structure can be formed with an odd sp2 count,
because each double bond needs two sp2 atoms.

Common errors:
- An ether oxygen marked sp2 instead of sp3.
- An amine nitrogen marked sp2 instead of sp3.
- An aliphatic carbon marked sp2 instead of sp3.

Fix example:

```
; Before (ODD):
MULT 6 O 2 0    ; ether oxygen incorrectly marked sp2

; After (EVEN):
MULT 6 O 3 0    ; ether oxygen correctly marked sp3
```

Document in the report:
- Finding: "sp2 count is [N] (odd/even)"
- Evidence: "Atoms with sp2: [list atom indices]"
- Impact: "Odd count violates LSD bonding rules → 0 solutions"
- Fix: "Change atom [X] from sp2 to sp3" (with the LSD command)

## Check 2: the hydrogen budget matches the formula

Procedure:
1. Add up the hydrogen counts of all MULT commands.
2. Take the hydrogen count from the molecular formula.
3. Compare the two.

```
Formula: <formula> with 16 H

MULT 1 C 2 0    ; 0 H
MULT 2 C 2 1    ; 1 H
...
(full list)

Sum: 0+1+1+2+2+3+3+0+1+1+1+1+0+0 = 16 H
Formula: 16 H
Match: ✓ PASS
```

If the two differ (FAIL). Root cause: incorrect multiplicity assignments. The difference says which
way:
- Sum above the formula: too many hydrogens assigned.
- Sum below the formula: too few hydrogens assigned.

Common errors:
- A CH marked as quaternary (0 H instead of 1 H): 1 H missing.
- A CH2 marked as CH (1 H instead of 2 H): 1 H missing.
- A CH3 marked as CH (1 H instead of 3 H): 2 H missing.

Fix example:

```
; Sum = 19 H, Formula = 21 H → missing 2 H

; Likely: Two CH carbons marked as quaternary
; Find carbons with 0 H that should have 1 H (check HSQC presence)

; Before (WRONG):
MULT 5 C 2 0    ; marked quaternary but visible in HSQC

; After (CORRECT):
MULT 5 C 2 1    ; corrected to CH
```

Document in the report:
- Finding: "Hydrogen budget mismatch"
- Evidence: "Sum of MULT hydrogens = [X], Formula = [Y], Difference = [Z]"
- Impact: "Incorrect multiplicity prevents valid structure → 0 solutions"
- Fix: "Change atom [index] from [old H count] to [new H count]" (with the LSD command)

## Check 3: 1J artefacts (HMBC against HSQC)

Procedure:
1. Extract all HMBC correlations from the LSD file.
2. Extract all HSQC correlations from the LSD file.
3. Compare the carbon and proton shifts of each HMBC correlation with all HSQC correlations.
4. A match within the tolerance is a 1J artefact.

Tolerance: ±1.5 ppm for carbon, ±0.3 ppm for proton.

```
HSQC correlations (from guided picking or LSD file comments):
- C155.08-H2.08
- C138.51-H7.24
- C127.30-H6.95

HMBC correlations:
- C155.15-H2.12  ; Check against HSQC
- C138.50-H3.21  ; Check against HSQC
- C172.40-H2.08  ; Check against HSQC

Check C155.15-H2.12 vs HSQC C155.08-H2.08:
  Carbon difference: |155.15 - 155.08| = 0.07 ppm (< 1.5 ppm) ✓
  Proton difference: |2.12 - 2.08| = 0.04 ppm (< 0.3 ppm) ✓
  → 1J ARTIFACT DETECTED ✗ FAIL

Check C138.50-H3.21 vs HSQC C155.08-H2.08:
  Carbon difference: |138.50 - 155.08| = 16.58 ppm (> 1.5 ppm) ✗
  → Not a match, continue

Check C138.50-H3.21 vs HSQC C138.51-H7.24:
  Carbon difference: |138.50 - 138.51| = 0.01 ppm (< 1.5 ppm) ✓
  Proton difference: |3.21 - 7.24| = 4.03 ppm (> 0.3 ppm) ✗
  → Not a match (carbon matches but proton differs)
```

If an artefact is found (FAIL). Root cause: an HMBC peak at the same position as an HSQC peak is a
1J (direct-bond) correlation that leaked into the HMBC spectrum, not a 2-3 bond long-range
correlation.

Why this causes 0 solutions:
- HSQC says: "C155.2 is directly bonded to H2.1" (1 bond).
- HMBC says: "C155.2 is 2-3 bonds from H2.1" (2-3 bonds).
- LSD cannot satisfy both: impossible constraint, 0 solutions.

Fix example:

```
; Before (WRONG):
HMBC 5 12    ; C155.2-H2.1 (1J artifact)

; After (CORRECT):
; Remove the line entirely
```

Document in the report:
- Finding: "1J artifact detected"
- Evidence: "HMBC C[X]-H[Y] matches HSQC C[X']-H[Y'] within tolerance (ΔC=[d1] ppm, ΔH=[d2] ppm)"
- Impact: "Creates impossible constraint (1-bond from HSQC AND 2-3 bonds from HMBC) → 0 solutions"
- Fix: "Remove HMBC command for C[X]-H[Y]"

## Check 4: HSQC declarations (every HMBC proton declared, no atom twice)

Procedure:

```bash
sed 's/;.*//' compound.lsd | awk '/^HMBC/ {print $NF}' | sort -u > /tmp/h_used
sed 's/;.*//' compound.lsd | awk '/^HSQC/ {print $3}'  | sort -u > /tmp/h_declared
comm -23 /tmp/h_used /tmp/h_declared                                # protons used but never declared
sed 's/;.*//' compound.lsd | awk '/^HSQC/ {print $2}' | sort | uniq -d   # atoms declared twice
```

If a proton is used but not declared (FAIL): LSD aborts with `error 250`, "Cannot set an HMBC
correlation between X and H-Y because H-Y is not defined by an HMQC command". It is usually an
exchangeable OH/NH proton: add `HSQC Y Y` on the heteroatom index.

If an atom is declared twice (FAIL): LSD aborts with `error 234`, "atom X already correlates with
H-X". A CH2 with two proton shifts gets one HSQC line; MULT carries the H count. Delete the
duplicate.

The order of the HSQC and HMBC lines is not a cause: LSD 3.4.9 accepts HMBC lines before the HSQC
lines, as tested against LSD itself.

Document in the report:
- Finding: "Undeclared HMBC proton" or "Duplicate HSQC declaration"
- Evidence: "HMBC [C] [Y] uses H[Y], no HSQC [Y] [Y] in file" / "HSQC [X] [X] appears twice"
- Impact: "LSD aborts before searching (error 250 / error 234) → 0 solutions"
- Fix: "Add HSQC [Y] [Y]" / "Remove the second HSQC [X] [X]"

## Check 5: close carbons below the digital resolution

Procedure:
1. Extract all carbon shifts from the MULT commands (from their comments or supplementary data).
2. Calculate the digital resolution of the HMBC F1 dimension (from CASE-PROGRESS.md or the
   spectrum metadata).
3. Identify carbon pairs closer than the minimum distinguishable spacing.

Digital resolution:

```
resolution = data_points / ppm_range    ; points per ppm
min_spacing = 1.5 / resolution          ; minimum distinguishable spacing
```

```
HMBC F1 dimension: 512 points, 200 ppm range
Resolution: 512 / 200 = 2.56 pts/ppm
Min spacing: 1.5 / 2.56 = 0.59 ppm

Carbon shifts (from MULT comments or 13C spectrum):
- C155.08 ppm
- C155.32 ppm
- C138.51 ppm
- C172.40 ppm

Check pairs:
  C155.08 vs C155.32: |155.32 - 155.08| = 0.24 ppm (< 0.59 ppm) → UNRESOLVABLE ✗ FAIL
  C155.08 vs C138.51: |155.08 - 138.51| = 16.57 ppm (> 0.59 ppm) → resolvable ✓
  ...
```

If an unresolvable pair is found (FAIL). Root cause: an HMBC correlation assigned to one carbon may
belong to the other; the low digital resolution makes the assignment ambiguous.

Why this can cause 0 solutions: if the HMBC correlation is assigned to the wrong carbon (for
example to C155.08 when it belongs to C155.32), the constraint contradicts the true structure and
LSD finds 0 solutions.

Fix example:

```
; Before (DEFINITIVE assignment, may be wrong):
HMBC 5 12    ; C155.08-H12 (but could be C155.32-H12)

; After (AMBIGUOUS encoding, grouped carbon side):
HMBC (5 6) 12    ; H12 correlates with C5 (155.08) or C6 (155.32)
```

Group only the carbon side. `HMBC 12 (5 6)` (grouped proton side) aborts LSD (`error 116`), and a
PROP over a "proton list" does not work: LSD lists hold only non-hydrogen atoms.

Document in the report:
- Finding: "Close carbon ambiguity detected"
- Evidence: "Carbons at [X] ppm and [Y] ppm are [Z] ppm apart, below minimum spacing [W] ppm
  (resolution [R] pts/ppm)"
- Impact: "HMBC correlation may be assigned to wrong carbon → incorrect constraint → 0 solutions"
- Fix: "Use grouped HMBC `HMBC (a b) h` to encode the ambiguity" (with the LSD commands)
