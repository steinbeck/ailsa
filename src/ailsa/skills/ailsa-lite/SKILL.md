---
name: ailsa-lite
description: Determines the structure of an unknown organic compound from its NMR spectra and molecular formula with the ailsa command line and the LSD solver. Use when asked to elucidate, solve or identify a structure from a folder of Bruker NMR data (13C, HSQC, HMBC; DEPT, APT or COSY if present). Lean version for small models - one fixed sequence of commands, no subagents.
metadata:
  version: "0.1.0"
  requires: "ailsa with the `ailsa case` commands; LSD and outlsd on PATH; the reference database"
---

# AILSA lite: a structure from NMR spectra

You find the structure by running `ailsa case` commands in a fixed order. The commands do the
bookkeeping: they pick the peaks, build the table of atoms, write the solver input, run the
solver and rank the candidate structures. Your job is to read each report and make the few
decisions the tools leave to you.

## Rules

1. Run only the commands of this skill, in the shell. Every command ends with a line `NEXT:`
   that shows the usual next command. Copy it exactly.
2. Never write or edit files yourself. Change the problem only with
   `ailsa case edit DATASET ... --reason "..."`. The reason names the observation behind it.
3. Never name a compound from memory, and never search the internet for the data or the answer.
   The report states the identity the tools derived.
4. Use the dataset path exactly as the user gave it. Results go to `DATASET/analysis/`.
5. A failing command prints `Error:`. Fix the cause and run it again. Never run the same
   failing command more than twice.

## Step 1: look at the data

```
ailsa case scan DATASET
```

Check that it says `LSD solver: ok` and `13C prediction: ok`. If one says MISSING, stop and tell
the user what is missing. Use the formula the user gave; otherwise the one the scan found.

## Step 2: build the problem

```
ailsa case setup DATASET --formula FORMULA
```

The report has three parts: the atom table, ERRORS and TO VERIFY.

## Step 3: check and fix

- **ERRORS** must be fixed before the solver can run. For each one, read the matching section
  of [references/fixing.md](references/fixing.md) and apply the edit it describes.
- **TO VERIFY** lists setup's best guesses. Keep each one unless you can point to an
  observation in the report that contradicts it. When in doubt, keep it.
- After every edit the command prints the full check again. Continue until there are no ERRORS.

Example of an edit:

```
ailsa case edit DATASET --mult 7=CH3 --reason "intense HSQC peak at 1.2 ppm, three protons"
```

## Step 4: solve

```
ailsa case solve DATASET
```

- `-> N structure(s)` with N above 0: go to step 5.
- `No structure fits`: read section "No structure" in
  [references/fixing.md](references/fixing.md), make the edits it suggests, and solve again.
  After three rounds without a structure, stop and report that the data gave no structure.
- `limit reached`: the list of structures is incomplete. Rank it anyway and say so in the report.
- `ERROR` from the solver: run `ailsa case check DATASET` and fix what it reports.

## Step 5: rank

```
ailsa case rank DATASET
```

Rank 1 has the lowest MAE: the mean difference between predicted and observed 13C shifts,
compared atom by atom. Read the result like this:

| What you see for rank 1 | What it means |
|---|---|
| MAE below 2 ppm and a margin of 0.3 ppm or more to rank 2 | a strong result |
| MAE below 2 ppm, margin below 0.3 ppm | rank 1 and 2 are both possible; name both in the note |
| MAE 2 to 4 ppm | plausible but uncertain |
| MAE above 4 ppm | probably wrong: go back to step 3 once and look for a wrong atom type |
| one or two unexplained HMBC | normal: some correlations span four bonds |
| more than three unexplained HMBC | doubtful: say so in the note |

Report rank 1. Do not pick another candidate because it looks more familiar.

## Step 6: report

```
ailsa case report DATASET --note "TEXT"
```

TEXT is two to four sentences: the structure in words (compound class, main groups), the
evidence (MAE, margin to rank 2, unexplained HMBC) and what remains uncertain. Then answer the
user with the SMILES of rank 1 and the path of `final_results.md`.
