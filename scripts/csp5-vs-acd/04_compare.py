#!/usr/bin/env python3
"""Join and statistics for comparisons A, B and C (quick task 261013-knr). csp5 venv.

Comparison A: CSP5 vs ACD agreement on the COCONUT sample (no experimental truth).
Comparison B: CSP5 / HOSE / ACD-NSDB / ACD-COCONUT / ACD-union vs experiment on the strict
              NMRShiftDB2 referee, plus ACD's own database-leakage diagnostic and strata.
Comparison C: the carbons where CSP5, ACD(union), HOSE and experiment all exist, side by side,
              with paired bootstrap CIs for the headline differences.

Writes only aggregates to SCRATCH/results/ (results.json, tables.md, run_counts.json). No
per-atom row, compound ID, structure or ACD value leaves SCRATCH.
"""
import gzip
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import common  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

HEAVY_BINS_GE_26 = {"26-40", "41-60", ">=61"}


# ---------------------------------------------------------------------------
# Run completion gate
# ---------------------------------------------------------------------------

def require_all_done(run_dir, label):
    run_dir = Path(run_dir)
    all_done_path = run_dir / "ALL_DONE"
    if not all_done_path.exists():
        print(f"ERROR: {label} has no ALL_DONE marker at {all_done_path}. Run it to completion "
              f"before comparing.", file=sys.stderr)
        sys.exit(1)
    manifest = json.load(open(run_dir / "manifest.json"))
    result = json.loads(all_done_path.read_text())
    n_expected = manifest.get("n_records")
    n_ok = result.get("n_ok_rids")
    n_fail = result.get("n_fail_rids")
    if n_ok is None or n_fail is None or n_expected is None or (n_ok + n_fail) != n_expected:
        print(f"ERROR: {label} count mismatch at comparison time: ok={n_ok} fail={n_fail} "
              f"expected={n_expected}. This indicates a run that did not truly complete.",
              file=sys.stderr)
        sys.exit(1)
    print(f"{label}: ALL_DONE verified, ok={n_ok} fail={n_fail} expected={n_expected}")
    return manifest, result


def load_fail_reasons(run_dir):
    """Aggregate (stage, reason-bucket) counts from every shard_*.chunk_*.fail.tsv."""
    counts = Counter()
    for fail_path in sorted(Path(run_dir).glob("shard_*.chunk_*.fail.tsv")):
        with open(fail_path) as fh:
            next(fh, None)
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                _rid, stage, reason = parts[0], parts[1], parts[2]
                if stage == "embed":
                    bucket = "embed_timeout" if reason.startswith("embed_timeout") else "embed_fail"
                else:
                    bucket = stage
                counts[bucket] += 1
    return dict(counts)


def load_csp5_predictions(run_dir):
    preds = defaultdict(dict)
    for tsv_path in sorted(Path(run_dir).glob("shard_*.chunk_*.tsv.gz")):
        with gzip.open(tsv_path, "rt") as fh:
            next(fh, None)
            for line in fh:
                rid, idx, shift = line.rstrip("\n").split("\t")
                preds[rid][int(idx)] = float(shift)
    return preds


def load_hose_predictions(path):
    preds = defaultdict(dict)
    with gzip.open(path, "rt") as fh:
        next(fh, None)
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            rid, idx, shift = parts[0], parts[1], parts[2]
            preds[rid][int(idx)] = float(shift)
    return preds


# ---------------------------------------------------------------------------
# Shared molecule helpers
# ---------------------------------------------------------------------------

def classify_carbons(mol):
    """{orig_idx: (carbon_class, hetero_bound)} for every carbon of `mol` (H-stripped view)."""
    for a in mol.GetAtoms():
        a.SetIntProp("orig_idx", a.GetIdx())
    h = Chem.RemoveHs(mol)
    out = {}
    for a in h.GetAtoms():
        if a.GetAtomicNum() != 6:
            continue
        orig = a.GetIntProp("orig_idx")
        out[orig] = (common.carbon_class(a), common.hetero_bound(a))
    return out


def classify_solvent(raw):
    if not raw:
        return "unknown"
    norm = raw.lower().replace(" ", "").replace("-", "")
    if "cdcl3" in norm:
        return "CDCl3"
    return "other"


def map_coconut_to_nsdb(coco_mol, nsdb_mol):
    """Map COCONUT 0-based atom indices onto the NMRShiftDB2 molblock's indices via full
    substructure match on H-stripped copies (equal heavy-atom count required).
    Returns (mapping_dict_or_None, used_chirality, reason)."""
    for a in coco_mol.GetAtoms():
        a.SetIntProp("orig_idx", a.GetIdx())
    for a in nsdb_mol.GetAtoms():
        a.SetIntProp("orig_idx", a.GetIdx())
    coco_h = Chem.RemoveHs(coco_mol)
    nsdb_h = Chem.RemoveHs(nsdb_mol)
    if coco_h.GetNumHeavyAtoms() != nsdb_h.GetNumHeavyAtoms():
        return None, False, "heavy_atom_count_mismatch"

    match = coco_h.GetSubstructMatch(nsdb_h, useChirality=True)
    used_chirality = True
    if not match:
        match = coco_h.GetSubstructMatch(nsdb_h, useChirality=False)
        used_chirality = False
    if not match:
        return None, False, "no_substruct_match"

    coco_to_nsdb = {}
    for nsdb_h_idx, coco_h_idx in enumerate(match):
        nsdb_orig = nsdb_h.GetAtomWithIdx(nsdb_h_idx).GetIntProp("orig_idx")
        coco_orig = coco_h.GetAtomWithIdx(coco_h_idx).GetIntProp("orig_idx")
        coco_to_nsdb[coco_orig] = nsdb_orig
    return coco_to_nsdb, used_chirality, "ok"


# ---------------------------------------------------------------------------
# Comparison A: COCONUT sample, CSP5 vs ACD agreement (no truth)
# ---------------------------------------------------------------------------

def run_comparison_a(csp5_coconut_preds):
    sample_path = config.INPUTS_DIR / "coconut_sample.sdf"
    rows = []  # (rid, signed_err, carbon_class, hetero_bound, size_bin)
    n_total = n_no_assignment = n_no_csp5 = n_molecules_used = 0

    sup = Chem.ForwardSDMolSupplier(str(sample_path), removeHs=False)
    for mol in sup:
        if mol is None:
            continue
        n_total += 1
        rid = mol.GetProp("SMILES_ID")
        if not mol.HasProp("NMREDATA_ASSIGNMENT"):
            n_no_assignment += 1
            continue
        acd = common.acd_assignment(mol)
        csp5_m = csp5_coconut_preds.get(rid)
        if not csp5_m:
            n_no_csp5 += 1
            continue
        common_idx = set(acd) & set(csp5_m)
        if not common_idx:
            continue
        carbon_info = classify_carbons(mol)
        size_bin = common.size_bin(mol)
        n_molecules_used += 1
        for idx in common_idx:
            cls, hetero = carbon_info.get(idx, ("unknown", False))
            err = csp5_m[idx] - acd[idx]
            rows.append((rid, err, cls, hetero, size_bin))

    errors = [r[1] for r in rows]
    mol_ids = [r[0] for r in rows]
    overall = common.metrics(errors, mol_ids)

    by_class = {}
    for cls in sorted({r[2] for r in rows}):
        sub = [r for r in rows if r[2] == cls]
        by_class[cls] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    by_hetero_all = {}
    for flag in (True, False):
        sub = [r for r in rows if r[3] == flag]
        by_hetero_all[str(flag)] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    by_hetero_sp3 = {}
    sp3_classes = {"CH3", "CH2", "CH", "Cq"}
    for flag in (True, False):
        sub = [r for r in rows if r[3] == flag and r[2] in sp3_classes]
        by_hetero_sp3[str(flag)] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    by_size = {}
    for sb in sorted({r[4] for r in rows}):
        sub = [r for r in rows if r[4] == sb]
        by_size[sb] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    cell_errors = defaultdict(list)
    for r in rows:
        cell_errors[(r[2], r[4])].append(r[1])
    cells = []
    for (cls, sb), errs in cell_errors.items():
        if len(errs) < 200:
            continue
        cells.append({"carbon_class": cls, "size_bin": sb, "n": len(errs),
                       "mean_signed_diff": statistics.mean(errs)})
    cells.sort(key=lambda c: -abs(c["mean_signed_diff"]))
    top_cells = cells[:15]

    counts = {
        "n_records_scanned": n_total,
        "n_no_assignment": n_no_assignment,
        "n_no_csp5_prediction": n_no_csp5,
        "n_molecules_compared": n_molecules_used,
        "n_carbons_compared": len(rows),
    }
    return {
        "label": "CSP5 - ACD agreement on COCONUT (Uebereinstimmung, nicht Genauigkeit)",
        "overall": overall,
        "by_carbon_class": by_class,
        "by_hetero_bound_all_carbons": by_hetero_all,
        "by_hetero_bound_sp3_only": by_hetero_sp3,
        "by_size_bin": by_size,
        "top_disagreement_cells": top_cells,
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# Comparison B (+ data shared with C): referee vs experiment
# ---------------------------------------------------------------------------

def build_coco_referee_index():
    """{full_inchikey: (mol, acd_dict)} from coconut_referee_match.sdf."""
    path = config.INPUTS_DIR / "coconut_referee_match.sdf"
    index = {}
    n_no_assignment = 0
    sup = Chem.ForwardSDMolSupplier(str(path), removeHs=False)
    for mol in sup:
        if mol is None:
            continue
        if not mol.HasProp("NMREDATA_ASSIGNMENT"):
            n_no_assignment += 1
            continue
        key = Chem.MolToInchiKey(mol)
        acd = common.acd_assignment(mol)
        index[key] = (mol, acd)
    return index, n_no_assignment


def run_comparison_b_and_c(csp5_referee_preds, hose_preds):
    coco_index, n_coco_no_assignment = build_coco_referee_index()
    referee_path = config.INPUTS_DIR / "referee.sdf"

    predictor_rows = defaultdict(list)  # name -> [(rid, err, cls, hetero, size_bin, solvent)]
    mol_stratum = {}  # rid -> "'>=90%'" | "'10-90%'" | "'<10%'" | None (no ACD coverage)
    c_records = []  # (rid, err_csp5, err_acd_union, err_hose, carbon_class, size_bin)

    map_stats = Counter()
    gate1_abs_diffs = []  # |ACD-NSDB - ACD-COCONUT| on atoms both cover (sanity gate 1)
    n_total = n_no_exp = 0
    carbons_total = 0
    hose_carbons_total = 0

    sup = Chem.ForwardSDMolSupplier(str(referee_path), removeHs=False)
    for mol in sup:
        if mol is None:
            continue
        n_total += 1
        rid = mol.GetProp("rid")
        if not mol.HasProp("exp13c"):
            n_no_exp += 1
            continue
        exp = common.nsdb_spectrum(mol.GetProp("exp13c"))

        acd_nsdb = common.nsdb_spectrum(mol.GetProp("acd_nsdb13c")) if mol.HasProp("acd_nsdb13c") else {}

        acd_coco = {}
        referee_key = mol.GetProp("inchikey") if mol.HasProp("inchikey") else ""
        if referee_key and referee_key in coco_index:
            coco_mol, coco_acd = coco_index[referee_key]
            mapping, used_chirality, reason = map_coconut_to_nsdb(coco_mol, mol)
            if mapping is None:
                map_stats[reason] += 1
            else:
                map_stats["chirality_match" if used_chirality else "achirality_match"] += 1
                for c_idx, shift in coco_acd.items():
                    if c_idx in mapping:
                        acd_coco[mapping[c_idx]] = shift
        acd_union = dict(acd_nsdb)
        acd_union.update(acd_coco)

        csp5_m = csp5_referee_preds.get(rid, {})
        hose_m = hose_preds.get(rid, {})

        carbon_info = classify_carbons(mol)
        size_bin = common.size_bin(mol)
        solvent = classify_solvent(mol.GetProp("exp_solvent") if mol.HasProp("exp_solvent") else "")

        carbons_total += len(carbon_info)
        hose_carbons_total += len(set(hose_m) & set(carbon_info))

        for name, pred in (("CSP5", csp5_m), ("HOSE", hose_m), ("ACD-NSDB", acd_nsdb),
                           ("ACD-COCONUT", acd_coco), ("ACD-union", acd_union)):
            common_idx = set(pred) & set(exp)
            for idx in common_idx:
                cls, hetero = carbon_info.get(idx, ("unknown", False))
                err = pred[idx] - exp[idx]
                predictor_rows[name].append((rid, err, cls, hetero, size_bin, solvent))

        acd_exp_common = set(acd_union) & set(exp)
        if acd_exp_common:
            share_exact = sum(
                1 for idx in acd_exp_common if abs(acd_union[idx] - exp[idx]) <= 0.05
            ) / len(acd_exp_common)
            if share_exact >= 0.90:
                stratum = ">=90%"
            elif share_exact >= 0.10:
                stratum = "10-90%"
            else:
                stratum = "<10%"
            mol_stratum[rid] = stratum

        quad_common = set(csp5_m) & set(hose_m) & set(acd_union) & set(exp)
        for idx in quad_common:
            cls, _hetero = carbon_info.get(idx, ("unknown", False))
            c_records.append((rid, csp5_m[idx] - exp[idx], acd_union[idx] - exp[idx],
                               hose_m[idx] - exp[idx], cls, size_bin))

        # Sanity-gate 1 input: molecules with BOTH ACD-NSDB and ACD-COCONUT coverage, compared
        # to each other directly (not via experiment).
        both_common = set(acd_nsdb) & set(acd_coco)
        for idx in both_common:
            gate1_abs_diffs.append(abs(acd_nsdb[idx] - acd_coco[idx]))

    return {
        "predictor_rows": predictor_rows,
        "mol_stratum": mol_stratum,
        "c_records": c_records,
        "map_stats": map_stats,
        "gate1_abs_diffs": gate1_abs_diffs,
        "counts": {
            "n_referee_records": n_total,
            "n_no_experimental_spectrum": n_no_exp,
            "n_coco_referee_match_no_assignment": n_coco_no_assignment,
            "n_coco_referee_match_total": len(coco_index),
            "carbons_total": carbons_total,
            "hose_carbons_with_prediction": hose_carbons_total,
            "hose_carbons_without_prediction": carbons_total - hose_carbons_total,
        },
    }


def aggregate_predictor_rows(rows):
    errors = [r[1] for r in rows]
    mol_ids = [r[0] for r in rows]
    overall = common.metrics(errors, mol_ids)

    by_class = {}
    for cls in sorted({r[2] for r in rows}):
        sub = [r for r in rows if r[2] == cls]
        by_class[cls] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    by_hetero = {}
    for flag in (True, False):
        sub = [r for r in rows if r[3] == flag]
        by_hetero[str(flag)] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    by_size = {}
    for sb in sorted({r[4] for r in rows}):
        sub = [r for r in rows if r[4] == sb]
        by_size[sb] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    by_solvent = {}
    for sv in sorted({r[5] for r in rows}):
        sub = [r for r in rows if r[5] == sv]
        by_solvent[sv] = common.metrics([r[1] for r in sub], [r[0] for r in sub])

    return {
        "overall": overall,
        "by_carbon_class": by_class,
        "by_hetero_bound": by_hetero,
        "by_size_bin": by_size,
        "by_solvent": by_solvent,
    }


# ---------------------------------------------------------------------------
# Sanity gates
# ---------------------------------------------------------------------------

def sanity_gates(b_data, b_agg):
    gates = {}
    ok = True

    # Gate 1: ACD-NSDB vs ACD-COCONUT agreement on atoms both cover directly (not via
    # experiment), on molecules carrying both.
    gate1_diffs = b_data.get("gate1_abs_diffs", [])
    if gate1_diffs:
        gate1_median = statistics.median(gate1_diffs)
        gates["acd_nsdb_vs_coconut_median_abs_diff"] = gate1_median
        gates["acd_nsdb_vs_coconut_n"] = len(gate1_diffs)
        gates["gate1_passed"] = gate1_median < 1.0
        if gate1_median >= 1.0:
            ok = False
    else:
        gates["acd_nsdb_vs_coconut_median_abs_diff"] = None
        gates["acd_nsdb_vs_coconut_n"] = 0
        gates["gate1_passed"] = True  # vacuously true: no molecules to check

    mae_coco = b_agg["ACD-COCONUT"]["overall"]["MAE"]
    mae_nsdb = b_agg["ACD-NSDB"]["overall"]["MAE"]
    gates["mae_acd_coconut_vs_exp"] = mae_coco
    gates["mae_acd_nsdb_vs_exp"] = mae_nsdb
    if mae_coco is not None and mae_nsdb is not None:
        if mae_coco >= 2 * mae_nsdb:
            ok = False
    gates["gate2_passed"] = mae_coco is None or mae_nsdb is None or mae_coco < 2 * mae_nsdb

    mae_csp5 = b_agg["CSP5"]["overall"]["MAE"]
    gates["mae_csp5_on_referee"] = mae_csp5
    gates["gate3_passed"] = mae_csp5 is not None and 0.3 <= mae_csp5 <= 3.0
    if not gates["gate3_passed"]:
        ok = False

    return ok, gates


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    manifest_coco, result_coco = require_all_done(config.RUNS_DIR / "csp5_coconut", "CSP5 coconut run")
    manifest_ref, result_ref = require_all_done(config.RUNS_DIR / "csp5_referee", "CSP5 referee run")
    manifest_hose, result_hose = require_all_done(config.RUNS_DIR / "hose_referee", "HOSE referee run")

    schema_meta = manifest_hose.get("schema_meta")

    csp5_coconut_preds = load_csp5_predictions(config.RUNS_DIR / "csp5_coconut")
    csp5_referee_preds = load_csp5_predictions(config.RUNS_DIR / "csp5_referee")
    hose_preds = load_hose_predictions(config.RUNS_DIR / "hose_referee" / "hose.tsv.gz")

    print(f"loaded CSP5 coconut predictions for {len(csp5_coconut_preds)} molecules")
    print(f"loaded CSP5 referee predictions for {len(csp5_referee_preds)} molecules")
    print(f"loaded HOSE referee predictions for {len(hose_preds)} molecules")

    # --- Comparison A ---
    comp_a = run_comparison_a(csp5_coconut_preds)
    print(f"Comparison A: {comp_a['counts']}")

    # --- Comparison B / C shared pass ---
    b_data = run_comparison_b_and_c(csp5_referee_preds, hose_preds)
    print(f"Comparison B/C pass: {b_data['counts']}")
    print(f"ACD-COCONUT mapping stats: {dict(b_data['map_stats'])}")

    b_agg = {name: aggregate_predictor_rows(rows) for name, rows in b_data["predictor_rows"].items()}

    # ACD leakage strata: report ACD(union)/CSP5/HOSE metrics restricted to molecules in each
    # stratum (same molecule membership for all three predictors; each predictor's own carbon
    # coverage within those molecules).
    strata_labels = [">=90%", "10-90%", "<10%"]
    strata_results = {}
    for stratum in strata_labels:
        mols_in_stratum = {rid for rid, s in b_data["mol_stratum"].items() if s == stratum}
        strata_results[stratum] = {
            "n_molecules": len(mols_in_stratum),
            "ACD-union": aggregate_predictor_rows(
                [r for r in b_data["predictor_rows"]["ACD-union"] if r[0] in mols_in_stratum])["overall"],
            "CSP5": aggregate_predictor_rows(
                [r for r in b_data["predictor_rows"]["CSP5"] if r[0] in mols_in_stratum])["overall"],
            "HOSE": aggregate_predictor_rows(
                [r for r in b_data["predictor_rows"]["HOSE"] if r[0] in mols_in_stratum])["overall"],
        }

    ok, gates = sanity_gates(b_data, b_agg)
    print(f"Sanity gates: {gates}")
    if not ok:
        print("ERROR: a sanity gate failed. This indicates a mapping bug, not a chemistry "
              "result. Aborting before writing results.", file=sys.stderr)
        sys.exit(1)

    # --- Comparison C ---
    c_records = b_data["c_records"]
    err_csp5 = [r[1] for r in c_records]
    err_acd = [r[2] for r in c_records]
    err_hose = [r[3] for r in c_records]
    mol_ids_c = [r[0] for r in c_records]
    classes_c = [r[4] for r in c_records]
    sizes_c = [r[5] for r in c_records]

    comp_c = {
        "n_carbons": len(c_records),
        "n_molecules": len(set(mol_ids_c)),
        "overall": {
            "CSP5": common.metrics(err_csp5, mol_ids_c),
            "ACD-union": common.metrics(err_acd, mol_ids_c),
            "HOSE": common.metrics(err_hose, mol_ids_c),
        },
        "by_carbon_class": {},
        "by_size_bin": {},
        "by_acd_exactness_stratum": {},
        "bootstrap": {},
    }
    for cls in sorted(set(classes_c)):
        sel = [i for i, c in enumerate(classes_c) if c == cls]
        comp_c["by_carbon_class"][cls] = {
            "CSP5": common.metrics([err_csp5[i] for i in sel], [mol_ids_c[i] for i in sel]),
            "ACD-union": common.metrics([err_acd[i] for i in sel], [mol_ids_c[i] for i in sel]),
            "HOSE": common.metrics([err_hose[i] for i in sel], [mol_ids_c[i] for i in sel]),
        }
    for sb in sorted(set(sizes_c)):
        sel = [i for i, s in enumerate(sizes_c) if s == sb]
        comp_c["by_size_bin"][sb] = {
            "CSP5": common.metrics([err_csp5[i] for i in sel], [mol_ids_c[i] for i in sel]),
            "ACD-union": common.metrics([err_acd[i] for i in sel], [mol_ids_c[i] for i in sel]),
            "HOSE": common.metrics([err_hose[i] for i in sel], [mol_ids_c[i] for i in sel]),
        }
    for stratum in strata_labels:
        mols_in_stratum = {rid for rid, s in b_data["mol_stratum"].items() if s == stratum}
        sel = [i for i, rid in enumerate(mol_ids_c) if rid in mols_in_stratum]
        comp_c["by_acd_exactness_stratum"][stratum] = {
            "n_carbons": len(sel),
            "CSP5": common.metrics([err_csp5[i] for i in sel], [mol_ids_c[i] for i in sel]),
            "ACD-union": common.metrics([err_acd[i] for i in sel], [mol_ids_c[i] for i in sel]),
            "HOSE": common.metrics([err_hose[i] for i in sel], [mol_ids_c[i] for i in sel]),
        }

    def bootstrap_subset(sel_indices, label):
        sub_csp5 = [err_csp5[i] for i in sel_indices]
        sub_acd = [err_acd[i] for i in sel_indices]
        sub_hose = [err_hose[i] for i in sel_indices]
        sub_mol = [mol_ids_c[i] for i in sel_indices]
        return {
            "n_carbons": len(sel_indices),
            "MAE_CSP5_minus_MAE_ACD": common.paired_bootstrap(sub_csp5, sub_acd, sub_mol),
            "MAE_CSP5_minus_MAE_HOSE": common.paired_bootstrap(sub_csp5, sub_hose, sub_mol),
        }

    all_idx = list(range(len(c_records)))
    comp_c["bootstrap"]["overall"] = bootstrap_subset(all_idx, "overall")
    lt10_mols = {rid for rid, s in b_data["mol_stratum"].items() if s == "<10%"}
    comp_c["bootstrap"]["stratum_lt10pct"] = bootstrap_subset(
        [i for i in all_idx if mol_ids_c[i] in lt10_mols], "stratum<10%")
    comp_c["bootstrap"]["heavy_ge_26"] = bootstrap_subset(
        [i for i in all_idx if sizes_c[i] in HEAVY_BINS_GE_26], "heavy>=26")

    # --- Write results ---
    results = {
        "A": comp_a,
        "B": {
            "by_predictor": b_agg,
            "acd_exactness_strata": strata_results,
            "counts": b_data["counts"],
            "mapping_stats": dict(b_data["map_stats"]),
            "sanity_gates": gates,
        },
        "C": comp_c,
        "counts": {
            "csp5_coconut": {"manifest": manifest_coco, "result": result_coco,
                              "fail_reasons": load_fail_reasons(config.RUNS_DIR / "csp5_coconut")},
            "csp5_referee": {"manifest": manifest_ref, "result": result_ref,
                              "fail_reasons": load_fail_reasons(config.RUNS_DIR / "csp5_referee")},
            "hose_referee": {"manifest": {k: v for k, v in manifest_hose.items() if k != "schema_meta"},
                              "result": result_hose},
            "db_schema_meta": schema_meta,
        },
    }

    (config.RESULTS_DIR / "results.json").write_text(json.dumps(results, indent=2, default=str))

    run_counts = {
        "csp5_coconut": result_coco, "csp5_referee": result_ref, "hose_referee": result_hose,
        "comparison_a": comp_a["counts"], "comparison_b": b_data["counts"],
        "mapping_stats": dict(b_data["map_stats"]),
    }
    (config.RESULTS_DIR / "run_counts.json").write_text(json.dumps(run_counts, indent=2, default=str))

    write_tables_md(results)
    print("04_compare.py done. Wrote results.json, run_counts.json, tables.md under",
          config.RESULTS_DIR)


def fmt_metrics(m):
    if not m or m.get("MAE") is None:
        return "n=0"
    return (f"n={m['n_carbons']} (mols={m['n_molecules']}) MAE={m['MAE']:.2f} "
            f"median={m['median_AE']:.2f} RMSE={m['RMSE']:.2f} bias={m['mean_signed_error']:+.2f} "
            f">5ppm={m['pct_gt5']:.1f}% >10ppm={m['pct_gt10']:.1f}% "
            f"exact(<=0.05)={m['pct_within_0_05']:.1f}%")


def write_tables_md(results):
    lines = ["# CSP5 vs ACD 13C comparison -- full tables", ""]

    lines.append("## Comparison A (COCONUT sample, agreement only -- not accuracy)")
    lines.append("")
    lines.append(f"Overall: {fmt_metrics(results['A']['overall'])}")
    lines.append("")
    lines.append("By carbon class:")
    for cls, m in results["A"]["by_carbon_class"].items():
        lines.append(f"- {cls}: {fmt_metrics(m)}")
    lines.append("")
    lines.append("By size bin:")
    for sb, m in results["A"]["by_size_bin"].items():
        lines.append(f"- {sb}: {fmt_metrics(m)}")
    lines.append("")
    lines.append("Top disagreement cells (carbon_class x size_bin, n>=200, sorted by |mean signed diff|):")
    for cell in results["A"]["top_disagreement_cells"]:
        lines.append(f"- {cell['carbon_class']} / {cell['size_bin']}: n={cell['n']} "
                      f"mean_signed_diff={cell['mean_signed_diff']:+.2f}")
    lines.append("")

    lines.append("## Comparison B (referee vs experiment)")
    lines.append("")
    for name, agg in results["B"]["by_predictor"].items():
        lines.append(f"### {name}")
        lines.append(f"Overall: {fmt_metrics(agg['overall'])}")
        lines.append("By carbon class: " + "; ".join(
            f"{cls}: {fmt_metrics(m)}" for cls, m in agg["by_carbon_class"].items()))
        lines.append("By size bin: " + "; ".join(
            f"{sb}: {fmt_metrics(m)}" for sb, m in agg["by_size_bin"].items()))
        lines.append("By solvent: " + "; ".join(
            f"{sv}: {fmt_metrics(m)}" for sv, m in agg["by_solvent"].items()))
        lines.append("")
    lines.append("### ACD leakage strata (molecule-level ACD-exactness vs experiment)")
    for stratum, data in results["B"]["acd_exactness_strata"].items():
        lines.append(f"- stratum {stratum} (n_molecules={data['n_molecules']}): "
                      f"ACD-union {fmt_metrics(data['ACD-union'])} | "
                      f"CSP5 {fmt_metrics(data['CSP5'])} | HOSE {fmt_metrics(data['HOSE'])}")
    lines.append("")
    lines.append(f"Sanity gates: {results['B']['sanity_gates']}")
    lines.append("")

    lines.append("## Comparison C (triple overlap: CSP5, ACD-union, HOSE, experiment)")
    lines.append(f"n_carbons={results['C']['n_carbons']} n_molecules={results['C']['n_molecules']}")
    for name, m in results["C"]["overall"].items():
        lines.append(f"- {name}: {fmt_metrics(m)}")
    lines.append("")
    lines.append("By carbon class:")
    for cls, preds in results["C"]["by_carbon_class"].items():
        lines.append(f"- {cls}: " + "; ".join(f"{n}: {fmt_metrics(m)}" for n, m in preds.items()))
    lines.append("")
    lines.append("By size bin:")
    for sb, preds in results["C"]["by_size_bin"].items():
        lines.append(f"- {sb}: " + "; ".join(f"{n}: {fmt_metrics(m)}" for n, m in preds.items()))
    lines.append("")
    lines.append("By ACD-exactness stratum:")
    for stratum, preds in results["C"]["by_acd_exactness_stratum"].items():
        lines.append(f"- {stratum} (n_carbons={preds['n_carbons']}): " + "; ".join(
            f"{n}: {fmt_metrics(m)}" for n, m in preds.items() if n != "n_carbons"))
    lines.append("")
    lines.append("Bootstrap 95% CIs (resampling molecules), MAE(CSP5) - MAE(other):")
    for label, data in results["C"]["bootstrap"].items():
        lines.append(f"- {label}: n_carbons={data['n_carbons']}")
        for key in ("MAE_CSP5_minus_MAE_ACD", "MAE_CSP5_minus_MAE_HOSE"):
            ci = data[key]
            if ci:
                lines.append(f"    {key}: point={ci['point']:+.3f} "
                              f"CI=[{ci['ci_lo']:+.3f}, {ci['ci_hi']:+.3f}] (n_boot={ci['n_boot']})")
            else:
                lines.append(f"    {key}: n/a")
    lines.append("")

    (config.RESULTS_DIR / "tables.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
