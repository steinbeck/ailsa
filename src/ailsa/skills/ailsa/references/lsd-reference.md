# LSD reference

How the CASE team writes LSD input: the commands and their syntax, the filter block, running
`ailsa lsd run` and reading the solution count. The LSD engineer reads it before writing the first
LSD file; the devil's advocate (DA) and the diagnostic specialist check LSD files against it. Under
each command, "When this fails" says what a wrong line does and how to find it.

Syntax examples use atom numbers and shifts only. Everything after `;` on a line is a comment.

## Contents

- File layout
- MULT: atom definitions
- HSQC and HMQC: direct C-H attachment
- HMBC: long-range correlations
- BOND, LIST, ELEM and PROP
- Heteroatom constraints need evidence
- Equivalent atoms: BOND and COSY instead of SYME
- Hybridisation: an even number of sp2 atoms
- ELIM escalation: tolerance for 4J correlations
- Filter block: ring exclusion and the single FEXP line
- Running LSD
- Solution count
- Checklist before every run

## File layout

One LSD file per run, `analysis/iteration_NN/compound.lsd`, in this order:

```
; === CONSTRAINT INVENTORY v2 === ... ; === END CONSTRAINT INVENTORY ===
MULT ...                 ; one line per non-hydrogen atom
DUPL 1
MAXS 20000
HSQC ...                 ; all HSQC lines before the first HMBC line
HMBC ...
BOND / LIST / ELEM / PROP ...
ELIM N 0                 ; only after ELIM escalation, after the last HMBC line
DEFF F1 "ring3"          ; filter block: after the correlations, before EXIT
DEFF F2 "ring4"
FEXP "NOT F1 AND NOT F2"
EXIT
```

## MULT: atom definitions

```
MULT index element hybridisation hydrogens
MULT 1 C 2 0    ; 168.2 carbon, sp2, 0H (quaternary)
MULT 2 C 2 1    ; 128.5 carbon, sp2, 1H (CH)
MULT 3 C 3 3    ; 21.3 carbon, sp3, 3H (CH3)
MULT 4 N 3 0    ; nitrogen, sp3, 0H
MULT 5 O 2 0    ; oxygen, sp2, 0H (carbonyl)
MULT 6 O 3 1    ; oxygen, sp3, 1H (hydroxyl)
```

- Elements: C, N, O, S, and others depending on the LSD version. Hydrogens: the number of H
  atoms on this atom.
- Hybridisation: `2` = sp2 (double bonds, aromatic, carbonyl), `3` = sp3 (single bonds only).
  LSD's number counts double bonds: 3 = none, 2 = one.
- Shift in the comment: on every carbon's MULT line the comment starts with that carbon's
  measured 13C shift, as above. The atom-by-atom ranking (`ailsa lsd rank --assigned`, run by the
  solution analyst) reads it there.
- Bridgehead carbon: sp3 with 0 H (`C 3 0`). It takes part in a ring fusion but is not a
  quaternary sp2 carbon; marking it sp2 is a common error.
- Nitrogen: a pyridine-type ring N is sp2. A pyrrole-type N-H is `N 3 1`, because a pyrrole N has
  no double bond in the Kekulé structure; `N 2 1` gives an odd sp2 count and aborts the run
  (`error 390`). Amine N (NR3, NR2H, NRH2) and the N of an N-methyl amide are sp3; a nitro N is
  sp2. Confusing an amine (sp3) with an imine (sp2) is a common error.

When this fails. MULT fixes atom type, valence and which atoms can carry double bonds.
- Wrong hybridisation: odd sp2 count, 0 solutions.
- Wrong hydrogen count: the H budget does not match the formula, 0 solutions.
- Wrong element: impossible bonding pattern, 0 or 1000+ solutions.
- To find it: count the sp2 atoms (the count is even), add up the MULT hydrogens (they equal the
  formula's H) and check that the heteroatom count matches the formula.

## HSQC and HMQC: direct C-H attachment

```
HSQC 2 2    ; carbon 2 has a directly attached proton (defines H-2)
```

- Syntax `HSQC atom proton`; `HMQC` is the same command. The proton gets the number of the atom it
  sits on: `HSQC 5 5` means carbon 5 carries H-5.
- One HSQC line per atom. A CH2 or CH3 gets a single `HSQC X X`; MULT already gives the H count. A
  CH2 with two proton shifts (diastereotopic) still gets one line. A second `HSQC X X` for the
  same atom aborts the run (`error 234`, "atom X already correlates with H-X").
- Order: write all HSQC lines before the HMBC lines. This is a convention for readable files;
  LSD 3.4.9 accepts either order.
- Heteroatom protons: any proton used as the H-side of an HMBC line needs its own `HSQC X X`
  first, including exchangeable OH/NH protons, where X is the heteroatom index, not a carbon.
  Omitting it does not merely drop the correlation, it aborts the run (`exit 255, error 250`,
  "H-X is not defined by an HMQC command").

```
MULT 17 O 3 1   ; hydroxyl oxygen, 1H
HSQC 17 17      ; required before any `HMBC ? 17` -- defines H-17
HMBC 5 17       ; chelated OH proton -> C5
```

These HSQC lines on heteroatoms are information-free: they declare that the H exists, they do
not assert connectivity. Emit them for every OH/NH proton you correlate; do not skip one to
"avoid injecting connectivity". Why this holds, as verified against LSD itself: the HMBC handler
opens with `non_nul(250, hestvalide(p2), ...)`; `hestvalide()` reads `htoc[]`, which only the
HSQC/HMQC handler writes, and its checks carry no element restriction, so O and N are legal as
the first field. A declared heteroatom proton leaves the solution count unchanged (no false
connectivity), and its HMBC lines stay active (an unsatisfiable variant gives no solution, a
4-bond variant gives `error 293`).

When this fails. HSQC fixes the direct one-bond C-H connectivity.
- A protonated carbon without its HSQC line is treated as quaternary: wrong structure.
- HSQC on a quaternary carbon: impossible constraint, 0 solutions.
- An HMBC proton without its own HSQC line: `error 250`. Two HSQC lines for one atom: `error 234`.
- To find it: compare the HSQC count with the protonated carbon count from DEPT-135; check that
  every HMBC proton has an HSQC line and no atom has two; cross-check the HSQC positions against
  the DEPT carbon positions.

## HMBC: long-range correlations

```
HMBC 1 2       ; carbon 1 correlates with the proton on carbon 2 (standard 2-3J)
HMBC (5 6) 10  ; H-10 correlates with C5 or C6 (grouped, ambiguous carbon)
```

- Syntax `HMBC carbon proton`. LSD reads it as "the carbon is 2 or 3 bonds away from the proton".
- Grouped notation puts the alternatives in parentheses on the carbon side only; a grouped proton
  side aborts LSD (`error 116`).
- 1J leakthrough: an HMBC peak at the same (C, H) position as an HSQC peak, within ±1.5 ppm
  (carbon) and ±0.3 ppm (proton), is a direct-bond correlation that leaked into the HMBC. LSD
  then reads "1 bond from HSQC and 2-3 bonds from HMBC", an impossible constraint, and finds 0
  solutions. Fix: remove that HMBC line.

When this fails. HMBC fixes the long-range connectivity.
- A 1J artefact included: 0 solutions.
- An ambiguous carbon assignment (close peaks): wrong connectivity, wrong structure.
- Too many HMBC lines: over-constrained, 0 solutions. Too few: under-constrained, 1000+ solutions.
- To find it: compare each HMBC correlation with all HSQC positions (the 1J check); look for
  carbons less than 3 ppm apart, which may be misassigned; check that every HMBC proton has its
  HSQC line.

## BOND, LIST, ELEM and PROP

```
BOND 1 14       ; atom 1 bonded to atom 14
LIST L1 1 2     ; list of atoms 1 and 2
ELEM L2 O       ; list of all oxygens
PROP L1 1 L2    ; each atom in L1 has exactly 1 neighbour from L2
```

- `BOND a b` fixes one bond between two named atoms, for known connectivity (for example a
  carbonyl carbon to a specific O, or an N-CH3 attachment). BOND is rigid (exact atoms); LIST and
  PROP are flexible (any atom from a list). A bond to a heteroatom follows the evidence rule in
  the next section.
- `LIST name atoms` names a set of atoms; `ELEM name element` is the set of all atoms of one
  element. Both exist to be used in a PROP.
- `PROP list1 count list2`: each atom in list1 has exactly `count` neighbours from list2.
  `PROP L1 1 L2 +` means at least 1, `PROP L1 1 L2 -` at most 1, and `PROP L1 0 L2` means all
  neighbours are in L2. The first field can also be one atom (`PROP 12 1 L2`). Lists are numbered
  `L1` to `L20` and hold only non-hydrogen atoms; a name such as `L_O` aborts the run
  (`error 114`).
- PROP serves functional-group constraints and ambiguity from close carbons. Whether a PROP may
  place a heteroatom is decided by the evidence rule in the next section.

When this fails.
- BOND between atoms that cannot bond, a BOND that contradicts the HMBC connectivity, or too many
  BONDs: 0 solutions. To find it: check that the bonded atoms are chemically compatible (C-O and
  C-C yes; C-H goes through HSQC, not BOND), that no BOND conflicts with an HMBC correlation, and
  that no BOND creates impossible ring strain.
- LIST with wrong atoms: wrong PROP, wrong structure. A LIST that no PROP uses is harmless. To
  find it: check that each LIST is used in a PROP and every atom in it is defined by MULT.
- ELEM for an element the formula lacks: empty list, the PROP has no effect. An ELEM that no PROP
  uses is harmless. To find it: check the element against the formula and the ELEM's use in a
  PROP.
- PROP with a wrong count in either direction excludes the true structure (the count is exact
  unless `+` or `-` is appended): 0 solutions or only wrong ones. Wrong lists give a wrong
  structural class. To find it: check that the count matches chemical logic (a carbonyl carbon
  has 1 oxygen neighbour, not 2), that both lists are defined before the PROP, and that the
  expected structure satisfies it.

## Heteroatom constraints need evidence

The DA's gate G-PROP-EVIDENCE enforces this rule: no hard heteroatom PROP or BOND from a single
statistical detection value. A hard heteroatom constraint (`PROP X O n`, `PROP X N n`, or any
`BOND` to a heteroatom outside the carbonyl exception) requires one of:

1. Direct connectivity evidence: an HMBC correlation establishing adjacency to a
   heteroatom-bearing carbon, an HSQC absence confirming Cq combined with the formula's O/N count
   and the shift range, or an exchangeable H peak confirming OH/NH.
2. Convergent multi-source corroboration (carbonyl exception only): Cq confirmed by DEPT/HSQC,
   shift in 160-220 ppm, unambiguous C=O context (ester, acid or amide chemistry from the
   formula), and O present in the formula. This is the one case where a detect-neighbours O value
   contributes to a hard BOND, because three independent sources converge. Emit `BOND X O` (C=O)
   in this case only.

The G-PROP-EVIDENCE gate blocks these patterns:
- Citing a single detect-neighbours "typical" probability (about 0.5-0.9) as the sole basis for
  PROP or BOND.
- Renormalising or inflating a detect-neighbours frequency (excluding elements and recalculating
  to a higher percentage). Use the raw tool output only.
- Emitting a hard heteroatom constraint when carbon is the dominant neighbour at that shift (the
  highest frequency in the detect-neighbours distribution).
- Citing detect-neighbours alone for any shift in the 145-160 ppm aromatic range, which is
  ambiguous: ring O versus a benzylic or electron-donating substituent.

When uncertain, leave the heteroatom placement open. Use LIST/ELEM/PROP only when direct HMBC
connectivity is established. Let LSD explore the alternatives; the 13C ranking (`ailsa lsd rank`)
discriminates. An incorrect hard PROP excludes the correct solution, and ranking cannot recover
from that.

## Equivalent atoms: BOND and COSY instead of SYME

SYME is not a native LSD 3.4.9 command: it aborts the run with `error 102` (unknown command). Do
not write SYME to an LSD file. Encode equivalence with native BOND and COSY lines:

| Equivalence | Native encoding |
|-------------|-----------------|
| Gem-dimethyl or isopropyl (two CH3 on the same parent CH) | `BOND p m1` and `BOND p m2` |
| Aromatic CH equivalent pair (para-disubstituted ring) | `COSY a b 3 3  ; equiv-pair` |
| Homotopic CH2 (both H on the same carbon) | no line: MULT defines both protons at one atom index |

```
BOND p m1       ; gem-dimethyl: first CH3 group on parent carbon p (illustrative)
BOND p m2       ; gem-dimethyl: second CH3 group on the same parent p (illustrative)
COSY a a' 3 3   ; aromatic CH pair equivalence  ; equiv-pair  (illustrative)
COSY b b' 3 3   ; aromatic CH pair equivalence  ; equiv-pair  (illustrative)
```

- Why it matters: equivalent atoms that are not encoded are treated as independent, which gives a
  permutation explosion (1000+ solutions). The BOND and COSY lines apply the same topological
  pressure that SYME was meant to, natively.
- Tag every equivalence-derived COSY line with the comment `; equiv-pair`. The DA uses it to tell
  equivalence COSY from peak-data COSY: `grep -c "^COSY.*; equiv-pair" compound.lsd`.
- Write every equivalence COSY with the explicit 3-bond range, `COSY X Y 3 3`, not plain
  `COSY X Y`. With `ELIM N 0` (no bond-distance limit) a plain `COSY X Y` is a candidate for
  elimination and may be dropped. The LSD manual (line 521) says a correlation with an explicit
  bond range is never eliminated, so `COSY 4 7 3 3` locks the pair and keeps the aromatic ring
  emerging.

Derive the cross-ring pairs with the CLI tool; do not hand-derive the atom indices:

```bash
ailsa detect aromatic-cosy "<shifts>" --multiplicities "<mults>"
```

Example (illustrative: a para-disubstituted ring with two equivalent CH pairs at equal shifts):

```bash
ailsa detect aromatic-cosy "135.20,135.20,128.10,128.10" --multiplicities "CH,CH,CH,CH"
# Output: COSY X Y    (illustrative atom indices)
#         COSY X' Y'
```

The tool uses the reversed-sort algorithm and outputs cross-ring pairs only (from different
chemical-shift groups), never within-group pairs. Write each output line as `COSY X Y 3 3` with
`; aromatic CH pair equivalence  ; equiv-pair` appended. Hand-derived indices risk within-group
pairs (for example `COSY 4 5` instead of `COSY 4 7`), which cause LSD `error 283` when ring BONDs
are also present; the tool prevents that error class.

When this fails. Symmetry was detected but the file has no `COSY ... ; equiv-pair` or
`BOND ... gem-dimethyl` lines: the encoding is missing and the solutions multiply. To find it:
check CASE-PROGRESS.md for symmetry or grouping notes and check that the paired atoms have the
same multiplicity (both CH, both CH3).

## Hybridisation: an even number of sp2 atoms

LSD requires an even number of sp2 atoms: each double bond connects two sp2 atoms. Count all sp2
atoms, heteroatoms included, before running. If the count is odd, adjust one atom.

## ELIM escalation: tolerance for 4J correlations

`ELIM P1 P2`: P1 is the maximum number of correlations that may be eliminated, P2 the maximum
bond distance (0 = no limit). P2 is always 0.

ELIM is the native 4J tolerance mechanism. `ELIM N 0` lets the solver drop up to N HMBC or COSY
correlations internally: it tries every subset of at most N dropped correlations and accepts a
solution if any such subset leaves the remaining constraints satisfied. No pre-classification of
4J candidates is needed. ELIM deliberately widens the solution set; the plausibility check and the
HOSE-based ranking discriminate.

Escalate step by step:

0. First run: all MULT + HSQC + heteroatom lines + the DEFF/FEXP filter block + HMBC (every
   correlation as a standard `HMBC X Y`, no bond-range extension). No ELIM.
1. If there are 0 plausible solutions and all other checks pass (sp2 count, H budget, formula):
   add `ELIM 1 0` and re-run.
2. If still 0: replace it with `ELIM 2 0` and re-run.
3. If still 0: replace it with `ELIM 3 0` and re-run.
4. If still 0 at N=3: escalate to the diagnostic specialist (a constraint conflict, not 4J).

Stop at the smallest N that yields at least 1 plausible solution; do not continue escalating.
"Plausible" means: an aromatic ring is present if at least 4 shifts lie in 110-160 ppm, and the
DBE is consistent with the formula. N=3 is the ceiling; document each escalation in
`[ITERATION-COMPLETE]`.

Do not use an explicit bond range such as `HMBC X Y 2 4`: such lines are immune to ELIM (LSD
manual line 549: a correlation with an explicit range is never eliminated, even with ELIM
present).

To see which correlations ELIM dropped, run
`ailsa lsd analyze compound.sol compound.lsd --format json`. It shows the path lengths in each
accepted solution; the correlations with `j_coupling >= 4` are the dropped ones.

When this fails. Each of these is a `WARNING`:
- ELIM N > 3 without documented prior escalation in `[ITERATION-COMPLETE]`.
- ELIM in iteration 1, before all HMBC lines are added.
- ELIM present while an HMBC line has an explicit bond range (4 numeric fields): that line is
  immune to ELIM.
- ELIM present while equivalence COSY pairs lack the explicit `3 3` range: ELIM may drop aromatic
  ring pairs.

## Filter block: ring exclusion and the single FEXP line

Add the filter block to every LSD file after the correlations, before EXIT. Ring exclusion uses
pre-built filter files bundled with the ailsa package in `src/ailsa/lsd/filters/`.
`ailsa lsd run` (through `LSDInputGenerator.write_file()`) copies ring3 and ring4 into the
iteration directory, so the relative paths below resolve when LSD runs from `iteration_NN/`.

The standard ring exclusion block goes into every file:

```
DEFF F1 "ring3"    ; exclude 3-membered rings (cyclopropane, aziridine, thiirane, epoxide)
DEFF F2 "ring4"    ; exclude 4-membered rings (cyclobutane, azetidine, thietane, oxetane)
FEXP "NOT F1 AND NOT F2"
```

- F1 and F2 are reserved for ring exclusion. A fragment goodlist uses F3 and above; do not assign
  F1 or F2 to a fragment DEFF line.
- One FEXP line: LSD accepts a single FEXP line per file; a second one aborts the run
  (`error 402`, "Attempting to redefine the filter expression"). Every filter goes into that one
  expression. With a fragment goodlist (F3) the block is:

```
DEFF F1 "ring3"
DEFF F2 "ring4"
DEFF F3 "fragment_abc123def456.lsd"
FEXP "F3 AND NOT F1 AND NOT F2"
```

- Keep all DEFF lines and the FEXP line together in this block after the correlations, before
  EXIT. LSD reads them anywhere before EXIT; one block makes them easy to check.
- Exception: remove the DEFF F1 ring3 exclusion only if the 13C spectrum shows 45-55 ppm and the
  formula has O (possible epoxide; let LSD explore). Adjust the FEXP line to `FEXP "NOT F2"`
  (with a fragment: `FEXP "F3 AND NOT F2"`).
- The DEFF and FEXP lines must persist across all iterations. Dropping them is a well-documented
  constraint-loss failure mode.
- `DEFF NOT C1CC1` (SMARTS syntax) is not native and aborts LSD (`error 150`). Do not write
  `DEFF NOT`.

## Running LSD

Run LSD through `ailsa lsd run` from the iteration directory. It produces `solutions.smi`
automatically; no manual `outlsd 5 < compound.sol > solutions.smi` call is needed on the primary
path. `outlsd` is still used internally by the runner; `ailsa lsd check` verifies that it is
available.

## Solution count

| Count | Meaning | Action |
|-------|---------|--------|
| 0 | Over-constrained | Check sp2 even, H budget, HMBC correct, formula |
| 1 | Ideal | Verify chemical sense |
| 2-10 | Good | Rank to identify the best |
| 10-100 | Under-constrained | Add more HMBC |
| >100 | Severely under-constrained | Review all constraints |

## Checklist before every run

1. All carbons from the 13C spectrum defined with MULT.
2. Heteroatoms from the formula added.
3. The sp2 count is even.
4. HSQC before HMBC in the file.
5. HMBC references only defined H positions: every H-side atom has its own `HSQC X X`, including
   exchangeable OH/NH protons on heteroatom indices (a missing one aborts the run with
   `exit 255, error 250`; it does not merely drop the correlation).
6. Heteroatom constraints: BOND for C=O only when convergent evidence confirms it (Cq via
   DEPT/HSQC, 160-220 ppm shift, unambiguous C=O context, O in the formula: three independent
   sources). Leave every other heteroatom placement open unless direct HMBC, HSQC or
   exchangeable-H evidence establishes the connectivity. Do not emit `PROP X O n` or a hard
   heteroatom BOND from a single detect-neighbours value, especially a "typical" (about 0.5-0.9)
   value or when carbon is the dominant neighbour. The DA's G-PROP-EVIDENCE gate blocks it.
7. No ELIM on the first run. ELIM is added only after all HMBC lines are included and 0 plausible
   solutions remain (see ELIM escalation).
8. Ring exclusion DEFF F1 "ring3" and DEFF F2 "ring4" present, and exactly one FEXP line:
   `FEXP "NOT F1 AND NOT F2"`, or `FEXP "F3 AND NOT F1 AND NOT F2"` with a fragment.
9. The constraint inventory block is present at the top of the file with correct counts.
10. If a fragment is applied: DEFF F3 in the filter block, F3 in the one FEXP line, and the
    fragment .lsd file in the iteration directory (F3 = fragment goodlist; F1 and F2 = ring
    exclusion, separate namespaces).
11. One HSQC line per protonated atom (no atom twice).
