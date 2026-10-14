#!/usr/bin/env python3
"""CSP5 prediction runner for the CSP5-vs-ACD comparison (quick task 261013-knr). csp5 venv.

Subcommands:
  shard  --input INPUT.sdf --out runs/NAME   size-sorted round-robin sharding into N_WORKERS shards
  work   --out runs/NAME --shard NN          predict one shard, chunk by chunk (resumable)
  launch --out runs/NAME                     start one detached `work` process per shard
  check  --out runs/NAME                     recount outputs against the manifest; write ALL_DONE

Traps handled here (see RESEARCH.md / PLAN.md <traps>, plus the 2026-10-14 deviation below):
1. ID tracking only via `extra_cols={"rid": ...}` / the `rid` SD field, never via molecule_id
   or output position (`predict_mols` drops failures and re-numbers molecule_id).
2. Shards are size-sorted then dealt round-robin, not striped, so no single worker gets all
   the giant molecules -- then shuffled within each shard (deviation below) so a worker's
   *processing order* also mixes sizes, not just its overall shard membership.
3. Each embed+predict+write step is scoped to one CHUNK of molecules
   (`shard_NN.chunk_MMMM.{tsv.gz,fail.tsv,done}`), not a whole shard, and a chunk's `.done` is
   written only after its output files are flushed and closed. The shard-level `shard_NN.done`
   is written only once every chunk is done. `ALL_DONE` is written only by `check`, which
   re-counts rows from every chunk's output files and verifies the count against the input
   manifest. Downstream steps check the count, not just the marker's existence.
4. Embedding happens per molecule in a try/except via `common.embed_mol_with_timeout`, with a
   bounded wall-clock timeout per attempt (see deviation below) -- never
   `predict_molecule_file(..., regenerate_geometry=True)`, which aborts the whole file on one
   failure, and never RDKit's untimed ETKDG default.

Deviation (2026-10-14, recorded in the SUMMARY): the original version of this script used
`csp5._runtime.cascade_core.embed_mol_conformers_canonical`, which calls RDKit's ETKDGv3 with
`timeout=0` (no limit) and up to 20 embed attempts, the later ones with random starting
coordinates. On the first production run, all 6-7 workers stalled on their first (largest)
molecule for 3h44m with zero output -- large fused/macrocyclic COCONUT natural products
(150-200 heavy atoms, >10 rings) can make ETKDG's random-coordinate retry hang indefinitely.
Fixed by `common.embed_mol_with_timeout` (per-attempt wall-clock timeout, calibrated
empirically against this exact molecule), by chunking `work` so failures/progress are visible
long before a whole shard finishes, and by shuffling each shard's processing order so a worker
does not spend its first N chunks entirely on giants. Worker count lowered 7 -> 6
(`config.N_WORKERS`) because the Mac has 4 performance + 4 efficiency cores and other jobs
share it.
"""
import argparse
import gzip
import json
import math
import os
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import common  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")


def iter_records(path, encoding="latin-1"):
    buf = []
    with open(path, encoding=encoding) as fh:
        for line in fh:
            if line.startswith("$$$$"):
                yield "".join(buf)
                buf = []
            else:
                buf.append(line)
    if buf and "".join(buf).strip():
        yield "".join(buf)


def cmd_shard(args):
    inp = Path(args.input)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    sized = []  # (n_heavy, record_text)
    n_parse_fail = 0
    for rec in iter_records(inp):
        molblock = rec.split("M  END")[0] + "M  END\n"
        m = Chem.MolFromMolBlock(molblock, sanitize=False)
        if m is None:
            n_parse_fail += 1
            n_heavy = 0
        else:
            n_heavy = m.GetNumHeavyAtoms()
        sized.append((n_heavy, rec))

    sized.sort(key=lambda t: -t[0])
    n_shards = config.N_WORKERS
    shards = [[] for _ in range(n_shards)]
    for i, (_, rec) in enumerate(sized):
        shards[i % n_shards].append(rec)

    # Round-robin dealing above balances each worker's share of every size class (trap 2),
    # but a sorted-then-strided split still leaves each shard's *own* records in descending
    # size order (every worker's first chunk would be all giants). Shuffle within each shard
    # (seeded, reproducible) so processing order mixes sizes too.
    for i, shard_recs in enumerate(shards):
        random.Random(config.SEED + i).shuffle(shard_recs)

    for i, shard_recs in enumerate(shards):
        p = out / f"shard_{i:02d}.sdf"
        with open(p, "w", encoding="latin-1") as fh:
            for rec in shard_recs:
                fh.write(rec)
                fh.write("$$$$\n")

    manifest = {
        "input": str(inp),
        "n_records": len(sized),
        "n_parse_fail_sizing": n_parse_fail,
        "n_shards": n_shards,
        "chunk_size": config.CHUNK_SIZE,
    }
    json.dump(manifest, open(out / "manifest.json", "w"), indent=2)
    print(f"sharded {len(sized)} records into {n_shards} shards (chunk size {config.CHUNK_SIZE}) "
          f"under {out} (parse failures at sizing time: {n_parse_fail})")


def cmd_work(args):
    out = Path(args.out)
    nn = args.shard
    manifest = json.load(open(out / "manifest.json"))
    chunk_size = int(manifest.get("chunk_size", config.CHUNK_SIZE))

    shard_done_path = out / f"shard_{nn:02d}.done"
    if shard_done_path.exists():
        print(f"shard {nn:02d} already done, skipping")
        return

    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    import torch
    torch.set_num_threads(1)
    from csp5 import predict_mols

    shard_path = out / f"shard_{nn:02d}.sdf"

    # Load every record once (fast; no embedding yet). Fixed file position -> fixed chunk
    # index, so chunking is deterministic across restarts (needed for the resumability
    # invariant: a chunk with a `.done` file is skipped, never re-processed).
    loaded = []  # (rid, mol_or_None)
    sup = Chem.ForwardSDMolSupplier(str(shard_path), removeHs=False)
    for pos, m in enumerate(sup):
        if m is None:
            loaded.append((f"_parsefail_{nn:02d}_{pos}", None))
        else:
            rid = m.GetProp("rid") if m.HasProp("rid") else m.GetProp("SMILES_ID")
            loaded.append((rid, m))

    n_chunks = math.ceil(len(loaded) / chunk_size) if loaded else 0
    totals = {"n_in": len(loaded), "n_ok": 0, "n_fail": 0}

    for chunk_idx in range(n_chunks):
        chunk_done_path = out / f"shard_{nn:02d}.chunk_{chunk_idx:04d}.done"
        if chunk_done_path.exists():
            d = json.load(open(chunk_done_path))
            totals["n_ok"] += d["n_ok"]
            totals["n_fail"] += d["n_fail"]
            continue

        t_chunk_start = time.perf_counter()
        chunk = loaded[chunk_idx * chunk_size:(chunk_idx + 1) * chunk_size]

        embedded_mols, embedded_ids = [], []
        fail_rows = []
        orig_by_rid = {}
        for rid, m in chunk:
            if m is None:
                fail_rows.append((rid, "parse", "rdkit_mol_from_molblock_none"))
                continue
            orig_by_rid[rid] = m
            try:
                embedded, _dt = common.embed_mol_with_timeout(m)
                embedded_mols.append(embedded)
                embedded_ids.append(rid)
            except Exception as e:  # noqa: BLE001 - embedding fails for many chemistry reasons
                fail_rows.append((rid, "embed", str(e)[:200]))

        n_ok_chunk = 0
        tsv_rows = []
        n_csp5_failure_strings = 0
        if embedded_mols:
            res = predict_mols(embedded_mols, nucleus="13C", batch_size=64,
                                extra_cols={"rid": embedded_ids})
            n_csp5_failure_strings += len(res.failures)
            preds_by_rid = {}
            if len(res.predictions):
                for rid, grp in res.predictions.groupby("rid"):
                    preds_by_rid[rid] = grp
            for rid in embedded_ids:
                grp = preds_by_rid.get(rid)
                if grp is None:
                    fail_rows.append((rid, "predict", "dropped_by_csp5"))
                    continue
                idx_set = set(grp["atom_index"].astype(int))
                if not common.self_check(orig_by_rid[rid], idx_set):
                    fail_rows.append((rid, "self_check", "indices_not_subset_of_carbons"))
                    continue
                n_ok_chunk += 1
                for atom_idx, shift in zip(grp["atom_index"].astype(int), grp["shift_ppm"]):
                    tsv_rows.append((rid, int(atom_idx), float(shift)))

        tsv_path = out / f"shard_{nn:02d}.chunk_{chunk_idx:04d}.tsv.gz"
        fail_path = out / f"shard_{nn:02d}.chunk_{chunk_idx:04d}.fail.tsv"
        with gzip.open(tsv_path, "wt") as fh:
            fh.write("rid\tatom_idx0\tcsp5_ppm\n")
            for rid, atom_idx, shift in tsv_rows:
                fh.write(f"{rid}\t{atom_idx}\t{shift}\n")
        with open(fail_path, "w") as fh:
            fh.write("rid\tstage\treason\n")
            for rid, stage, reason in fail_rows:
                fh.write(f"{rid}\t{stage}\t{reason}\n")

        n_fail_chunk = len(fail_rows)
        chunk_elapsed = time.perf_counter() - t_chunk_start
        json.dump({"n_in": len(chunk), "n_ok": n_ok_chunk, "n_fail": n_fail_chunk,
                   "seconds": round(chunk_elapsed, 1),
                   "csp5_failure_strings_seen": n_csp5_failure_strings},
                  open(chunk_done_path, "w"))
        totals["n_ok"] += n_ok_chunk
        totals["n_fail"] += n_fail_chunk
        print(f"shard {nn:02d} chunk {chunk_idx:04d}/{max(0, n_chunks - 1):04d}: "
              f"n={len(chunk)} ok={n_ok_chunk} fail={n_fail_chunk} {chunk_elapsed:.1f}s",
              flush=True)

    json.dump(totals, open(shard_done_path, "w"), indent=2)
    print(f"shard {nn:02d} ALL CHUNKS DONE: {totals}")


def cmd_launch(args):
    out = Path(args.out)
    manifest = json.load(open(out / "manifest.json"))
    n_shards = manifest["n_shards"]
    script = Path(__file__).resolve()
    pids = []
    for i in range(n_shards):
        done_path = out / f"shard_{i:02d}.done"
        if done_path.exists():
            print(f"shard {i:02d} already done, not launching")
            continue
        log_path = out / f"shard_{i:02d}.log"
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = "1"
        env["MKL_NUM_THREADS"] = "1"
        with open(log_path, "a") as logf:
            p = subprocess.Popen(
                [sys.executable, str(script), "work", "--out", str(out), "--shard", str(i)],
                stdout=logf, stderr=subprocess.STDOUT, env=env, start_new_session=True,
            )
        pids.append(p.pid)
    print(f"launched {len(pids)} workers for {out}: pids {pids}")


def cmd_check(args):
    out = Path(args.out)
    manifest = json.load(open(out / "manifest.json"))
    n_shards = manifest["n_shards"]
    n_expected = manifest["n_records"]

    missing_shards = [i for i in range(n_shards) if not (out / f"shard_{i:02d}.done").exists()]
    for i in range(n_shards):
        n_chunk_done = len(list(out.glob(f"shard_{i:02d}.chunk_*.done")))
        status = "DONE" if i not in missing_shards else f"{n_chunk_done} chunk(s) done"
        print(f"  shard {i:02d}: {status}")
    if missing_shards:
        print(f"missing .done for shards: {missing_shards}")
        sys.exit(1)

    ok_rids, fail_rids = set(), set()
    for tsv_path in sorted(out.glob("shard_*.chunk_*.tsv.gz")):
        with gzip.open(tsv_path, "rt") as fh:
            next(fh, None)
            for line in fh:
                ok_rids.add(line.split("\t", 1)[0])
    for fail_path in sorted(out.glob("shard_*.chunk_*.fail.tsv")):
        with open(fail_path) as fh:
            next(fh, None)
            for line in fh:
                fail_rids.add(line.split("\t", 1)[0])

    n_recount = len(ok_rids | fail_rids)
    if n_recount != n_expected:
        print(f"count mismatch: expected {n_expected}, recounted {n_recount} "
              f"(ok_rids={len(ok_rids)} fail_rids={len(fail_rids)}, overlap "
              f"{len(ok_rids & fail_rids)})")
        sys.exit(1)

    result = {"n_expected": n_expected, "n_ok_rids": len(ok_rids), "n_fail_rids": len(fail_rids)}
    (out / "ALL_DONE").write_text(json.dumps(result))
    print(f"ALL_DONE: {result}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("shard")
    sp.add_argument("--input", required=True)
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_shard)

    sp = sub.add_parser("work")
    sp.add_argument("--out", required=True)
    sp.add_argument("--shard", required=True, type=int)
    sp.set_defaults(func=cmd_work)

    sp = sub.add_parser("launch")
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_launch)

    sp = sub.add_parser("check")
    sp.add_argument("--out", required=True)
    sp.set_defaults(func=cmd_check)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
