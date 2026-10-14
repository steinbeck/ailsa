"""Shared paths and constants for the CSP5-vs-ACD 13C comparison (quick task 261013-knr).

Import this from every script in this directory. Never scatter these paths elsewhere.
Must stay importable from both the csp5 venv and the AILSA (/opt/miniconda3) env, so this
module uses only the standard library.
"""
import os
from pathlib import Path

# All data and per-atom tables live outside the repo. Override with CSP5_VS_ACD_DIR if needed.
SCRATCH = Path(os.environ.get("CSP5_VS_ACD_DIR", str(Path.home() / "Dropbox/develop/data/csp5-vs-acd")))

CSP5_PYTHON = SCRATCH / ".venv-csp5" / "bin" / "python"
AILSA_PYTHON = Path("/opt/miniconda3/bin/python")

# Source SD files (verified by the planner; see RESEARCH.md "facts").
ACD_SDF = Path.home() / "Dropbox/develop/data/Sherlock-original-input-sd 2/acd_coconut.sdf"
NSDB_SDF = Path.home() / "Dropbox/develop/data/Sherlock-original-input-sd/nmrshiftdb2withsignals.sd"

REFEREE_IDS = SCRATCH / "referee_nmrshiftdb_ids_strict.json"
COCONUT_KEYS = SCRATCH / "coconut_inchikeys.json"
ZENODO_DIR = SCRATCH / "zenodo" / "x" / "zenodo_csp5_upload" / "data"

# repo-relative reference DB, resolved from this file's location:
# scripts/csp5-vs-acd/config.py -> parents[0]=csp5-vs-acd, [1]=scripts, [2]=repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
DEREP_DB = REPO_ROOT / "data" / "reference" / "lucy-ng-derep.db"

SEED = 20261013
SAMPLE_N = 20000
# 6, not 8: 4 performance + 4 efficiency cores on this Mac, and other jobs share the machine.
# Lowered from 7 on 2026-10-14 together with the chunked/timeout-guarded embedder -- see
# common.embed_mol_with_timeout and the SUMMARY's "Deviations" section.
N_WORKERS = 6
# Molecules per embed+predict+write+done chunk inside `02_csp5_run.py work`. Keeps runs
# resumable and gives visible progress instead of one shard-sized all-or-nothing step.
CHUNK_SIZE = 128

# Heavy-atom size bins, inclusive bounds.
SIZE_BINS = [(0, 15), (16, 25), (26, 40), (41, 60), (61, 10**6)]

INPUTS_DIR = SCRATCH / "inputs"
RUNS_DIR = SCRATCH / "runs"
RESULTS_DIR = SCRATCH / "results"


def size_bin_label(lo, hi):
    if hi >= 10**6:
        return f">={lo}"
    return f"{lo}-{hi}"
