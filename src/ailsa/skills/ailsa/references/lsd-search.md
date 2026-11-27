# LSD search strategy

How the CASE team steers what LSD searches: keeping every atom assignment, injecting a fragment
goodlist, and searching every viable multiplicity family. The LSD engineer reads it before writing
the first LSD file, together with the command reference; the devil's advocate (DA) and the
diagnostic specialist check runs against it.

## Contents

- DUPL and MAXS: keep every atom assignment
- Fragment goodlist
- Per-family multiplicity search

## DUPL and MAXS: keep every atom assignment

```
DUPL 1          ; keep every atom assignment
MAXS 20000      ; stop after 20000 solutions
```

Write both lines in every LSD file. Without `DUPL 1`, LSD keeps only one, arbitrary atom
assignment per structure, and the atom-by-atom ranking may judge a right structure by a wrong
assignment. `DUPL 1` can multiply the solution count; `MAXS` caps it. A count equal to the cap
means the list is incomplete: add constraints or report it.

## Fragment goodlist

Fragment search finds known substructural fragments that match the experimental 13C shifts. If a
high-confidence fragment exists, inject it as a goodlist constraint so LSD only generates
structures containing that fragment.

```bash
# Search for matching fragments (always --top 1, never several)
ailsa fragment search --shifts "<comma_separated_shifts>" --format json --top 1

# Generate the fragment .lsd file for DEFF/FEXP injection
ailsa fragment to-lsd "<smiles>" --output-dir {work_dir}/iteration_NN/ --filter-index 3 --format json
```

JSON fields of `fragment search`: `result_count` (number of matching fragments),
`fragments[0].smiles` (SMILES of the best match), `fragments[0].atom_count` (heavy atoms in the
fragment), `fragments[0].avg_deviation` (average shift deviation in ppm).

JSON fields of `fragment to-lsd`:
- `filename`: name of the generated .lsd file (for example `fragment_abc123def456.lsd`).
- `deff_command`: the DEFF F3 command string for compound.lsd (F3 because F1 and F2 are reserved
  for ring exclusion).
- `fexp_command`: the fragment's own filter expression (`FEXP "F3"`). Do not add it as a second
  FEXP line: merge it into the single FEXP line of the filter block,
  `FEXP "F3 AND NOT F1 AND NOT F2"`.

- Placement: `DEFF F3 "filename.lsd"` joins the filter block after the correlations, next to
  DEFF F1 and F2, and F3 enters the one FEXP line.
- Persistence: carry the fragment DEFF F3 line and the merged FEXP line forward across iterations
  (read them from the previous LSD file, do not reconstruct them), like the ring exclusion lines.
- Do not inject more than one fragment (`--top 1` only; support for several fragments is
  deferred).
- The fragment .lsd file sits in the same `iteration_NN/` directory as compound.lsd (pass
  `--output-dir` explicitly), so that its relative DEFF path resolves like the ring filters.

Zero-solution fallback, when LSD returns 0 solutions and a fragment was injected:
1. Remove the fragment DEFF Fn line and take `Fn AND ` out of the FEXP line, which goes back to
   `FEXP "NOT F1 AND NOT F2"` (Fn is the fragment goodlist filter, F3 by default; the
   `deff_command` field in the inventory gives the actual index). Do not delete the FEXP line
   itself or the ring exclusion lines DEFF F1 and F2: without FEXP the ring filters are silently
   off.
2. Re-run LSD without the fragment.
3. If solutions return, the fragment conflicts with the data: discard it.
4. Set the inventory's `deff_fexp.status` to `"discarded"`, with `conflict_reason` saying why.
5. Log the discard in the `[ITERATION-COMPLETE]` message.

## Per-family multiplicity search

When aliphatic CH/CH₂/CH₃ multiplicity cannot be determined from the spectra, the NMR chemist
sends `[MULTIPLICITY-AMBIGUOUS]` with a numbered `viable_families:` list. Do not hard-code a
single leading multiplicity model: with one hard-coded model, a correct structure from another
family is never handed to LSD and cannot be found.

Run each viable family as a separate LSD run, each in its own iteration directory named
`iteration_NN_<family>` (for example `{work_dir}/iteration_03_A/` and `{work_dir}/iteration_03_B/`).
In each directory run `ailsa lsd run compound.lsd --purpose family`, so that the run record tells
the family searches apart from the main iterations.

- Not a single relaxed-MULT run: LSD may not enumerate the intended families cleanly, and the
  solution count may explode.
- Not sequential with fallback (search the leading family and fall back to the next only if it
  looks poor). A leading family can score as plausible while the correct structure sits in a
  family that is then never searched. Every viable family gets its own fair, fully constrained
  search regardless of how good another family looks.

Each per-family compound.lsd is fully constrained and carries forward all identical constraints
by the read-previous, never-reconstruct rule (HSQC, HMBC, the ring exclusion DEFF F1/F2 and
FEXP, BOND C=O, the COSY equivalence pairs, the fragment DEFF/FEXP, the inventory block). The runs
differ only in their MULT block, which is written by hand from each family's per-atom
multiplicity (CH₃ = `MULT i C 3 3`, CH₂ = `MULT i C 3 2`, CH = `MULT i C 3 1`). Two blocks for
the same skeleton:

```
; iteration_NN_A/compound.lsd -- family A (3×CH3 + CH)
MULT 11 C 3 3    ; CH3
MULT 12 C 3 3    ; CH3
MULT 13 C 3 3    ; CH3
MULT 14 C 3 1    ; CH

; iteration_NN_B/compound.lsd -- family B (2×CH3 + CH2 + CH2)
MULT 11 C 3 3    ; CH3
MULT 12 C 3 3    ; CH3
MULT 13 C 3 2    ; CH2
MULT 14 C 3 2    ; CH2
```

An HMBC correlation that one family explains directly, such as a CH₃ proton to a CH₂ carbon (a
real 2-3J), is evidence for that family. Do not explain it away as gem-dimethyl coupling.

Coverage counts searched families, not ranked ones. A family counts as searched once it has its
own `iteration_NN_<family>/` directory with a real LSD run and has sent an `[ITERATION-COMPLETE]`
reporting its solution count. A family with a large solution count (more than about 50) is not
converted to `solutions.smi`, and it is still searched: it stays in the coverage and in the
union. In that family's `[ITERATION-COMPLETE]`, note "searched, N solutions, conversion
deferred". The coordinator's coverage gate checks that every viable family was searched.

Once each family with a tractable solution set has a `solutions.smi`:

1. Build `{work_dir}/union_solutions.smi` by concatenating the per-family `solutions.smi` files.
2. Deduplicate by canonical SMILES. The `ailsa lsd rank` parser does not deduplicate, and
   duplicate SMILES across families would distort counts and ranks. Canonicalise each SMILES and
   keep one copy per canonical form before ranking.
3. Run one ranking across the union. The atom-by-atom ranking decides; it reads each family's
   `.sol` and deduplicates structures itself:
   ```bash
   ailsa lsd rank --assigned {work_dir}/iteration_NN_<family1>/compound.lsd --assigned {work_dir}/iteration_NN_<family2>/compound.lsd --format json
   ```
   The nearest-line cross-check runs on the deduplicated union file:
   ```bash
   ailsa lsd rank {work_dir}/union_solutions.smi --shifts "<13C list>" --format json
   ```
   Ranking runs across the union, never per family followed by picking the best-looking family.
4. Report which family the top-ranked solution came from, so that coverage and the winning model
   are both traceable.
