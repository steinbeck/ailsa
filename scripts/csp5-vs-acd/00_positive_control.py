#!/usr/bin/env python3
"""Positive control for the CSP5-vs-ACD comparison (quick task 261013-knr). Run FIRST.

Reproduces the measured CSP5 accuracy on molecules the shipped CSP5-13C model never trained
on (scaffold-DOI test split of Exp22K). If this fails, no later referee number in this task is
trustworthy -- stop and report instead of continuing.

csp5 venv only (`.venv-csp5/bin/python`). Ported from
`~/Dropbox/develop/data/csp5-vs-acd/scripts/which_split.py` (verified in RESEARCH.md).
No compound identities or ACD values are involved; this script only touches the public,
MIT-licensed Exp22K/CSP5 split data.
"""
import ast
import json
import pickle
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import common  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")
from csp5 import predict_mols  # noqa: E402
from csp5._runtime import cascade_core as core  # noqa: E402

Z = config.ZENODO_DIR

LO, HI = 0.45, 0.80  # ppm; expected scaffold-DOI test MAE range (RESEARCH.md measured 0.58-0.64)
N_SAMPLE = 250
SPLIT_SEED = 7
N_EMBED_COMPARISON = 100  # molecules; keeps runtime bounded even at worst-case timeouts
MAX_EMBED_DELTA = 0.05  # ppm; required agreement between csp5's embedder and ours


def roles(split_name):
    s = json.load(open(Z / f"splits/CSP5-13C-{split_name}_split.json"))["splits"]
    r = {}
    for k in ("train", "val", "test"):
        for i in s[k]:
            r[i] = k
    return r


def mae_for(entries, indices, label):
    if not indices:
        print(f"{label:55s} empty pool, skipped")
        return None, None
    rng = random.Random(SPLIT_SEED)
    pick = rng.sample(indices, min(N_SAMPLE, len(indices)))
    mols, ids = [], []
    for i in pick:
        m = Chem.MolFromMolBlock(entries[i]["mol_block"], removeHs=False)
        if m is not None:
            mols.append(m)
            ids.append(i)
    res = predict_mols(mols, nucleus="13C", batch_size=64, extra_cols={"eid": ids})
    err = []
    for eid, grp in res.predictions.groupby("eid"):
        ex = entries[eid]["exp_shift_dict"]
        ex = ast.literal_eval(ex) if isinstance(ex, str) else ex
        p = dict(zip(grp["atom_index"].astype(int), grp["shift_ppm"]))
        err += [abs(p[k] - v) for k, v in ex.items() if k in p]
    mae = statistics.mean(err)
    median = statistics.median(err)
    print(f"{label:55s} pool={len(indices):5d} mols={len(ids)} atoms={len(err)} "
          f"MAE={mae:.3f} median={median:.3f}")
    return mae, median


def embedding_comparison(entries, indices, label, n=N_EMBED_COMPARISON):
    """Strip Exp22K's built-in (DFT) 3D geometry and re-embed from scratch with (a) csp5's own
    `embed_mol_conformers_canonical` and (b) `common.embed_mol_with_timeout`, then compare
    downstream CSP5 accuracy against experiment for both. This is the real embedder-swap check:
    `mae_for` above never exercises any embedding code, csp5's or ours, because Exp22K's
    `mol_block` already carries DFT-optimized 3D coordinates and `predict_mols` uses whatever
    conformer it is given -- confirmed by inspection (api.py's `predict_mols` has no embedding
    call on the direct-mol path) and empirically (z-coordinates in entry 0's mol_block span
    -3.09..3.27 A, not all-zero as a 2D depiction would be).
    """
    rng = random.Random(SPLIT_SEED)
    pick = rng.sample(indices, min(n, len(indices)))

    def run(embed_fn, method_label):
        mols, ids, embed_fail = [], [], 0
        for i in pick:
            m = Chem.MolFromMolBlock(entries[i]["mol_block"], removeHs=False)
            if m is None:
                continue
            m.RemoveAllConformers()
            try:
                embedded = embed_fn(m)
            except Exception as e:  # noqa: BLE001
                embed_fail += 1
                print(f"    [{method_label}] embed failure on eid={i}: {str(e)[:120]}")
                continue
            mols.append(embedded)
            ids.append(i)
        if not mols:
            print(f"  [{label}] {method_label}: no molecules embedded, skipped")
            return None
        res = predict_mols(mols, nucleus="13C", batch_size=64, extra_cols={"eid": ids})
        err = []
        for eid, grp in res.predictions.groupby("eid"):
            ex = entries[eid]["exp_shift_dict"]
            ex = ast.literal_eval(ex) if isinstance(ex, str) else ex
            p = dict(zip(grp["atom_index"].astype(int), grp["shift_ppm"]))
            err += [abs(p[k] - v) for k, v in ex.items() if k in p]
        mae = statistics.mean(err) if err else None
        print(f"  [{label}] {method_label}: mols={len(ids)} embed_fail={embed_fail} "
              f"atoms={len(err)} MAE={mae}")
        return mae

    mae_csp5 = run(
        lambda m: core.embed_mol_conformers_canonical(
            m, max_embed_tries=20, num_conformers=1, prune_rms_thresh=0.0, ff_max_iters=200
        )[0]["mol"],
        "csp5 own embedder (embed_mol_conformers_canonical)",
    )
    mae_ours = run(lambda m: common.embed_mol_with_timeout(m)[0], "our timeout-guarded embedder")

    if mae_csp5 is not None and mae_ours is not None:
        delta = abs(mae_csp5 - mae_ours)
        print(f"  [{label}] |MAE(ours) - MAE(csp5 own)| = {delta:.3f} ppm "
              f"(must be <= {MAX_EMBED_DELTA})")
        return mae_csp5, mae_ours, delta
    return mae_csp5, mae_ours, None


def implicit_h_embedding_check(entries, indices, label, n=N_EMBED_COMPARISON):
    """Strip Exp22K's hydrogens down to IMPLICIT form (matching COCONUT/NMRShiftDB2's own
    molblock convention) before re-embedding, and check `common.embed_mol_with_timeout`
    against csp5's own embedder on that basis.

    Deviation (2026-10-14): the embedder-swap check above missed a real bug because Exp22K's
    `mol_block` already carries EXPLICIT hydrogens (confirmed: entry 0 has 40 atoms vs 16 heavy
    atoms) -- it never exercised the implicit-H path at all. `common.embed_mol_with_timeout`
    originally embedded molecules AS GIVEN, without calling `Chem.AddHs()` first; on an
    implicit-H input (COCONUT, NMRShiftDB2) this places 3D coordinates for the heavy-atom
    skeleton only, leaving CSP5's geometry-based GNN blind to hydrogen positions -- which
    corrupted the first production run (referee MAE ~25-28 ppm). Fixed by adding `Chem.AddHs`
    inside `embed_mol_with_timeout` (it appends new H atoms after the existing ones without
    reordering, so heavy-atom indices are unaffected). This check makes the implicit-H path a
    permanent, first-class part of the positive control so the gap cannot reopen silently.
    """
    rng = random.Random(SPLIT_SEED)
    pick = rng.sample(indices, min(n, len(indices)))

    def to_implicit_h(mol):
        tagged = Chem.Mol(mol)
        for a in tagged.GetAtoms():
            a.SetIntProp("orig_idx", a.GetIdx())
        stripped = Chem.RemoveHs(tagged)
        idx_map = {a.GetIdx(): a.GetIntProp("orig_idx") for a in stripped.GetAtoms()}
        return stripped, idx_map

    def run(embed_fn, method_label):
        mols, ids, idx_maps, embed_fail = [], [], {}, 0
        for i in pick:
            m = Chem.MolFromMolBlock(entries[i]["mol_block"], removeHs=False)
            if m is None:
                continue
            m.RemoveAllConformers()
            implicit_m, idx_map = to_implicit_h(m)
            if implicit_m.GetNumAtoms() == m.GetNumAtoms():
                continue  # nothing to strip; not a useful test case for this check
            try:
                embedded = embed_fn(implicit_m)
            except Exception as e:  # noqa: BLE001
                embed_fail += 1
                print(f"    [{method_label}] embed failure on eid={i}: {str(e)[:120]}")
                continue
            mols.append(embedded)
            ids.append(i)
            idx_maps[i] = idx_map
        if not mols:
            print(f"  [{label}] {method_label}: no molecules embedded, skipped")
            return None
        res = predict_mols(mols, nucleus="13C", batch_size=64, extra_cols={"eid": ids})
        err = []
        for eid, grp in res.predictions.groupby("eid"):
            ex = entries[eid]["exp_shift_dict"]
            ex = ast.literal_eval(ex) if isinstance(ex, str) else ex
            idx_map = idx_maps[eid]
            p = {idx_map[int(stripped_idx)]: shift
                 for stripped_idx, shift in zip(grp["atom_index"], grp["shift_ppm"])}
            err += [abs(p[k] - v) for k, v in ex.items() if k in p]
        mae = statistics.mean(err) if err else None
        print(f"  [{label}] {method_label}: mols={len(ids)} embed_fail={embed_fail} "
              f"atoms={len(err)} MAE={mae}")
        return mae

    mae_csp5 = run(
        lambda m: core.embed_mol_conformers_canonical(
            m, max_embed_tries=20, num_conformers=1, prune_rms_thresh=0.0, ff_max_iters=200
        )[0]["mol"],
        "csp5 own embedder (implicit-H input)",
    )
    mae_ours = run(lambda m: common.embed_mol_with_timeout(m)[0],
                   "our timeout-guarded embedder (implicit-H input)")

    if mae_csp5 is not None and mae_ours is not None:
        delta = abs(mae_csp5 - mae_ours)
        print(f"  [{label}] |MAE(ours) - MAE(csp5 own)| on implicit-H input = {delta:.3f} ppm "
              f"(must be <= {MAX_EMBED_DELTA})")
        return mae_csp5, mae_ours, delta
    return mae_csp5, mae_ours, None


def main():
    entries = pickle.load(open(Z / "assigned/Exp22K_13C_entries.pkl", "rb"))
    scaffold_roles = roles("scaffold-doi")
    random_roles = roles("random")

    unseen_both = [i for i in range(len(entries))
                   if scaffold_roles.get(i) == "test" and random_roles.get(i) == "test"]
    scaffold_test = [i for i, role in scaffold_roles.items() if role == "test"]
    scaffold_train = [i for i, role in scaffold_roles.items() if role == "train"]

    mae_for(entries, scaffold_train, "scaffold-DOI train (sanity: should be well below test)")
    mae_for(entries, unseen_both, "B unseen by both splits (scaffold-test and random-test)")
    mae_scaffold, median_scaffold = mae_for(entries, scaffold_test, "scaffold-DOI test overall")

    print(f"\nscaffold-DOI test MAE = {mae_scaffold:.3f} ppm (expected {LO:.2f}-{HI:.2f})")
    if mae_scaffold is None or not (LO <= mae_scaffold <= HI):
        print("POSITIVE CONTROL FAILED: scaffold-DOI test MAE is outside the expected range. "
              "No referee or COCONUT-sample number in this task is trustworthy until this is "
              "understood. STOP.", file=sys.stderr)
        sys.exit(1)
    print("POSITIVE CONTROL (prediction network) PASSED.")

    print(f"\nEmbedder-swap check (strips Exp22K's DFT geometry, re-embeds from scratch; "
          f"n<={N_EMBED_COMPARISON} molecules per method):")
    mae_csp5_embed, mae_ours_embed, delta = embedding_comparison(
        entries, scaffold_test, "scaffold-DOI test, re-embedded"
    )
    if delta is None or mae_csp5_embed is None or mae_ours_embed is None:
        print("POSITIVE CONTROL FAILED: embedder-swap comparison could not be computed "
              "(no molecules embedded by one or both methods). STOP.", file=sys.stderr)
        sys.exit(1)
    if not (LO <= mae_csp5_embed <= HI and LO <= mae_ours_embed <= HI):
        print(f"POSITIVE CONTROL FAILED: re-embedded MAE outside {LO:.2f}-{HI:.2f} ppm "
              f"(csp5 own={mae_csp5_embed:.3f}, ours={mae_ours_embed:.3f}). STOP.",
              file=sys.stderr)
        sys.exit(1)
    if delta > MAX_EMBED_DELTA:
        print(f"POSITIVE CONTROL FAILED: our embedder's MAE differs from csp5's own embedder "
              f"by {delta:.3f} ppm (> {MAX_EMBED_DELTA}). STOP -- do not trust the COCONUT/"
              f"referee CSP5 run with this embedder.", file=sys.stderr)
        sys.exit(1)
    print(f"Embedder-swap check PASSED: csp5 own embedder MAE={mae_csp5_embed:.3f} ppm, "
          f"our timeout-guarded embedder MAE={mae_ours_embed:.3f} ppm, "
          f"delta={delta:.3f} ppm (<= {MAX_EMBED_DELTA}).")

    print(f"\nImplicit-H embedding check (strips to implicit H, matching COCONUT/NMRShiftDB2's "
          f"own convention; n<={N_EMBED_COMPARISON} molecules per method):")
    mae_csp5_ih, mae_ours_ih, delta_ih = implicit_h_embedding_check(
        entries, scaffold_test, "scaffold-DOI test, implicit-H re-embedded"
    )
    if delta_ih is None or mae_csp5_ih is None or mae_ours_ih is None:
        print("POSITIVE CONTROL FAILED: implicit-H embedding check could not be computed. "
              "STOP.", file=sys.stderr)
        sys.exit(1)
    if not (LO <= mae_csp5_ih <= HI and LO <= mae_ours_ih <= HI):
        print(f"POSITIVE CONTROL FAILED: implicit-H re-embedded MAE outside {LO:.2f}-{HI:.2f} "
              f"ppm (csp5 own={mae_csp5_ih:.3f}, ours={mae_ours_ih:.3f}). This is exactly the "
              f"failure mode that corrupted the first production run -- STOP.", file=sys.stderr)
        sys.exit(1)
    if delta_ih > MAX_EMBED_DELTA:
        print(f"POSITIVE CONTROL FAILED: on implicit-H input, our embedder's MAE differs from "
              f"csp5's own embedder by {delta_ih:.3f} ppm (> {MAX_EMBED_DELTA}). STOP.",
              file=sys.stderr)
        sys.exit(1)
    print(f"Implicit-H embedding check PASSED: csp5 own embedder MAE={mae_csp5_ih:.3f} ppm, "
          f"our timeout-guarded embedder MAE={mae_ours_ih:.3f} ppm, "
          f"delta={delta_ih:.3f} ppm (<= {MAX_EMBED_DELTA}).")
    print("POSITIVE CONTROL PASSED.")


if __name__ == "__main__":
    main()
