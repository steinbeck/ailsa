#!/usr/bin/env python3
"""AILSA HOSE prediction on the strict NMRShiftDB2 referee set (quick task 261013-knr).

Runs in the AILSA environment (`/opt/miniconda3/bin/python`), NOT the csp5 venv: this is the
only script in this task that touches `ailsa`. Read-only use of the reference DB.

On COCONUT the HOSE prediction is circular (its stats were generated from ACD-predicted
COCONUT shifts), so it is only meaningful here, on the NMRShiftDB2 referee, as an
"ACD-via-HOSE" proxy (see RESEARCH.md Pattern 4).

Ported from `~/Dropbox/develop/data/csp5-vs-acd/scripts/ailsa_hose_smoke.py` (verified).
"""
import gzip
import json
import sqlite3
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import common  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

N_POOL_WORKERS = 4

_predictor = None


def _init_worker():
    global _predictor
    from ailsa.prediction.predictor import C13Predictor
    _predictor = C13Predictor.from_database(str(config.DEREP_DB))


def _predict_one(args):
    rid, molblock = args
    m = Chem.MolFromMolBlock(molblock, removeHs=False)
    if m is None:
        return rid, None, "parse_fail"
    for a in m.GetAtoms():
        a.SetIntProp("orig_idx", a.GetIdx())
    h = Chem.RemoveHs(m)
    try:
        out = _predictor.predict_from_mol(h)
    except Exception as e:  # noqa: BLE001
        return rid, None, f"predict_fail:{str(e)[:150]}"
    rows = []
    idx_set = set()
    for p in out:
        orig = h.GetAtomWithIdx(p.atom_index).GetIntProp("orig_idx")
        idx_set.add(orig)
        rows.append((orig, p.shift, p.radius_used, p.match_count))
    if not common.self_check(m, idx_set):
        return rid, None, "self_check_fail"
    if not rows:
        # Deviation (2026-10-14, Rule 1): `predict_from_mol` can legitimately return an empty
        # list (no HOSE-stats match at any radius for any carbon) -- confirmed by direct
        # inspection, not a bug in the predictor. `self_check` passes vacuously on an empty
        # idx_set, so without this branch these ~3% "zero HOSE coverage" molecules were
        # silently counted as `n_ok` yet left no row in hose.tsv.gz, breaking the recount
        # invariant (input must equal rows-with-output + rows-in-fail-file). Tracked as its
        # own, non-error reason so `check`'s recount balances and the report can state the
        # coverage gap plainly.
        return rid, None, "no_hose_coverage"
    return rid, rows, None


def print_schema_meta():
    con = sqlite3.connect(str(config.DEREP_DB))
    try:
        rows = con.execute("select key, value from schema_meta").fetchall()
    except Exception as e:  # noqa: BLE001
        rows = [("error", str(e))]
    finally:
        con.close()
    print("derep DB schema_meta:", rows)
    return rows


def main():
    out_dir = config.RUNS_DIR / "hose_referee"
    out_dir.mkdir(parents=True, exist_ok=True)
    referee_path = config.INPUTS_DIR / "referee.sdf"

    schema_meta = print_schema_meta()

    records = []
    sup = Chem.ForwardSDMolSupplier(str(referee_path), removeHs=False)
    pos = -1
    n_parse_fail = 0
    for m in sup:
        pos += 1
        if m is None:
            n_parse_fail += 1
            continue
        rid = m.GetProp("rid")
        records.append((rid, Chem.MolToMolBlock(m)))

    n_total = len(records) + n_parse_fail
    json.dump({"n_records": n_total, "n_parse_fail": n_parse_fail, "schema_meta": schema_meta},
               open(out_dir / "manifest.json", "w"), indent=2)
    print(f"referee.sdf: {len(records)} usable records, {n_parse_fail} parse failures")

    tsv_path = out_dir / "hose.tsv.gz"
    fail_path = out_dir / "hose.fail.tsv"
    n_ok = n_fail = 0

    with Pool(N_POOL_WORKERS, initializer=_init_worker) as pool, \
            gzip.open(tsv_path, "wt") as tfh, open(fail_path, "w") as ffh:
        tfh.write("rid\tatom_idx0\those_ppm\tradius_used\tmatch_count\n")
        ffh.write("rid\tstage\treason\n")
        for rid, rows, err in pool.imap_unordered(_predict_one, records, chunksize=50):
            if err is not None:
                ffh.write(f"{rid}\those\t{err}\n")
                n_fail += 1
                continue
            n_ok += 1
            for orig_idx, shift, radius, match_count in rows:
                tfh.write(f"{rid}\t{orig_idx}\t{shift}\t{radius}\t{match_count}\n")

    json.dump({"n_in": len(records), "n_ok": n_ok, "n_fail": n_fail},
               open(out_dir / "hose.done", "w"))

    seen_ok, seen_fail = set(), set()
    with gzip.open(tsv_path, "rt") as fh:
        next(fh, None)
        for line in fh:
            seen_ok.add(line.split("\t", 1)[0])
    with open(fail_path) as fh:
        next(fh, None)
        for line in fh:
            seen_fail.add(line.split("\t", 1)[0])

    n_recount = len(seen_ok | seen_fail)
    if n_recount != len(records):
        print(f"WARNING: recount mismatch: expected {len(records)}, got {n_recount}", file=sys.stderr)
        sys.exit(1)

    result = {"n_in": len(records), "n_ok_rids": len(seen_ok), "n_fail_rids": len(seen_fail),
              "n_parse_fail_loading_referee_sdf": n_parse_fail}
    (out_dir / "ALL_DONE").write_text(json.dumps(result))
    print(f"HOSE referee done: {result}")


if __name__ == "__main__":
    main()
