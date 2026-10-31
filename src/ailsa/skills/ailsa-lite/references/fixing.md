# Fixing the problem

Every fix is one `ailsa case edit DATASET ... --reason "..."` command. Atom numbers are the
numbers in the atom table (`C7` is `7`). Correlation ids (`B12`, `Y3`) come from
`ailsa case show DATASET --correlations`.

## Contents

- [Carbon count](#carbon-count)
- [Hydrogen count](#hydrogen-count)
- [Even number of sp2 atoms](#even-number-of-sp2-atoms)
- [Too many sp2 atoms](#too-many-sp2-atoms)
- [A correlation whose proton is gone](#a-correlation-whose-proton-is-gone)
- [No structure](#no-structure)
- [Shift ranges](#shift-ranges)

## Carbon count

`C: the formula has N, the problem has M`

**Fewer carbons than the formula (M < N).** Some lines stand for two or more equivalent carbons,
or a carbon is missing from the 13C list.
- Equivalent carbons give one line that is about twice as intense. Typical cases: a benzene ring
  with two substituents opposite each other (two CH lines, each two carbons), an isopropyl or
  gem-dimethyl group (one CH3 line, two carbons), a tert-butyl group (one CH3 line, three
  carbons). Fix: `--copies ID=2` (or `=3`).
- If the report lists "Peaks with no atom" from the HSQC, that carbon is real but has no 13C
  line (too weak, or under the solvent signal). Fix: `--add-carbon SHIFT:CH` (or `:CH2`, `:CH3`).

**More carbons than the formula (M > N).** A line is noise or an impurity. Remove the weakest
line that has no proton in the HSQC and is not in a typical range for an unprotonated carbon
(see the shift ranges below). Fix: `--remove ID`.

## Hydrogen count

`hydrogens: the formula has N, the atoms carry M`

- Too few: an OH or NH is missing (`--hetero-h ID=1` on an O or N), or a carbon has too few
  hydrogens. Look at TO VERIFY first: a line marked "chosen by shifts" may be CH3 instead of CH
  (`--mult ID=CH3`).
- Too many: an OH/NH too many (`--hetero-h ID=0`), or a carbon has too many hydrogens.
- A difference of two often means one carbon is CH3 instead of CH, or the reverse.

## Even number of sp2 atoms

`N sp2 atoms: the number must be even`

Every double bond joins two sp2 atoms. Usually a carbonyl oxygen is missing: an unprotonated
carbon at 150-168 ppm next to oxygen (ester, lactone, amide, urea) is a C=O. Make one oxygen
without hydrogen sp2: `--hyb ID=sp2` on that O. In a compound with nitrogen it can also be a
C=N: make an N sp2. If no heteroatom fits, one carbon at 90-110 ppm may be sp3 (an acetal):
`--hyb ID=sp3`.

## Too many sp2 atoms

`too many sp2/sp atoms`

There are more double bonds than the formula allows. Make an sp2 oxygen or nitrogen sp3, or a
carbon at 90-110 ppm sp3.

## A correlation whose proton is gone

`Bxx: its proton sits on ..., which has no hydrogen now`

You changed a carbon to C (no hydrogen) while a correlation still uses its proton. Either the
change was wrong, or drop the correlation: `--drop Bxx`.

## No structure

The solver found no structure even when it was allowed to ignore three correlations. Something
in the atom table is wrong, or several correlations are. Check in this order and change one
thing per round:

1. **Hydrogens on heteroatoms.** With both O and N in the formula, the H may sit on N instead of
   O (`--hetero-h`).
2. **sp2 heteroatoms.** A carbon at 150-168 ppm without hydrogen: C=O (then an O is sp2) or
   C=C/C=N (then not). Try the other choice.
3. **Atom types marked "chosen by shifts"** in TO VERIFY. Try the second most likely type.
4. **Symmetry.** A line marked `x2` may be one carbon, and another line two.
5. **Correlations.** In `ailsa case show DATASET --correlations`, the weakest correlations
   (lowest SNR), especially to carbons with another carbon line within 1 ppm, are the least
   reliable. Drop at most three: `--drop B17,B19`.

Then run `ailsa case solve DATASET` again.

## Shift ranges

| 13C (ppm) | Typical carbon |
|---|---|
| 190-220 | ketone or aldehyde C=O |
| 160-185 | acid, ester, lactone or amide C=O |
| 100-160 | aromatic or alkene carbon; 140-165 can be C-O or C-N on a ring |
| 90-110 | acetal or ketal carbon (sp3), or an electron-rich alkene carbon |
| 50-90 | carbon bonded to O (or N at 40-65) |
| 0-50 | carbon bonded only to C and H |

| 1H (ppm) | Typical proton |
|---|---|
| 9-10 | aldehyde |
| 6-8.5 | aromatic |
| 4.5-6.5 | alkene, or CH bonded to two O |
| 3-4.5 | CH bonded to O or N; methoxy about 3.3-3.9 |
| 0.8-2.5 | CH, CH2, CH3 bonded only to carbon |
