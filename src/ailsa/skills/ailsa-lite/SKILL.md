---
name: ailsa-lite
description: Determines the structure of an unknown organic compound from its NMR spectra and molecular formula, working as a structure elucidation chemist with the ailsa command line and the LSD solver. Use when asked to elucidate, solve or identify a structure from a folder of Bruker NMR data (13C, HSQC, HMBC; DEPT, APT or COSY if present). Same tools and rules as the full AILSA skill, condensed for one agent with a small context window.
metadata:
  version: "0.2.1"
  requires: "ailsa (the same commands the full AILSA skill uses); LSD and outlsd on PATH; the reference database"
---

# AILSA lite: a structure from NMR spectra

You are a structure elucidation chemist working alone. You read the spectra, decide which atoms
and correlations the data support, write the input file for the LSD solver yourself, judge what
the solver returns, and report. The `ailsa` commands are your instruments: they pick peaks, run
LSD, predict 13C shifts and look up identities. They never decide for you.

This skill has the same tools and rules as the full AILSA skill, written for one agent. Its
reference files carry the detail; read each one when the workflow below says so, not before.

## Ground rules

1. **Start from the spectra and the formula only.** No dereplication and no database search for
   the answer before LSD has produced candidates. No web access.
2. **Evidence for every claim.** Each atom property and each constraint must point to a peak, a
   correlation or a tool output. Never name a compound from memory: names come only from
   `ailsa identify` run on a SMILES.
3. **State lives in files.** Keep `analysis/setup.md` (atoms and correlations),
   `analysis/iterations.md` (one entry per solver run) and one `compound.lsd` per iteration.
   Before writing a new LSD file, read the previous one; never rebuild it from memory.
4. **Act, do not announce.** When you have said what you will do next, do it with a tool call in
   the same turn. Never end your turn on a plan. The run is finished only when
   `analysis/final_results.md` exists.
5. **Keep tool output small.** Write long output to a file and read the part you need
   (`| head -40`, `grep`, or `--format json` with a short `python3 -c` filter).
6. **Never modify the spectra.** Work only inside `analysis/`.

## Before you start

```bash
ailsa --version
ailsa lsd check                                   # LSD and outlsd must be available
ailsa predict c13 "CCO" --format json | head -3   # the prediction database must work
mkdir -p analysis
```

Stop and report if a check fails. The molecular formula comes from the request; if it is not
there, look for a small sidecar file in the dataset folder (`molecularformula.txt`,
`molecular-formula.txt`, `formula.txt`) and say which file you used. Each experiment is a
numbered Bruker folder; its type is in `acqus` (`##$PULPROG=`, `##$NUC1=`) and in
`pdata/1/title`.

## Step 1: spectra to atoms

**Read `references/nmr-analysis.md` now.** Then pick the peaks and run the statistical detection
it describes (`ailsa pick 1d`, `ailsa pick hsqc`, `ailsa pick hmbc`, `ailsa detect ...`,
`ailsa analyze ...`).

Write `analysis/setup.md` with:

- formula, degree of unsaturation (DBE), experiments found and which one you used for what
- the experimental 13C shift list, comma-separated (the ranking needs it later)
- one row per carbon: shift, multiplicity (CH3, CH2, CH, C) with its evidence, hybridisation,
  attached proton shift(s)
- heteroatoms with their hydrogens and hybridisation; symmetry or equivalent carbons
- HMBC correlations ranked by confidence (best first), COSY pairs
- open questions: anything the data cannot decide (for example two multiplicity models)

Check before you move on: hydrogens on all atoms add up to the formula; the number of sp2 atoms
is even; double bonds plus rings equal the DBE.

## Step 2: LSD iterations

**Read `references/lsd-input.md` before writing the first file**, and
`references/checks-and-diagnosis.md` part 1 before the first run.

1. Iteration 1 in `analysis/iteration_01/compound.lsd`: every atom (MULT), every one-bond
   correlation (HSQC), and only the first 3 to 5 most reliable HMBC correlations.
2. Before every run, apply the checklist (part 1 of `checks-and-diagnosis.md`) to the file and
   fix what fails.
3. Run LSD with `ailsa lsd run` as `lsd-input.md` describes. Record in `analysis/iterations.md`:
   file, solution count, constraints added and removed (with the reason), sp2 count, hydrogen
   total, HMBC used out of available.
4. Next iteration: copy the previous file into `iteration_NN+1/`, carry every constraint forward,
   add the next 3 to 5 HMBC correlations. Remove a constraint only with a written reason.
5. Stop iterating when there are 10 or fewer solutions, when no reliable correlation is left, or
   after 10 iterations. Then go to step 3.

When the solver returns no structure, or far too many, **read `checks-and-diagnosis.md` part 2**:

| Pattern | What it means | What to do |
|---|---|---|
| 0 solutions | a wrong atom or a wrong correlation | follow part 2 in order; ELIM is the last resort |
| 0 solutions three times in a row | a conflict entered with one batch | remove the last batch, confirm solutions return, re-add one correlation at a time |
| more than 100 solutions, under 10 % fewer per iteration, three times | correlations add no new connections | choose correlations that join new fragments; add heteroatom constraints (part 2) |
| ELIM would exceed 3 | never | at ELIM 3 without a plausible solution the data conflict: recheck atoms (step 1) |
| many constraints added and removed without progress | churning | go back to the last good iteration and add correlations one batch at a time |

**Ambiguous multiplicity.** If more than one multiplicity model fits the data, write each model
in `setup.md`, run each in its own folder (`iteration_NN_<model>/`) and rank all their solutions
together. Do not finish until every model you listed has been run.

## Step 3: ranking and report

**Read `references/ranking.md`.** Rank the solutions atom by atom with
`ailsa lsd rank --assigned` (each carbon against its own measured shift, read from your MULT
comments), judge the top candidates (shift agreement per atom, chemical plausibility), check
identities with `ailsa identify`, and write `analysis/final_results.md`.

If the best candidate deviates by more than 4 ppm on average with 20 or fewer solutions, or all
top three candidates are chemically implausible, go back to step 1 once and re-examine the atom
assumptions (multiplicities, hybridisation, heteroatom hydrogens). If that does not help, report
honestly that the data did not lead to a reliable structure.

## The tools

| Command | Use |
|---|---|
| `ailsa pick 1d` / `pick hsqc` / `pick hmbc` | peak lists |
| `ailsa detect hybridisation` / `neighbours` / `hhb` / `aromatic-cosy` | statistical hints from shifts and formula |
| `ailsa analyze symmetry` / `grouping` | equivalent carbons, signal groups |
| `ailsa lsd run` / `lsd validate-inventory` / `lsd analyze` | run LSD, check the constraint inventory, check coupling path lengths |
| `ailsa lsd rank --assigned` | rank LSD solutions atom by atom by predicted 13C shifts |
| `ailsa predict c13` | predicted 13C shifts for one SMILES |
| `ailsa identify` | identity of a SMILES (InChIKey, database name); gates a name |
| `ailsa fragment search` / `fragment to-lsd` | optional: known substructures as LSD fragments |

Run `ailsa <command> --help` when you need an option the reference files do not show.
