# CSP5 vs ACD 13C comparison (quick task 261013-knr)

Purpose: compare the free, MIT-licensed CSP5 13C predictor with the ACD/Labs C+H NMR Predictors
2020.1.0 shifts that AILSA's reference DB holds for COCONUT (COCONUT 13C shifts: ACD/Labs
predictions from J.-M. Nuzillard, Zenodo, doi:10.5281/zenodo.6561449, CC BY 4.0), to see whether a
reference DB built from freely computable predictions would be in the same league. This is a sample
comparison (20,000 COCONUT records + the full strict NMRShiftDB2 referee), not the full
895k-record run.

**Nothing from `~/Dropbox/develop/data/csp5-vs-acd/` (SCRATCH) is ever copied into this repo.**
No script here contains a compound ID, a structure or a shift value as a literal. All ACD
values, per-atom tables, and the referee ID list live only under SCRATCH, outside the git tree.
Results, the report and its verification also stay under SCRATCH (`SCRATCH/results/`,
`SCRATCH/report/`, `SCRATCH/verify/`); nothing derived from them is committed.

## Order of steps and which Python runs which script

| Step | Script | Python | What |
|---|---|---|---|
| 0 | `00_positive_control.py` | csp5 venv | **Run first.** Reproduces the known CSP5 accuracy on molecules it never trained on. If this fails, stop — no later number is trustworthy. |
| 1 | `01_prepare.py` | csp5 venv | Samples 20,000 COCONUT records, extracts the referee NMRShiftDB2 records, matches COCONUT to the referee by InChIKey. Writes `SCRATCH/inputs/*.sdf`. |
| 2 | `02_csp5_run.py shard/launch/check` | csp5 venv | Shards, predicts (background, resumable) and verifies completion for `coconut_sample.sdf` -> `runs/csp5_coconut` and `referee.sdf` -> `runs/csp5_referee`. Launch coconut first; launch referee only after coconut's `check` passes (14 worker processes at once is too many for 8 cores). |
| 3 | `03_hose_referee.py` | **AILSA env** (`/opt/miniconda3/bin/python`) | HOSE-code 13C prediction on the referee, using the same reference DB that backs AILSA's dereplication. Can run in the background while step 2 runs. |
| 4 | `04_compare.py` | csp5 venv | Joins everything, computes comparisons A/B/C, writes `SCRATCH/results/{results.json,tables.md}`. |
| 5 | `SCRATCH/report/` | — | German report (kept outside the repo), written from `results.json` only. |

`common.py` and `config.py` are shared by every script above and import only
`rdkit` + stdlib + `numpy`, so they load in both Python environments.

## Where data lives

- `SCRATCH = ~/Dropbox/develop/data/csp5-vs-acd/` (override with `CSP5_VS_ACD_DIR`).
- `SCRATCH/inputs/` — sampled/extracted SDFs built by `01_prepare.py`.
- `SCRATCH/runs/{csp5_coconut,csp5_referee,hose_referee}/` — sharded prediction runs.
- `SCRATCH/results/` — `results.json`, `tables.md`, `run_counts.json` from `04_compare.py`.
- The repo only ever gains the scripts in this directory.

## The four traps that have bitten before

1. **Re-indexing.** `predict_mols` drops molecules that fail and re-numbers `molecule_id`. Map
   output ONLY via the `rid` column carried through `extra_cols`. Never use output position or
   `molecule_id`.
2. **Striped sharding.** Dealing records 0, 7, 14, ... gives one worker all the giant
   molecules. Shards here are sorted by heavy-atom count descending, then dealt round-robin.
3. **A completion marker written after a kill.** Each worker writes its own `shard_NN.done`
   (with `n_in`, `n_ok`, `n_fail`) only after its output files are flushed and closed.
   `ALL_DONE` is written only by a separate `check` step that re-counts rows from the output
   files and verifies the count matches the input manifest. Downstream steps check the count,
   not just the marker's existence.
4. **`predict_molecule_file(..., regenerate_geometry=True)` aborts the whole file on one
   embedding failure.** Embedding happens per molecule in a try/except using
   `csp5._runtime.cascade_core.embed_mol_conformers_canonical` directly.

Two more worth knowing:

5. Never `slopcheck install` and never pip/uv-install into `/opt/miniconda3` (that env hosts
   the global `ailsa`).
6. HOSE on COCONUT is circular (its stats were generated from ACD-predicted COCONUT shifts), so
   it is excluded from comparison A and only meaningful on the NMRShiftDB2 referee.
