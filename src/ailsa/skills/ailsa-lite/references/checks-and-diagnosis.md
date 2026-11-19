# Checks and diagnosis

**When to read this.** You write every LSD file yourself, so you must check it yourself. Apply
part 1 to every LSD file before every solver run, also after a one-line change. Read part 2 when
LSD returns no structure, or far too many (thousands, a time-out, or more than 100 that barely
shrink from run to run). Run all commands from the iteration folder, `analysis/iteration_NN/`.

Two grades are used below:

- **FIX**: the solver aborts, or the true structure is excluded. Never run with one open.
- **JUSTIFY**: allowed only with a one-line reason in `analysis/iterations.md`.

## Part 1: before every run

### 1.1 Three commands

```bash
# atoms: element counts, hydrogen total, sp2 count
sed 's/;.*//' compound.lsd | awk '$1=="MULT"{n[$3]++; h+=$5; if($4==2) s++} END{for(e in n) printf "%s=%d ", e, n[e]; print "H=" h, "sp2=" s+0}'
# correlations: prints each problem it finds; no output means none
sed 's/;.*//' compound.lsd | awk '$1=="HSQC"{d[$3]++} $1=="HMBC"{h=($2~/^\(/)?$NF:$3; u[h]=1; if($2==h) print "HMBC to its own proton:", $0; if($2!~/^\(/ && NF>3) print "HMBC with bond range:", $0} END{for(x in u) if(!(x in d)) print "no HSQC for HMBC proton", x; for(x in d) if(d[x]>1) print "HSQC repeated for", x}'
# all other constraints, to read line by line
grep -nE '^(BOND|LIST|ELEM|PROP|COSY|DEFF|FEXP|ELIM)' compound.lsd
```

### 1.2 Atoms (all FIX)

- [ ] Every element count equals the formula. Equivalent carbons need one MULT line each.
- [ ] `H=` equals the H of the formula. OH and NH hydrogens count on their O or N line
  (`MULT 6 O 3 1`). Too few: an OH/NH is missing, or a CH is written as C. A difference of 2:
  a CH3 written as CH, or the reverse.
- [ ] `sp2=` is even, because every double bond joins two sp2 atoms. If odd, look for a carbonyl
  O left at 3, an ether or hydroxyl O or an amine N set to 2, or an sp3 carbon set to 2.
- [ ] Double bonds (sp2 count / 2) do not exceed the DBE; rings = DBE minus double bonds.
- [ ] In LSD, hybridisation 2 means the atom carries exactly one double bond. Carbonyl O: 2.
  Ether and hydroxyl O: 3. Amine and amide N: 3. Imine and pyridine-type N: 2. Quaternary and
  bridgehead sp3 carbons: `C 3 0`. Acetal carbons (90-110 ppm, two O neighbours): 3.

### 1.3 Correlations (all FIX)

- [ ] Every number in HSQC, HMBC, COSY, BOND and LIST lines is an atom defined by MULT.
- [ ] One HSQC line per protonated atom, also for CH2 and CH3 (a second line for the same atom
  is LSD error 234). No HSQC on an atom without H.
- [ ] Every HMBC proton has its own HSQC line, also an OH or NH proton: `HSQC 17 17` on the
  oxygen, then `HMBC 5 17`. Without it LSD aborts with error 250.
- [ ] No one-bond leak-through: no `HMBC 5 5` (error 252), and no HMBC peak within 1.5 ppm
  (13C) and 0.3 ppm (1H) of an HSQC peak. Delete such lines.
- [ ] All HSQC lines come before the first HMBC line.
- [ ] Two carbons the HMBC cannot tell apart get grouped notation, `HMBC (5 6) 10`, never a
  guess. The HMBC's carbon resolution is the smallest step between distinct F1 positions in the
  `ailsa pick hmbc` output; carbons closer than 1.5 times that step are unresolved. Treat any
  pair within 3 ppm with suspicion.
- [ ] No HMBC with a bond range (`HMBC 1 3 2 4`, flagged by the second command). Write
  `HMBC 1 3`: ELIM can never drop a correlation that has a range.

### 1.4 Constraints

- [ ] FIX: the ring filter block, in every iteration. `ailsa lsd run` copies the `ring3` and
  `ring4` files into the folder.
  ```
  DEFF F1 "ring3"
  DEFF F2 "ring4"
  FEXP "NOT F1 AND NOT F2"
  ```
  Only one FEXP line per file: a second one aborts LSD (error 402). With a fragment from
  `ailsa fragment to-lsd`, keep F1 and F2, add its `DEFF F3 "fragment_....lsd"` line (that file
  must sit in the same folder) and combine everything in one line:
  `FEXP "F3 AND NOT F1 AND NOT F2"`. JUSTIFY: if an epoxide is possible (O in the formula,
  carbons at 45-55 ppm), drop only ring3: `FEXP "NOT F2"`. Never write `DEFF NOT ...`
  (error 150) or `SYME` (error 102).
- [ ] FIX: equivalent carbons, written with native commands:
  - Aromatic CH pairs: run `ailsa detect aromatic-cosy "SHIFTS" --multiplicities "MULTS"` with
    all carbon shifts and multiplicities in MULT order (it prints positions in that list, 1 =
    first) and copy each pair as `COSY a b 3 3 ; equiv-pair`. Never pair atoms by hand. A
    correct pair joins two different shifts; a pair of two atoms with the same shift is wrong
    (the ring never forms; with ring BONDs it is error 283). The `3 3` keeps ELIM from dropping
    the pair.
  - Gem-dimethyl or isopropyl: `BOND p m1` and `BOND p m2` (both CH3 on parent carbon p).
- [ ] FIX: the heteroatom evidence rule. A BOND or PROP to O or N needs direct evidence: an HMBC
  that places it, an OH or NH proton, or the carbonyl case (unprotonated carbon at 160-220 ppm,
  O in the formula, C=O context; then write `BOND c o` with an sp2 O). Output of
  `ailsa detect neighbours SHIFT --format json` is a hint only. It is never enough on its own;
  never use it when `constraint_type` is `typical`, when `dominant_element` is carbon and nothing
  else supports the heteroatom, or for aromatic carbons at 145-160 ppm; never recalculate its
  percentages. When in doubt, leave the position open: ranking can choose among open
  alternatives, but it can never bring back a structure that a wrong hard constraint excluded.
- [ ] FIX: BOND only between two atoms that can bond, never to a hydrogen (HSQC does that),
  never against an HMBC. `PROP L1 n L2` means every atom of L1 has exactly n neighbours in L2.
  Define LIST and ELEM lines before the PROP that uses them.
- [ ] JUSTIFY: ELIM. None in the first run and none before all reliable HMBC are in. Only the form
  `ELIM N 0`, N raised one step at a time (1, 2, 3), never above 3.

### 1.5 Since the previous iteration (from iteration 2 on)

```bash
diff ../iteration_PP/compound.lsd compound.lsd      # PP = the previous iteration number
```

Lines starting with `<` were removed. Losing a line by accident is the most common failure in
this work.

- [ ] FIX: MULT and HSQC lines unchanged, unless `iterations.md` records a deliberate
  correction from part 2. Alternative multiplicity models live in their own folders.
- [ ] FIX: no ring filter line, BOND, `; equiv-pair` COSY, grouped `HMBC (a b) h`, LIST, ELEM
  or PROP lost or rewritten in a simpler form without a recorded reason.
- [ ] JUSTIFY: the number of HMBC lines only grows. Removing a batch needs its reason.
- [ ] JUSTIFY: everything `setup.md` promises (symmetry, signal groups, carbonyl BOND, OH/NH) is
  in the file. A detection result left unused for three iterations: apply it or write why not.
- [ ] The constraint inventory block (see `lsd-input.md`) is present and
  `ailsa lsd validate-inventory --format json compound.lsd` reports `"valid": true`. Correct the
  counts it lists.
- [ ] Once all checks pass, run the file unchanged. After any edit, check again.

### 1.6 Before you accept a result

- [ ] Four or more carbons at 110-160 ppm, but no candidate has an aromatic ring: a 4-bond HMBC
  probably forces a wrong skeleton. Go to part 2, section 2.2, step 7 (ELIM).
- [ ] A correlation that is a real 2- or 3-bond path only under a multiplicity model you have
  not run (for example, it joins a CH3 to a CH2 that only the other model has) is evidence for
  that model. Run that model in its own folder before you report. Only a run closes this point;
  never explain the correlation away to keep the leading model.

## Part 2: no structure, or far too many

### 2.1 Find out what LSD said

`ailsa lsd run` says which of these happened:

- `Solutions found: N` with N above zero: LSD produced structures.
- `no structure fits the constraints` (`Solutions found: 0`): go to 2.2.
- `LSD execution timed out`: go to 2.3. Raise the limit with `--timeout 600` only for a file
  you expect to be well constrained.
- `LSD error NNN: <reason>`: the input is invalid; the table below names the fix.

| Error | Cause | Fix |
|---|---|---|
| 102 | unknown command, e.g. SYME | native BOND or COSY (1.4) |
| 150 | `DEFF NOT ...` | the ring filter block |
| 234 | second HSQC for one atom | one HSQC per atom |
| 250 | HMBC proton without HSQC | add `HSQC x x`, also on O or N |
| 252 | HMBC to the carbon's own proton | delete the line |
| 283 | COSY pair inside one shift group, with ring BONDs | pairs from `ailsa detect aromatic-cosy` |
| 402 | second FEXP line | one combined FEXP |
| 420 | BONDs cut the molecule into pieces | remove the wrong BOND |

### 2.2 No structure

Change one thing per run and record each change and its result in `iterations.md`. Go in this
order and stop at the first step that brings structures back.

1. Apply all of part 1 again and fix every FIX item. Most empty results come from an odd sp2
   count, a wrong H total or a wrong element count.
2. If the last run added a batch of HMBC, remove the batch; structures must come back. Then add
   its correlations back one at a time. The one that empties the result is the conflict. Check
   it for leak-through, for a neighbouring carbon within resolution (use grouped notation), or
   for a weak peak (drop it).
3. If a fragment filter is in the file, remove its DEFF line and `F3` from the FEXP line. If
   structures come back, the fragment contradicts the data: leave it out and record why.
4. Remove every heteroatom BOND or PROP that lacks direct evidence (1.4).
5. Revisit one atom decision per run, keeping the counts of 1.2 right: carbonyl O (2) or ether
   O (3); amine or amide N (3) or imine N (2); H on N instead of O when the formula has both;
   multiplicities chosen from shifts alone rather than from DEPT or HSQC (run each alternative
   in its own folder); symmetry (a line counted twice may be one carbon, and another line two).
6. Rewrite correlations to carbons within resolution of each other in grouped notation. Then drop
   the weakest (lowest SNR) correlations to such carbons: at most three, each recorded.
7. Only when all reliable HMBC are in and every check passes: add `ELIM 1 0`. If still empty,
   replace it with `ELIM 2 0`, then `ELIM 3 0`. Stop at the smallest N that gives at least one
   plausible structure: an aromatic ring when four or more carbons lie at 110-160 ppm, and
   rings plus double bonds equal to the DBE. Then run

   ```bash
   ailsa lsd analyze compound.sol compound.lsd
   ```

   It lists, per structure, the path length of every HMBC. Correlations of 4J or longer
   (`j_coupling` 4 or more with `--format json`) are the ones ELIM dropped. Record them.
8. Still empty at `ELIM 3 0`: the conflict lies in the atoms or the correlations, not in a
   4-bond HMBC. Never go above 3, and never add and remove ELIM again and again: ELIM does not
   repair an odd sp2 count, a wrong H total, a leak-through or two mixed-up carbons. Return to
   the atom list (workflow step 1): a missed carbon (a weak carbonyl:
   `ailsa pick 1d C13_DIR --snr-floor 3 --format json`, look at 160-220 ppm), symmetry, the
   formula itself. If that fails too, report that the data gave no structure and list what you
   tried.

### 2.3 Far too many structures

Signs: thousands of structures, a time-out, or more than 100 that shrink by less than 10 % per
batch for three runs. If the count went up after you added constraints, a constraint was lost or
loosened: run the diff of 1.5 first.

Check all five points, then fix the largest gap.

1. **ELIM.** Reached through the steps of 2.2? Then a large set is expected: rank it
   (`ranking.md`), the ranking does the sorting. Check that N is 3 or less and that no HMBC has
   a bond range.
2. **Too few HMBC.** Ratio = number of HMBC lines / number of MULT lines. Below 0.3: expect
   thousands; 0.3-0.5: hundreds; 0.5-1.0: tens; above 1.0: a handful. Below 0.5, add reliable
   HMBC in batches of 3 to 5. Prefer correlations to unprotonated carbons, to carbons with no
   other carbon within 3 ppm, from protons with no other proton within 0.2 ppm, strong peaks,
   and correlations that join atoms not yet linked. A correlation inside an already linked
   fragment adds nothing.
3. **Floating unprotonated carbons.** A carbon without H and without HMBC can sit anywhere:

   ```bash
   sed 's/;.*//' compound.lsd | awk '$1=="MULT" && $3=="C" && $5==0 {q[$2]=1} $1=="HMBC"{gsub(/[()]/,""); for(i=2;i<NF;i++) delete q[$i]} END{for(x in q) print "C", x, "has no HMBC"}'
   ```

   For each one, pick again with `ailsa pick hmbc HMBC_DIR --snr-floor 3 --format json`. Keep
   only peaks within 2.5 ppm of that carbon's shift whose proton matches an HSQC proton, and add
   one or two. If there are none and the carbon lies at 160-220 ppm, apply the carbonyl case of
   1.4.
4. **Open heteroatoms.** Every O or N without BOND, PROP or HMBC evidence multiplies the
   structures. Constrain it only under the evidence rule of 1.4. With direct evidence that
   heteroatom X sits on one of a set of candidate carbons: `LIST L1 a b`, `PROP X 1 L1` (X has
   exactly one neighbour among them; `PROP X 0 L1` if all its neighbours are). `PROP L1 1 L2`
   with L2 = all oxygens would force an O onto every candidate. Without evidence, leave it open.
5. **Symmetry not written.** Fewer 13C lines than formula carbons
   (`ailsa analyze symmetry FORMULA C13_DIR`) but no `; equiv-pair` COSY or gem-dimethyl
   BONDs: LSD permutes the equivalent atoms (a para-disubstituted ring alone can multiply the
   count up to 24-fold). Write them as in 1.4.

If all reliable HMBC are in and the count stays high, stop adding. Rank what you have and state
in the report that the data do not determine the structure fully.

### 2.4 Few structures, all poor

The best MAE is above 4 ppm with 20 or fewer structures, or all top three candidates are
implausible: the atom list is wrong, not the solver. Re-examine once, in this order:

1. DBE: are rings plus double bonds right? A deficit often means a missed carbonyl:
   `ailsa pick 1d C13_DIR --snr-floor 3 --format json`, look for lines at 160-220 ppm with SNR
   3 to 20.
2. Aromatic CH lines at least 1.6 times as intense as the median of their kind are two
   equivalent carbons each: give them to `ailsa detect aromatic-cosy` and write the pairs.
3. For every doubtful line: does its DEPT sign agree with its multiplicity?

Rebuild once with what you found. If you find nothing, report honestly.

### 2.5 Going in circles

Constraints added and removed over five runs without progress: return to the last iteration
whose count made sense and add one batch per run, chosen by the criteria of 2.3, point 2. If
nothing converges, suspect the molecular formula.
