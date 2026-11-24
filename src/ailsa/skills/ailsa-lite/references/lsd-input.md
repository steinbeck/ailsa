# LSD input: write, run, iterate

**When to read this.** Before you write the first LSD file. It covers atom numbering, the exact
syntax of every LSD command you need, a complete small example, running `ailsa lsd run`,
reading its result, and building the next iteration without losing constraints. Before each
run, also apply part 1 of `checks-and-diagnosis.md`; when LSD finds no structure or far too
many, go to part 2 of that file.

## 1. Folders and files

- One folder per solver run: `iteration_01/compound.lsd`, then `iteration_02/`, and so
  on (two digits). An alternative multiplicity model gets its own folder,
  `iteration_NN_<model>/`.
- From iteration 2 on, copy the previous file and edit the copy:
  `cp iteration_01/compound.lsd iteration_02/`. Never retype a file from
  memory. Every constraint stays unless you record a reason for removing it.
- `ailsa lsd run` writes `compound.sol`, `solncounter` (solutions found) and `solutions.smi`
  (one SMILES per solution) into the same folder.

## 2. Numbering

- Carbons first, numbered from 1 in order of decreasing 13C shift. Then the heteroatoms: O, then
  N, then S.
- One atom per carbon. A 13C line that stands for two equivalent carbons gets two consecutive
  numbers with the same shift.
- A proton has the number of the atom it sits on: the protons of carbon 7 are H-7. The two
  protons of a CH2 share that number.
- Everything after `;` is a comment. Comment every line with shift, multiplicity and evidence.
  On a carbon's MULT line the comment starts with its measured 13C shift
  (`MULT 1 C 2 0 ; 208.1 ...`): the atom-by-atom ranking reads it there.
- LSD limits: atoms 1 to 60, at most 300 commands, at most 100 HMBC plus COSY lines, lists L1 to
  L20, at most 4 atoms inside parentheses.

## 3. Commands

Commands are upper case; parts are separated by spaces.

### MULT: one line per non-hydrogen atom

```
MULT index element hybridisation hydrogens
MULT 1 C 2 0    ; 208.1 C, ketone C=O
MULT 6 O 3 1    ; OH
```

Hybridisation is LSD's own definition, read from the Lewis structure: `2` = exactly one double
bond; `1` = one triple bond or two double bonds; `3` = single bonds only.

| Atom | MULT |
|---|---|
| carbonyl O (C=O) | `O 2 0` |
| ether O | `O 3 0` |
| hydroxyl O | `O 3 1` |
| amine or amide N | `N 3 h` (h = its hydrogens) |
| imine or pyridine-type N (C=N) | `N 2 h` |
| pyrrole- or indole-type N-H (no double bond to N) | `N 3 1` |
| thioether S | `S 3 0` |
| quaternary or bridgehead sp3 carbon | `C 3 0` |
| acetal carbon, 90-110 ppm, two O neighbours | `C 3 h` |

The MULT hydrogens must add up to the formula H. The number of atoms with hybridisation 2 must
be even: every double bond joins two (a C=O makes its O sp2 too).

### HSQC: which proton sits on which atom

```
HSQC 2 2      ; carbon 2 carries H-2
HSQC 6 6      ; OH proton on oxygen 6 (exchangeable, not seen in the HSQC)
```

- Exactly one HSQC line per protonated carbon, also for CH2 and CH3. A second line for the same
  atom aborts LSD (error 234). No HSQC on an atom without hydrogens.
- An OH or NH proton that shows any HMBC peak needs `HSQC o o` on its heteroatom, from
  iteration 1 on. Without it LSD aborts (error 250). This line only declares the proton; it
  adds no connectivity.
- Write all HSQC lines before the first HMBC line.

### HMBC: carbon first, then the proton

```
HMBC 1 3          ; C 208.1 sees H-3 (2.18): carbon 1 is 2 or 3 bonds from H-3
HMBC (4 5) 9      ; carbon 4 or carbon 5 sees H-9
```

- The first number is the carbon (or heteroatom), the second the atom that carries the proton.
  Do not swap them.
- Parentheses list the carbons a peak could belong to: carbons closer than the HMBC can resolve,
  or the copies of an equivalent pair. Only the carbon side can be grouped; a peak whose proton
  could belong to two different carbons is not used.
- A proton on an equivalent pair: use the first copy's number for all its peaks.
- Never `HMBC 5 5` (a carbon with its own proton: error 252). A peak at an HSQC position
  (13C within 1.5 ppm, 1H within 0.3 ppm) is one-bond leak-through: leave it out.
- Never give a bond range (`HMBC 1 3 2 4`): ELIM can never drop such a line.

### COSY: two protons three bonds apart

```
COSY 2 4             ; H-2 and H-4 couple: carbons 2 and 4 are bonded
COSY 4 7 3 3 ; equiv-pair
```

Both numbers are proton numbers. A COSY peak from the spectrum is written plainly, like the
first line. Equivalence pairs (section 4) carry the range `3 3` and the comment `; equiv-pair`;
the explicit range keeps ELIM from dropping them.

### BOND, LIST, ELEM, PROP

```
BOND 1 5        ; C 208.1 = O 5 (carbonyl case)
LIST L1 2 3     ; carbons 2 and 3
ELEM L2 O       ; all oxygens
PROP L1 1 L2    ; each atom of L1 has exactly 1 neighbour in L2
```

- `BOND a b` forces a bond between two atoms. Never to a hydrogen; HSQC does that.
- `PROP X n L` means exactly n neighbours in list L; `PROP X n L +` at least n; `PROP X n L -`
  at most n; `PROP X 0 L` all neighbours in L. X is one atom or a list.
- LSD reads LIST, ELEM and PROP lines in order: define a list before the PROP that uses it.
- Lists are numbered `L1` to `L20` and hold only non-hydrogen atoms; a name such as `L_O`
  aborts the run (error 114).

### ELIM: let LSD ignore a few correlations

```
ELIM 1 0        ; LSD may drop up to 1 HMBC or COSY correlation
```

Only the form `ELIM N 0`, never in the first run, N at most 3. Section 10 says when.

### Ring filters: every file, every iteration

```
DEFF F1 "ring3"
DEFF F2 "ring4"
FEXP "NOT F1 AND NOT F2"
```

They exclude three- and four-membered rings; `ailsa lsd run` supplies the filter files. F1 and
F2 are reserved for them. Only one FEXP line per file; a second one aborts LSD (error 402).
Exception: with O in the formula and carbons at 45-55 ppm (a possible epoxide), drop
`DEFF F1`, write `FEXP "NOT F2"`, and record why in `iterations.md`.

### MAXS: limit the number of solutions

```
MAXS 20000      ; stop after 20000 solutions
```

Optional guard against runaway runs. If the count equals the limit, the list is cut short:
add constraints before you rank, or rank and state that the set is incomplete.

### DUPL 1: keep every atom assignment

```
DUPL 1          ; keep every atom assignment
```

Write it in every file. Without it LSD keeps only one, arbitrary, atom assignment per
structure, and the atom-by-atom ranking (`ranking.md`) may judge a right structure by a wrong
assignment. It can multiply the solution count; keep `MAXS 20000`.

### Never write

- `SYME` (error 102) or `DEFF NOT ...` (error 150). LSD does not know them, and
  `ailsa lsd run` passes your file to LSD unchanged. Use section 4 and the ring filters.
- `EXIT`. LSD silently ignores everything after it, so a line appended later would be lost.
- `SKEL`, or a second `FEXP` line.

## 4. Equivalent carbons

Without these lines LSD treats equivalent atoms as independent and the number of solutions
explodes.

- **Aromatic CH pairs.** Run the tool with all carbon shifts and multiplicities in MULT order,
  each copy written once:

  ```bash
  ailsa detect aromatic-cosy "197.8,143.8,134.8,129.2,129.2,128.4,128.4,26.5,21.6" \
      --multiplicities "C,C,C,CH,CH,CH,CH,CH3,CH3"
  ```

  Given the full list in MULT order, the numbers it prints are your atom numbers (here
  `COSY 6 5` and `COSY 7 4`). Write each as `COSY 6 5 3 3 ; equiv-pair`. Never pair atoms by
  hand: a correct pair joins two different shifts; a pair of two atoms with the same shift is
  wrong and, with ring BONDs present, aborts LSD (error 283).
- **Gem-dimethyl or isopropyl** (two equivalent CH3 on one parent carbon p, placed there by
  HMBC): `BOND p m1` and `BOND p m2`.
- **CH2 protons:** nothing to do; both share the carbon's number.

## 5. Heteroatoms and hard constraints

- Hydrogens on O and N are formula H minus the H on carbons; the HSQC cannot see them. Put
  them on the O or N line (`MULT 6 O 3 1`). With both O and N in the formula, either may carry
  the H; test the other choice in a separate run.
- O atoms are interchangeable labels: LSD decides where each one goes. Pair each carbonyl carbon
  with its own sp2 O.
- A BOND or PROP to O or N needs direct evidence: an HMBC that places it, an OH or NH proton
  peak, or the carbonyl case (carbon without H at 160-220 ppm, O in the formula, C=O context:
  `BOND c o`). Output of `ailsa detect neighbours` is a hint, never enough on its own (details
  in `checks-and-diagnosis.md`, 1.4). When in doubt, leave the position open. Ranking can choose
  among open alternatives; it can never bring back a structure that a wrong constraint
  excluded.
- **Aromatic rings emerge; do not force them.** Write no ring BONDs for an aromatic ring and
  never `SKEL`; the equivalence COSY pairs, the HMBC and the ring filters are enough. Only after
  three consecutive iterations without an aromatic candidate (with four or more carbons at
  110-160 ppm) may you add BONDs that define the ring, recording reason and iteration number
  in `iterations.md`.

## 6. Constraint inventory

Every file starts with a short inventory block in comment lines (example in section 7). It
records what the file must contain, so the next iteration can check that nothing was lost.

- Every line between the two markers starts with `; `. Copy the markers exactly.
- In the next iteration, change only: `iteration` (+1), `timestamp`, a new entry in
  `hmbc_batches`, `hmbc_total`, `elim_budget` when ELIM changes, and the list of any constraint
  you added or removed with a recorded reason.
- The counts must match the commands in the same file. Check it with
  `ailsa lsd validate-inventory compound.lsd`; it must print `Valid constraint inventory v2`.

## 7. Example: iteration 1

A small generic problem, formula C4H8O2: a ketone carbon, a CH bearing O, two CH3, one carbonyl
O and one OH. Hydrogens 1 + 3 + 3 + 1 = 8; sp2 atoms 1 and 5 (even).

```
; === CONSTRAINT INVENTORY v2 ===
; {"version": 2, "iteration": 1, "formula": "C4H8O2", "timestamp": "2026-11-18T12:00:00Z",
;  "mult_count": 6, "hsqc_count": 4, "hmbc_total": 4,
;  "hmbc_batches": [{"batch": 1, "count": 4, "correlations": ["1 3", "1 2", "2 4", "4 2"]}],
;  "grouped_hmbc": [], "bond_constraints": ["1 5"], "cosy_equiv_pairs": [],
;  "list_prop_constraints": [], "elim_budget": 0, "ring_exclusion_enabled": true}
; === END CONSTRAINT INVENTORY ===
MULT 1 C 2 0    ; 208.1 C (no HSQC), ketone C=O
MULT 2 C 3 1    ; 73.2 CH (DEPT-135 +), bears O
MULT 3 C 3 3    ; 25.0 CH3, H 2.18
MULT 4 C 3 3    ; 19.3 CH3, H 1.35
MULT 5 O 2 0    ; carbonyl O
MULT 6 O 3 1    ; OH, from the hydrogen budget
HSQC 2 2        ; 73.2 / 4.25
HSQC 3 3        ; 25.0 / 2.18
HSQC 4 4        ; 19.3 / 1.35
HSQC 6 6        ; OH proton 3.60, used by a pending HMBC
HMBC 1 3        ; 208.1 / 2.18
HMBC 1 2        ; 208.1 / 4.25
HMBC 2 4        ; 73.2 / 1.35
HMBC 4 2        ; 19.3 / 4.25
BOND 1 5        ; carbonyl case: C without H at 208.1, O in formula
DEFF F1 "ring3"
DEFF F2 "ring4"
FEXP "NOT F1 AND NOT F2"
DUPL 1
MAXS 20000
; --- pending HMBC, most reliable first ---
; HMBC 4 6      ; 19.3 / 3.60 (OH)
; HMBC 1 4      ; 208.1 / 1.35
```

This file gives 3 solutions: 2 different structures, one of them in two atom assignments
(`DUPL 1`). Iteration 2 activates the first pending line by deleting its `;` and gives 1. Keep the unused HMBC as comments at the end like this: each copy then carries the
full list forward, and the next batch is taken from the top.

## 8. Run and read the result

```bash
cd iteration_NN && ailsa lsd run compound.lsd
```

The default time limit is 60 seconds; `--timeout 600` raises it. Read the text output:

| Output | Meaning |
|---|---|
| `LSD completed successfully`, `Solutions found: N` | N structures; `solutions.smi` is written |
| `LSD completed: no structure fits the constraints` | 0 solutions: the file is valid but over-constrained or wrong; `checks-and-diagnosis.md` 2.2 |
| `LSD failed ...` with `LSD error NNN: <reason>` | invalid input; the reason names the line; table in `checks-and-diagnosis.md` 2.1 |
| `LSD execution timed out after N seconds` | not zero: `cat solncounter` shows how many structures LSD had found when it was stopped; usually far too many (`checks-and-diagnosis.md` 2.3) |

With `--format json`, `success` is false for 0 solutions as well as for errors: read
`solution_count` and `stderr`, ignore `return_code`.

| Count | Meaning | Action |
|---|---|---|
| 0 | over-constrained, or a wrong atom | `checks-and-diagnosis.md` 2.2 |
| 1 | ideal | check that it makes chemical sense; rank |
| 2-10 | good | rank (`ranking.md`) |
| 11-100 | under-constrained | next HMBC batch |
| above 100 | severely under-constrained | next batch; check symmetry and unprotonated carbons without HMBC (`checks-and-diagnosis.md` 2.3) |

## 9. Iterating

**Never add all HMBC at once.** Add 3 to 5 per iteration and watch the count.

Choose each batch from the pending list, best first:

1. the carbon has no other carbon within 3 ppm;
2. the proton has no other proton within 0.2 ppm;
3. the peak is strong (top quarter of the validated peaks);
4. it involves an unprotonated carbon, or links atoms not yet linked. A correlation inside an
   already linked fragment adds nothing.

Write one line of reason per chosen correlation in `iterations.md`.

After each run, compare with the previous count:

- More than 30 % fewer: continue with the next batch.
- Count went up: a constraint was lost or loosened. Diff against the previous file
  (`checks-and-diagnosis.md` 1.5) before anything else.
- 0: remove the last batch, confirm the structures come back, then add its correlations back one
  at a time (`checks-and-diagnosis.md` 2.2).
- Less than 10 % fewer in two runs: the batches add no new connections; choose correlations
  that link new atoms or unprotonated carbons.
- Less than 10 % fewer in three consecutive runs with more than 50 solutions: stop adding. Run
  the checks of `checks-and-diagnosis.md` 2.3, then rank and state that the data leave the
  structure underdetermined.

Stop iterating when 10 or fewer solutions remain, when no reliable HMBC is left, or after 10
iterations.

## 10. ELIM: the last step for 0 solutions

LSD treats every HMBC as 2 or 3 bonds, so one real 4-bond peak can leave no structure. ELIM
lets it drop a few correlations. Use it only when all three hold: every reliable HMBC is in the
file, every check of part 1 of `checks-and-diagnosis.md` passes, and there is still no
plausible structure.

1. Add `ELIM 1 0` and run.
2. Still none: replace it with `ELIM 2 0`, then `ELIM 3 0`.
3. Stop at the smallest N that gives at least one plausible structure: an aromatic ring when
   four or more carbons lie at 110-160 ppm, and rings plus double bonds equal to the DBE. Rank
   all of them; ELIM makes larger sets on purpose and the ranking sorts them.
4. See which correlations were dropped:
   `ailsa lsd analyze compound.sol compound.lsd`. Correlations listed as 4J or longer
   (`j_coupling` 4 or more with `--format json`) are the ones ELIM dropped. Record them.
5. Still nothing at `ELIM 3 0`: the conflict is in the atoms or the correlations, not a 4-bond
   peak. Never go above 3, and never add and remove ELIM repeatedly. Go to
   `checks-and-diagnosis.md` 2.2, step 8.

Record `elim_budget` in the inventory.

## 11. Alternative multiplicity models

When `setup.md` lists more than one multiplicity model, run every model in its own folder
`iteration_NN_<model>/`. The files carry all the same constraints and differ only in
the MULT lines of the atoms in question (`C 3 3` for CH3, `C 3 2` for CH2, `C 3 1` for CH).
Never run only the best-looking model and fall back to another when it disappoints. A model
counts as searched once its run has finished, even if it gave too many structures to rank.
Rank all models together (`ranking.md`).

## 12. Optional: a fragment filter

`ailsa fragment search --shifts "..." --top 1 --format json` proposes one known substructure.
Use it only if every element of the fragment is in the formula and its `atom_count` is smaller
than the molecule's heavy atom count. Never copy the `DEFF` line the search prints (it uses F1,
the ring filter's number). Run
`ailsa fragment to-lsd "SMILES" --output-dir iteration_NN/ --format json`, add its
`deff_command` (`DEFF F3 "fragment_....lsd"`), and merge into the one FEXP line:
`FEXP "F3 AND NOT F1 AND NOT F2"`. If that run gives 0 solutions, remove the F3 line and `F3`
from FEXP; if structures return, discard the fragment and record why.
