# Ranking, judging and reporting

**When to read this.** Read this once LSD has produced structures (a `solutions.smi` file
exists). It covers ranking the candidates by 13C prediction, judging them, deriving the
identity with the tool, and declaring the result. Follow the sections in order.

## 1. Rank

**Atom by atom (decides the ranking).** LSD numbers the atoms of every solution as in your file,
so each carbon's predicted shift is compared with the measured shift of that same atom. The tool
reads the measured shifts from your MULT comments and the solutions from `compound.sol`:

```
ailsa lsd rank --assigned iteration_NN/compound.lsd -n 100 --format json > ranking_results.json
ailsa lsd rank --assigned iteration_NN/compound.lsd
```

The first saves the top 100 as the record, the second prints the top 10 to read. If it warns
that `DUPL 1` is missing, add it, run LSD again and rank again. For alternative multiplicity
models, pass every run at once (`--assigned` once per `compound.lsd`) and rank them together;
never rank each run alone and pick the run you like.

**Nearest line (cross-check).** The older mode matches every predicted shift to the nearest
experimental line, whatever atom it belongs to:

```
ailsa lsd rank iteration_NN/solutions.smi --shifts "S1,S2,S3"
```

It cannot tell regioisomers apart well: a wrong structure borrows lines that belong to other
atoms. Use it only as a second opinion and report where the two disagree.

## 2. Read the numbers

- **Order.** The atom-by-atom ranking sorts by MAE (lower is better), then by the number of
  carbons within 3 ppm. Each distinct structure appears once, with its best atom assignment.
- **`mae`**: mean of |predicted - measured| over the carbons compared, each carbon against its
  own measured shift. **`within_tolerance` / `compared`**: carbons within 3 ppm.
- **`max_error`** and **`worst_atom`**: the largest deviation and its LSD atom number.
- **`atoms`**: per carbon the LSD atom, measured and predicted shift, and the signed error
  (predicted minus measured). Use it for section 3.
- **What the numbers mean.** In tests, right structures had an atom-by-atom MAE of about 0.3 to
  2.5 ppm; the 13C prediction is weak for rare skeletons, so a right structure can show single
  errors of 5 to 8 ppm. The margin to rank 2 says more than the absolute value. Above 4 ppm
  for every candidate, suspect the atom table (SKILL.md, step 3).
- **Cross-check numbers** (nearest-line mode): `matched` out of all carbons and an MAE against the
  nearest lines. They are always lower than the atom-by-atom ones and can rank a wrong
  regioisomer first. With 4 or more lines at 110-160 ppm that mode also flags candidates without
  an aromatic ring.

## 3. Check atom by atom

For the top 3 to 5 candidates, read their `atoms` lists in `ranking_results.json`
(measured and predicted shift per LSD atom). For the prediction's confidence and radius of a
single structure (6 = most specific match), run `ailsa predict c13 "SMILES"`.

- A carbon off by more than 3.5 ppm marks the part of the structure most likely wrong.
- An experimental line that is no carbon's nearest match is unexplained. MAE does not see it;
  note it.
- Errors with the same sign across one region point to wrong regiochemistry or
  stereochemistry rather than a wrong skeleton.
- Low confidence or low radius means the prediction itself is uncertain (unusual environment).
  Do not reject a structure on that carbon alone.
- Two candidates with similar MAE: compare the carbons where they differ. If nothing decides between them, record an ambiguity and name both.
- LSD writes aromatic rings with alternating single and double bonds. The tools handle that;
  do not judge aromaticity from the SMILES by eye.

## 4. Chemical plausibility

Check each top candidate:

1. **Functional groups match the shifts.** Acid or ester C=O at 160-185 ppm, ketone or
   aldehyde at 190-220, aromatic CH at 110-160. A group with no matching line is a failure.
2. **DBE.** Rings plus double bonds must equal (2C + 2 + N - H) / 2 from the formula.
3. **Strain.** 3- or 4-membered rings are very rare in natural products.
4. **Systematic deviations** (section 3).
5. **Natural-product likelihood.** A known scaffold class (terpenoid, alkaloid, polyketide,
   phenylpropanoid), sensible heteroatom placement, no exotic groups (azide, perchlorate).
6. **Aromatic evidence.** If the experiment has 4 or more lines at 110-160 ppm: a candidate
   with no aromatic ring is QUESTIONABLE; a candidate with no predicted shift at all in
   110-160 ppm is IMPLAUSIBLE. Predicted aromatic carbons matching the experimental count raise
   confidence.

Verdict: **PLAUSIBLE** (all pass), **QUESTIONABLE** (one fails), **IMPLAUSIBLE** (two or more
fail, or check 6 says IMPLAUSIBLE).

Long-range correlations, for the caveats:

```
ailsa lsd analyze iteration_NN/compound.sol iteration_NN/compound.lsd --solution N --format json
```

N is the candidate's `solution_index`. An HMBC with `j_coupling` 4 or more is a long-range
correlation the solver was allowed to drop (ELIM): list it as a caveat, never remove it.

## 5. Decide

- **The answer is rank 1.** If rank 1 is IMPLAUSIBLE and a lower candidate is PLAUSIBLE, take
  the best-ranked PLAUSIBLE one and say why. Never promote a candidate because it looks
  familiar.
- **Re-examine once** if all top 3 are QUESTIONABLE or IMPLAUSIBLE, or the best MAE is above
  4.0 ppm with 20 or fewer solutions. The 13C interpretation is probably wrong: look for a
  missed carbonyl (DBE short, weak peak at 160-220 ppm), a line holding two equivalent
  carbons, a DEPT sign contradicting a multiplicity. Fix a concrete defect and solve again.
  One round only; if you find no defect, report at Low confidence and suggest more data.
- **No aromatic candidate despite aromatic evidence:** go back to the solver and raise ELIM by
  one, if all HMBC correlations are already in.
- **Ambiguous multiplicity:** if setup left several multiplicity models possible, every one
  must have its own LSD run before you accept. A low MAE does not replace a missing run.
- **More than 10 solutions at the iteration limit:** rank anyway. The result is
  under-determined; confidence is at most Medium.

## 6. Confidence

Per carbon, rate three factors High / Medium / Low:

1. **Resolution:** isolated line / close but resolved / overlapping.
2. **Prediction error:** below 2.0 / 2.0-3.5 / above 3.5 ppm.
3. **Correlations:** HSQC plus 3 or more HMBC / 1-2 HMBC / no HMBC or unclear HSQC.

Downgrades: any ambiguity caps all ratings at Medium. A carbon with error above 3.5 ppm, a
quaternary carbon without HMBC, or a carbon with no clear 13C peak is Low. An unresolved
DEPT/HSQC conflict caps that carbon at Medium.

Per structure (critical = a carbon whose position decides between candidates):

- **High:** at least 80 % of carbons High or Medium, at most one Low, not critical.
- **Medium:** at least 50 % High or Medium, two Low, or one critical Low.
- **Low:** below 50 %, three or more Low, or two or more critical Low.

When unsure, choose the lower level.

## 7. Identity

Never name a compound from memory. Before you write any name, derive the identity of the
chosen SMILES:

```
ailsa identify --smiles 'SMILES' --format json
```

If you have a name in mind, add `--reported-name 'NAME'` so the tool checks it. Read `verdict`,
`derived` and `warning`; they alone decide what you write:

| verdict | Primary identity | Name | Identity confidence |
|---|---|---|---|
| `confirmed` | `derived.name` | plain | tool-confirmed |
| `confirmed-structure` | InChIKey + canonical SMILES; state "structure in reference DB, trivial name not confirmed" | any name `(tentative, unverified)` | structure-only |
| `novel` | InChIKey + canonical SMILES; report as a novel structure | any name `(tentative, unverified)` | unverified/novel |
| `tentative` | as the row matching `derived.confidence`; put `warning` first in the Identity block | `(tentative, unverified)` | as the row matching `derived.confidence` |

Write the literal `(tentative, unverified)` after every name that is not `confirmed`. A name
claims an exact isomer (substituent positions, linkage, symmetry); if the data do not fix
those, the name is tentative. A downgraded name never blocks the structural result.

## 8. Declare the result

You do not write the report. You declare the result once with `ailsa run finalize`; the report
(`final_results.md`) is generated from the declaration and the record.

```
ailsa run finalize --outcome proposal --ranking latest --candidate 1 --confidence medium \
  --caveat "unexplained line at 128 ppm" --open-question "regiochemistry of the methyl" \
  --next-step "acquire NOESY" --alternative 2:less_likely
```

- `--outcome`: `proposal` (one structure you stand behind), `proposal_under_determined` (the data
  leave several), `inconclusive` (a ranking exists but you do not trust it), `no_structure_fits`,
  `insufficient_data` (no candidate needed for these two), `handed_to_human`.
- `--ranking latest` names the ranking `ailsa lsd rank --assigned` wrote last; `--candidate N` is
  the rank you chose (section 5, not always 1).
- `--confidence high|medium|low` follows section 6.
- `--caveat`, `--open-question`, `--next-step`: one text each, repeat the option for more
  (ambiguities, unexplained lines, long-range correlations, Low carbons, data that would decide).
- `--alternative RANK:STATUS`: every other candidate worth naming, with `not_excluded`,
  `less_likely` or `excluded`.
- `--termination-reason`: why you stopped (iteration limit, converged, no data left).

An identity block comes from section 7: run `ailsa identify` and let `verdict` decide the name.
Finalize refuses a ranking you wrote yourself and one older than your last solver run; run
`ailsa lsd run` and `ailsa lsd rank --assigned` again, then finalize. Iteration limit with more
than 10 solutions: use `proposal_under_determined` and name more 2D spectra, an HRMS formula
check and a manual peak review as next steps.

Then answer the user with the chosen SMILES, its identity as section 7 gives it, the confidence,
and the run folder.
