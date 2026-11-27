# Diagnosing a solution explosion

The systematic procedure the diagnostic specialist runs when LSD returns 1000+ solutions. Run all
five checks in order and document every result, PASS or FAIL. Do not stop at the first PASS: the
root cause may sit in a later check or be a combination of factors.

Each check ends with what to write into the report. Shifts and atom numbers in the examples are
illustrative.

## Contents

- Check 1: ELIM presence
- Check 2: constraint-to-atom ratio
- Check 3: quaternary carbon connectivity
- Check 4: heteroatom position constraints
- Check 5: symmetry encoding

## Check 1: ELIM presence

Procedure:
1. Search the LSD file for the `ELIM` keyword.
2. If it is there, note its parameters (P1, P2) and the current iteration number.

```bash
grep -n "^ELIM" compound.lsd

; If found:
ELIM 2 0    ; allows elimination of up to 2 correlations (N=2 budget)
```

If ELIM is found: ELIM is expected when zero-solution recovery reached ELIM escalation (all HMBC
added, 0 plausible solutions, then `ELIM 1 0`, `ELIM 2 0`, `ELIM 3 0`). It is the 4J tolerance
mechanism: large solution sets are expected and are handled by the plausibility pre-filter and the
HOSE ranking. ELIM presence alone is not a failure.

Check for these `WARNING` conditions:
- ELIM N > 3: `WARNING`, "Excessive ELIM N without documented prior escalation. Confirm N=1, N=2,
  N=3 were tried first (check [ITERATION-COMPLETE] history). N=3 is the recommended ceiling."
- ELIM present in iteration 1, before all HMBC lines are added: `WARNING`, "ELIM should only be
  added after all HMBC are included and 0 plausible solutions remain. Check iteration history."
- ELIM present while an HMBC line has an explicit bond range (4 numeric arguments in the HMBC
  command): `WARNING`, "HMBC with explicit bond range is immune to ELIM (LSD manual line 549). Use
  plain `HMBC X Y` so ELIM can act on it."

Document in the report:
- Finding: "ELIM command detected at N=[P1]"
- Evidence: "ELIM [P1] 0 at line [X]; iteration=[N]; documented prior escalation=[yes/no]"
- Assessment: "Expected (4J tolerance mechanism)" or "WARNING: [specific condition above]"

## Check 2: constraint-to-atom ratio

Procedure:
1. Count the atoms from the MULT commands.
2. Count the HMBC correlations.
3. Calculate the ratio HMBC_count / atom_count.
4. Compare it with the thresholds.

```
MULT commands: 16 atoms (13 C, 2 O, 1 N)
HMBC commands: 3 correlations

Ratio: 3 / 16 = 0.19 (< 0.5) → INSUFFICIENT ✗ FAIL
```

Ratio thresholds:
- Below 0.3: severely under-constrained (expect 1000+ solutions).
- 0.3-0.5: under-constrained (expect 100-1000 solutions).
- 0.5-1.0: adequately constrained (expect 10-100 solutions).
- Above 1.0: well-constrained (expect 1-10 solutions).

If the ratio is below 0.5 (FAIL). Root cause: too few HMBC correlations to constrain the structure.

Fix guidance:

```
Target ratio: 0.5-1.0 for adequate constraint

For 16 atoms:
  Current: 3 HMBC (ratio 0.19)
  Target: 8-16 HMBC (ratio 0.5-1.0)
  Need: Add 5-13 more HMBC correlations

Follow incremental HMBC strategy:
1. Select 3-5 high-confidence correlations per batch
2. Prioritize:
   - Isolated carbon shifts (>3 ppm from nearest neighbor)
   - Unique proton assignments
   - Strong peak intensity (top quartile)
   - Quaternary carbon connections (see the quaternary carbon check below)
```

Document in the report:
- Finding: "Insufficient HMBC constraints"
- Evidence: "HMBC count = [X], Atom count = [Y], Ratio = [Z] (< 0.5 threshold)"
- Impact: "Structure is severely under-determined → 1000+ solutions"
- Fix: "Add [N] more high-confidence HMBC correlations to reach ratio 0.5-1.0" (with the selection
  criteria)

## Check 3: quaternary carbon connectivity

Procedure:
1. Identify all quaternary carbons (MULT with 0 H, no HSQC).
2. Count the HMBC correlations involving each of them.
3. Flag a quaternary carbon with 0 HMBC as a "floating atom".

```
Quaternary carbons (from MULT with hydrogen count = 0):
- Atom 1 (C155.2 ppm, sp2, 0 H) → quaternary aromatic
- Atom 8 (C172.4 ppm, sp2, 0 H) → quaternary carbonyl

HMBC correlations:
- HMBC 5 12  ; C138.5-H12 (not quaternary)
- HMBC 9 12  ; C127.3-H12 (not quaternary)
- HMBC 1 3   ; C155.2-H3 (quaternary atom 1) ✓

Quaternary HMBC count:
- Atom 1: 1 HMBC correlation ✓
- Atom 8: 0 HMBC correlations ✗ FAIL (floating atom)
```

If a quaternary carbon has 0 HMBC (FAIL). Root cause: quaternary carbons connect only through HMBC,
because they have no HSQC. With 0 HMBC the atom is disconnected from the structure.

Why this causes 1000+ solutions:
- LSD can place the floating atom anywhere in the structure.
- The permutations of all possible placements make the solutions explode.

Fix guidance:

```
For each quaternary with 0 HMBC:

Option 1: Targeted HMBC search
  1. Lower threshold incrementally (start 0.05, reduce to 0.04, 0.032, ...)
  2. Search in ±2.5 ppm window around quaternary shift
  3. Validate new peaks against 13C and HSQC (guided picking)
  4. Stop when 1-2 correlations found OR threshold reaches noise floor

Option 2: Shift-based constraints (if HMBC search fails)
  - For carbonyl C=O (160-220 ppm): BOND to oxygen
  - For aromatic junction (120-160 ppm): LIST/PROP to ring carbons
  - Example:
    BOND 8 13        ; C172.4 (carbonyl) bonded to O13
```

Document in the report:
- Finding: "Quaternary carbon(s) with 0 HMBC correlations"
- Evidence: "Atom [X] at [Y] ppm: quaternary, 0 HMBC correlations (floating atom)"
- Impact: "Floating atom massively increases solution space → 1000+ solutions"
- Fix: "Apply targeted HMBC threshold reduction OR add shift-based constraint" (with the LSD
  commands)

## Check 4: heteroatom position constraints

Procedure:
1. Count the heteroatoms (O, N, S) from the MULT commands.
2. Search the LSD file for BOND or LIST/PROP constraints involving heteroatoms.
3. Count the constrained heteroatoms.

```
Heteroatoms (from MULT):
- Atom 13: O (sp2)
- Atom 14: O (sp3)
- Atom 15: N (sp3)

Heteroatom constraints (search for BOND/LIST/PROP):
BOND 1 13        ; C1 bonded to O13 ✓

Constrained: 1 heteroatom (O13)
Unconstrained: 2 heteroatoms (O14, N15) ✗ FAIL
```

If heteroatoms are unconstrained (FAIL). Root cause: heteroatom positions strongly constrain the
structure; without constraints LSD tries all permutations.

Why this causes 1000+ solutions:
- For 2 unconstrained oxygens and 16 carbons, LSD tries O at positions {C1,C2}, {C1,C3}, ...,
  {C15,C16}: hundreds of permutations.
- Each permutation may yield several solutions.

Fix guidance by heteroatom type.

Carbonyl oxygen (sp2, carbon at 160-220 ppm):

```
BOND carbonyl_C oxygen_idx    ; If exact position known

; Example:
BOND 1 13    ; C172.4 (carbonyl) bonded to O13
```

Ether oxygen (sp3, adjacent carbon at 50-90 ppm):

```
; If position ambiguous, constrain the oxygen (here O13):
LIST L1 5 6 7              ; candidate C-O carbons
PROP 13 0 L1               ; all neighbours of O13 are among C5, C6, C7
```

(`PROP L1 1 L2` with L1 = candidates and L2 = oxygens would force every candidate to carry an
oxygen.)

Amine nitrogen (sp3, N-CH3 or N-CH2):

```
; If N-methyl attachment known:
BOND N_idx CH3_idx

; If ambiguous (nitrogen N14):
LIST L1 9 10 11            ; candidate N-methyl carbons
PROP 14 1 L1               ; N14 has exactly one neighbour among C9, C10, C11
```

Document in the report:
- Finding: "Unconstrained heteroatom positions"
- Evidence: "[X] heteroatoms total, [Y] constrained, [Z] unconstrained ([list elements])"
- Impact: "Unconstrained heteroatom permutations → 1000+ solutions"
- Fix: "Add BOND or LIST/PROP constraints for [heteroatom list]" (with the LSD commands and the
  functional group context)

## Check 5: symmetry encoding

Procedure:
1. Check CASE-PROGRESS.md for symmetry detection notes.
2. Compare the expected carbons (from the formula) with the observed carbons (from 13C/DEPT).
3. If symmetry was detected, check the LSD file for native symmetry encoding: BOND/COSY
   equivalence constraints (SYME is not native in LSD 3.4.9).

```
From CASE-PROGRESS.md iteration 1 notes:
"Symmetry detected: 13 carbons expected (formula), 11 observed (13C spectrum).
Difference = 2 carbons → likely one pair of equivalent carbons."

Check LSD file for native symmetry encoding:
grep -cE "^COSY.*; equiv-pair|^BOND" compound.lsd
; Returns 0 → no symmetry constraints found ✗ FAIL
; Returns > 0 → symmetry encoded (verify it matches detected equivalent atoms)
```

If symmetry was detected but not encoded (FAIL). Root cause: LSD treats the symmetric atoms as
independent, which inflates the solution space.

Why this causes 1000+ solutions:
- Without symmetry encoding, LSD explores all permutations in which equivalent atoms sit in
  different positions.
- Example: a para-disubstituted benzene ring (2 pairs of equivalent CH) without COSY equiv-pair
  constraints: LSD tries all 4! permutations, a 24-fold solution inflation.

Fix guidance: encode the equivalence with native BOND and COSY lines (SYME is not native in
LSD 3.4.9).

```
; For aromatic CH equivalent pairs (para-disubstituted ring):
COSY 5 6 3 3    ; aromatic CH pair equivalence  ; equiv-pair
COSY 7 8 3 3    ; aromatic CH pair equivalence  ; equiv-pair

; For gem-dimethyl / isopropyl (2 CH3 on same parent CH at atom 10):
BOND 10 9   ; gem-dimethyl: first CH3 (atom 9) on parent CH (atom 10)
BOND 10 11  ; gem-dimethyl: second CH3 (atom 11) on parent CH (atom 10)
```

Tag every equivalence-derived COSY line with `; equiv-pair`: the devil's advocate uses the tag to
tell equivalence COSY from peak-data COSY.

Document in the report:
- Finding: "Symmetry detected but not encoded"
- Evidence: "Expected [X] carbons, observed [Y] signals → [Z] equivalent carbons detected"
- Impact: "LSD treats symmetric atoms as independent → permutation explosion → 1000+ solutions"
- Fix: "Add BOND/COSY equivalence constraints (COSY atom1 atom2 3 3 ; equiv-pair for aromatic CH
  pairs; BOND parent CH3_1 + BOND parent CH3_2 for gem-dimethyl/isopropyl)". SYME is not native in
  LSD 3.4.9.
