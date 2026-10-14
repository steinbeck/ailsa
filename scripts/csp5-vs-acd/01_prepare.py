#!/usr/bin/env python3
"""Data preparation for the CSP5-vs-ACD comparison (quick task 261013-knr). csp5 venv.

Produces, under SCRATCH/inputs/ (never committed, outside the repo):
- coconut_sample_ids.json : the ~20,000 chosen CNP record IDs (one per base ID, seed-sampled)
- coconut_sample.sdf      : those ACD COCONUT records, copied verbatim (NMREDATA_ASSIGNMENT intact)
- coconut_referee_match.sdf : COCONUT records whose full InChIKey matches a referee molecule
- referee.sdf             : the 12,643 strict-referee NMRShiftDB2 records, with derived fields
                            rid, inchikey, exp13c, exp_solvent, acd_nsdb13c (where present)

Ported from the verified research scripts (not re-derived):
`~/Dropbox/develop/data/csp5-vs-acd/scripts/{overlap.py,acd_exact.py,nsdb_rule.py}`.

Records are copied by raw text, never reconstructed through RDKit, so every original SD field
(including NMREDATA_ASSIGNMENT / CNMR_SHIFTS / Spectrum 13C N / Program) survives intact.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402
import common  # noqa: E402

from rdkit import Chem, RDLogger  # noqa: E402

RDLogger.DisableLog("rdApp.*")

EXPECTED_REFEREE_MATCHES = 1996  # RESEARCH.md measured number; stop if we deviate by >10%


def iter_records(path, encoding="latin-1"):
    """Yield each SD record's raw text (molblock + field blocks), without the '$$$$' line."""
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


def append_field(rec_text, name, value):
    """Append one SD field block ('> <NAME>\\nvalue\\n\\n') to a record's raw text."""
    if not rec_text.endswith("\n"):
        rec_text += "\n"
    return rec_text + f"> <{name}>\n{value}\n\n"


# ---------------------------------------------------------------------------
# Step 1: sample 20,000 COCONUT base IDs (one record per base ID)
# ---------------------------------------------------------------------------

def build_sample_ids():
    keys_list = json.load(open(config.COCONUT_KEYS))  # [[cid, inchikey_or_null], ...], file order
    groups = defaultdict(list)
    for cid, key in keys_list:
        if key is None:
            continue
        base = cid.split(".")[0]
        groups[base].append(cid)

    rng = random.Random(config.SEED)
    base_ids_sorted = sorted(groups.keys())
    chosen_record = {}
    for base in base_ids_sorted:
        recs = sorted(groups[base])
        chosen_record[base] = rng.choice(recs)

    n_sample = min(config.SAMPLE_N, len(base_ids_sorted))
    sampled_bases = rng.sample(base_ids_sorted, n_sample)
    chosen_cids = sorted(chosen_record[b] for b in sampled_bases)

    print(f"COCONUT base IDs (non-null key): {len(base_ids_sorted)}, sampled: {len(chosen_cids)}")
    config.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json.dump(chosen_cids, open(config.INPUTS_DIR / "coconut_sample_ids.json", "w"))
    return set(chosen_cids)


# ---------------------------------------------------------------------------
# Step 2: referee extraction from NSDB_SDF
# ---------------------------------------------------------------------------

def build_referee():
    referee_ids = set(json.load(open(config.REFEREE_IDS)))
    out_path = config.INPUTS_DIR / "referee.sdf"
    n_found = n_with_exp = n_with_acd = n_parse_fail = 0
    referee_inchikeys = set()

    with open(out_path, "w", encoding="latin-1") as out_fh:
        for rec in iter_records(config.NSDB_SDF):
            fields = common.parse_sd_fields(rec)
            rid = fields.get("nmrshiftdb2 ID", "").strip()
            if not rid or rid not in referee_ids:
                continue
            n_found += 1

            prog = common.nsdb_program(fields)
            solv = common.nsdb_solvent(fields)

            exp_keys = sorted(
                int(k.split()[-1]) for k in fields
                if k.startswith("Spectrum 13C ") and int(k.split()[-1]) not in prog
            )
            acd_keys = sorted(
                int(k.split()[-1]) for k in fields
                if k.startswith("Spectrum 13C ") and "ACD" in prog.get(int(k.split()[-1]), "")
            )
            if not exp_keys:
                continue
            n_with_exp += 1

            exp_k = exp_keys[0]
            exp_spec_text = fields[f"Spectrum 13C {exp_k}"]
            exp_solvent = solv.get(exp_k, "")

            acd_text = None
            if acd_keys:
                n_with_acd += 1
                acd_k = acd_keys[0]
                acd_text = fields[f"Spectrum 13C {acd_k}"]

            molblock = rec.split("M  END")[0] + "M  END\n"
            # Deviation (2026-10-14): NMRShiftDB2's CDK-origin export mis-sets the MDL atom
            # valence field (see common.fix_nsdb_valence_field); must be fixed before RDKit
            # ever parses this text, downstream of here.
            molblock = common.fix_nsdb_valence_field(molblock)
            mol = Chem.MolFromMolBlock(molblock, removeHs=False)
            if mol is None:
                n_parse_fail += 1
                continue

            inchikey = fields.get("INChI key", "").strip()
            if inchikey:
                referee_inchikeys.add(inchikey)

            new_rec = molblock
            # keep the original field blocks too (Program/Solvent/Spectrum.../INChI key/etc.)
            for name, value in fields.items():
                new_rec = append_field(new_rec, name, value)
            new_rec = append_field(new_rec, "rid", rid)
            new_rec = append_field(new_rec, "inchikey", inchikey)
            new_rec = append_field(new_rec, "exp13c", exp_spec_text)
            new_rec = append_field(new_rec, "exp_solvent", exp_solvent)
            if acd_text is not None:
                new_rec = append_field(new_rec, "acd_nsdb13c", acd_text)
            out_fh.write(new_rec)
            out_fh.write("$$$$\n")

    print(f"referee IDs found: {n_found}, with experimental 13C: {n_with_exp}, "
          f"with hosted ACD spectrum: {n_with_acd}, molblock parse failures: {n_parse_fail}")
    return referee_inchikeys


# ---------------------------------------------------------------------------
# Step 3: one stream over ACD_SDF -> coconut_sample.sdf + coconut_referee_match.sdf
# ---------------------------------------------------------------------------

def build_coconut_files(sample_ids, referee_inchikeys):
    coconut_keys = json.load(open(config.COCONUT_KEYS))  # [[cid, key_or_null], ...], file order

    sample_path = config.INPUTS_DIR / "coconut_sample.sdf"
    referee_match_path = config.INPUTS_DIR / "coconut_referee_match.sdf"

    n_total = 0
    n_sample_written = 0
    n_referee_written = 0
    n_no_assignment = 0
    seen_referee_keys = set()

    with open(sample_path, "w", encoding="latin-1") as sample_fh, \
            open(referee_match_path, "w", encoding="latin-1") as referee_fh:
        for i, rec in enumerate(iter_records(config.ACD_SDF)):
            n_total += 1
            fields = common.parse_sd_fields(rec)
            cid = fields.get("SMILES_ID", "?").strip()
            if "NMREDATA_ASSIGNMENT" not in fields:
                n_no_assignment += 1

            expected_cid, key = coconut_keys[i] if i < len(coconut_keys) else (None, None)

            want_sample = cid in sample_ids
            want_referee = (
                key is not None and key in referee_inchikeys and key not in seen_referee_keys
            )

            if want_sample:
                sample_fh.write(rec)
                sample_fh.write("$$$$\n")
                n_sample_written += 1
            if want_referee:
                referee_fh.write(rec)
                referee_fh.write("$$$$\n")
                seen_referee_keys.add(key)
                n_referee_written += 1

    print(f"ACD_SDF records scanned: {n_total}, lacking NMREDATA_ASSIGNMENT: {n_no_assignment}")
    print(f"coconut_sample.sdf written: {n_sample_written} (expected ~{config.SAMPLE_N})")
    print(f"coconut_referee_match.sdf written: {n_referee_written} "
          f"(expected ~{EXPECTED_REFEREE_MATCHES})")

    deviation = abs(n_referee_written - EXPECTED_REFEREE_MATCHES) / EXPECTED_REFEREE_MATCHES
    if deviation > 0.10:
        print(f"ERROR: referee-match count deviates from the expected {EXPECTED_REFEREE_MATCHES} "
              f"by {deviation * 100:.1f}% (>10%). Stopping for investigation.", file=sys.stderr)
        sys.exit(1)

    sample_deviation = abs(n_sample_written - len(sample_ids)) / max(1, len(sample_ids))
    if sample_deviation > 0.10:
        print(f"ERROR: sample-written count ({n_sample_written}) deviates from the chosen sample "
              f"({len(sample_ids)}) by {sample_deviation * 100:.1f}% (>10%). Stopping.",
              file=sys.stderr)
        sys.exit(1)


def main():
    config.INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    sample_ids = build_sample_ids()
    referee_inchikeys = build_referee()
    build_coconut_files(sample_ids, referee_inchikeys)
    print("01_prepare.py done.")


if __name__ == "__main__":
    main()
