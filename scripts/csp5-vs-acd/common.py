"""Shared parsers, carbon classification and statistics for the CSP5-vs-ACD comparison.

Imports only rdkit + stdlib + numpy, so this module loads in both the csp5 venv and the
AILSA (/opt/miniconda3) environment. No ACD values, structures or IDs are hard-coded here.

Parsing logic is ported from the verified research scripts (not re-derived):
`~/Dropbox/develop/data/csp5-vs-acd/scripts/acd_exact.py`, `overlap.py`, `nsdb_idx.py`.
"""
import math
import random
import re
import statistics
import time
from collections import defaultdict

from rdkit import Chem
from rdkit.Chem import AllChem

try:
    import config
except ImportError:  # pragma: no cover - allow import without sys.path setup in some contexts
    config = None

# ---------------------------------------------------------------------------
# SD field / spectrum parsing (verified against nmrshiftdb2withsignals.sd and acd_coconut.sdf)
# ---------------------------------------------------------------------------

_SD_FIELD_PAT = re.compile(r"^> *<([^>]+)>\n(.*?)(?=\n\n|\n> *<|\Z)", re.S | re.M)
_KEYED_PAT = re.compile(r"(\d+):(.*?)(?=\s\d+:|$)")


def parse_sd_fields(text):
    """Parse an SD record's text (molblock + '> <NAME>' blocks) into {name: value}."""
    return {m.group(1): m.group(2).strip() for m in _SD_FIELD_PAT.finditer(text)}


def acd_assignment(mol):
    """NMREDATA_ASSIGNMENT: 'label, shift, atom_1based \\' per line -> {0-based idx: ppm}."""
    out = {}
    for ln in mol.GetProp("NMREDATA_ASSIGNMENT").splitlines():
        p = [x.strip() for x in ln.rstrip("\\ ").split(",")]
        if len(p) >= 3 and p[2]:
            out[int(p[2]) - 1] = float(p[1])
    return out


def nsdb_spectrum(s):
    """'shift;intensity+mult;atomidx|...' (0-based atom index) -> {0-based idx: ppm}."""
    out = {}
    for t in s.split("|"):
        p = t.split(";")
        if len(p) >= 3 and p[2].strip().isdigit():
            out[int(p[2])] = float(p[0])
    return out


def _parse_keyed(s):
    """'0:FOO 1:BAR ...' -> {int key: value string}."""
    return {int(m.group(1)): m.group(2) for m in _KEYED_PAT.finditer(s)}


def nsdb_program(fields):
    """fields['Program'] -> {spectrum ordinal k: program string}."""
    return _parse_keyed(fields.get("Program", ""))


def nsdb_solvent(fields):
    """fields['Solvent'] -> {spectrum ordinal k: solvent string}."""
    return _parse_keyed(fields.get("Solvent", ""))


def fix_nsdb_valence_field(molblock_text):
    """Zero out the MDL atom-block 'valence' field (0-indexed columns [49:52]) in every atom
    line of an NMRShiftDB2 molblock.

    Deviation (2026-10-14, found investigating a referee CSP5 MAE of ~25-28 ppm): NMRShiftDB2's
    CDK-origin SD export (`nmrshiftdb2withsignals.sd`) writes each atom's CURRENT explicit
    bond-order sum into this field instead of leaving it at the MDL default of 0 ("no valence
    constraint -- use the standard valence model"). RDKit honours the field strictly, so every
    atom whose degree is below its standard valence gets `noImplicit=True` and ZERO implicit
    hydrogens -- even a plain sp3 CH2/CH3 carbon. Confirmed empirically on referee rid 234
    (warburganal): before this fix every atom showed `GetTotalNumHs() == 0`; after, the SMILES
    is the sane `CC1(C)CCC[C@@]2(C)C1CC=C(C=O)[C@]2(O)C=O`. Must be applied to the RAW molblock
    text before RDKit ever parses it (patching the parsed Mol after the fact does not reliably
    trigger RDKit to recompute implicit H counts). COCONUT molblocks (a different, ACD-origin
    pipeline) do not carry this quirk -- confirmed by inspection -- so this function is only
    used for NMRShiftDB2 content.
    """
    lines = molblock_text.split("\n")
    try:
        n_atoms = int(lines[3][0:3])
    except (IndexError, ValueError):
        return molblock_text
    for i in range(4, min(4 + n_atoms, len(lines))):
        line = lines[i]
        if len(line) >= 52:
            lines[i] = line[:49] + "  0" + line[52:]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Carbon classification (on an H-stripped mol)
# ---------------------------------------------------------------------------

def carbon_class(atom):
    """Mutually exclusive carbon class, precedence: C=O > aromatic > sp2 > sp > sp3 (by #H)."""
    assert atom.GetAtomicNum() == 6, "carbon_class called on a non-carbon atom"
    for b in atom.GetBonds():
        if b.GetBondType() == Chem.BondType.DOUBLE:
            other = b.GetOtherAtom(atom)
            if other.GetAtomicNum() == 8:
                return "C=O"
    if atom.GetIsAromatic():
        return "aromatisch"
    hyb = atom.GetHybridization()
    if hyb == Chem.HybridizationType.SP2:
        return "sp2 olefinisch/C=N"
    if hyb == Chem.HybridizationType.SP:
        return "sp"
    n_h = atom.GetTotalNumHs()
    if n_h == 3:
        return "CH3"
    if n_h == 2:
        return "CH2"
    if n_h == 1:
        return "CH"
    return "Cq"


def hetero_bound(atom):
    """True iff the carbon has any heavy neighbour that is not carbon."""
    return any(n.GetAtomicNum() not in (1, 6) for n in atom.GetNeighbors())


def size_bin(mol, bins=None):
    """Heavy-atom-count bin label, using config.SIZE_BINS by default."""
    if bins is None:
        bins = config.SIZE_BINS if config is not None else [(0, 15), (16, 25), (26, 40), (41, 60), (61, 10**6)]
    n = mol.GetNumHeavyAtoms()
    for lo, hi in bins:
        if lo <= n <= hi:
            return f">={lo}" if hi >= 10**6 else f"{lo}-{hi}"
    return "unknown"


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def metrics(errors_signed, mol_ids):
    """Aggregate metrics for a set of (predicted - reference) signed errors, grouped by molecule.

    Returns a dict with n_carbons, n_molecules, MAE, median_AE, RMSE, mean_signed_error,
    pct_gt5, pct_gt10, pct_within_0_05, and mol_mae_quantiles (per-molecule MAE: median, p90,
    pct_le_2, pct_le_3).
    """
    errors_signed = [float(e) for e in errors_signed]
    mol_ids = list(mol_ids)
    assert len(errors_signed) == len(mol_ids)
    n = len(errors_signed)
    if n == 0:
        return {
            "n_carbons": 0, "n_molecules": 0, "MAE": None, "median_AE": None, "RMSE": None,
            "mean_signed_error": None, "pct_gt5": None, "pct_gt10": None, "pct_within_0_05": None,
            "mol_mae_quantiles": None,
        }
    abs_err = [abs(e) for e in errors_signed]
    out = {
        "n_carbons": n,
        "n_molecules": len(set(mol_ids)),
        "MAE": statistics.mean(abs_err),
        "median_AE": statistics.median(abs_err),
        "RMSE": math.sqrt(statistics.mean(e * e for e in errors_signed)),
        "mean_signed_error": statistics.mean(errors_signed),
        "pct_gt5": 100.0 * sum(a > 5 for a in abs_err) / n,
        "pct_gt10": 100.0 * sum(a > 10 for a in abs_err) / n,
        "pct_within_0_05": 100.0 * sum(a <= 0.05 for a in abs_err) / n,
    }
    by_mol = defaultdict(list)
    for e, mid in zip(abs_err, mol_ids):
        by_mol[mid].append(e)
    mol_maes = [statistics.mean(v) for v in by_mol.values()]
    mol_maes_sorted = sorted(mol_maes)
    p90_idx = min(len(mol_maes_sorted) - 1, max(0, int(math.ceil(0.9 * len(mol_maes_sorted))) - 1))
    out["mol_mae_quantiles"] = {
        "median": statistics.median(mol_maes),
        "p90": mol_maes_sorted[p90_idx],
        "pct_le_2": 100.0 * sum(m <= 2 for m in mol_maes) / len(mol_maes),
        "pct_le_3": 100.0 * sum(m <= 3 for m in mol_maes) / len(mol_maes),
        "n_molecules": len(mol_maes),
    }
    return out


def paired_bootstrap(err_a, err_b, mol_ids, n=1000, seed=None):
    """95% CI of MAE(|err_a|) - MAE(|err_b|), resampling molecules (not carbons) with replacement.

    err_a, err_b, mol_ids must be aligned per-carbon sequences restricted to carbons present in
    both error sets (the caller is responsible for that alignment).
    """
    if seed is None:
        seed = config.SEED if config is not None else 0
    by_mol = defaultdict(lambda: ([], []))
    for a, b, mid in zip(err_a, err_b, mol_ids):
        by_mol[mid][0].append(abs(a))
        by_mol[mid][1].append(abs(b))
    mols = list(by_mol.keys())
    if not mols:
        return None
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        sample = [mols[rng.randrange(len(mols))] for _ in range(len(mols))]
        a_errs, b_errs = [], []
        for m in sample:
            a_errs.extend(by_mol[m][0])
            b_errs.extend(by_mol[m][1])
        if not a_errs or not b_errs:
            continue
        diffs.append(statistics.mean(a_errs) - statistics.mean(b_errs))
    diffs.sort()
    if not diffs:
        return None
    lo_idx = max(0, int(0.025 * len(diffs)))
    hi_idx = min(len(diffs) - 1, int(0.975 * len(diffs)) - 1)
    point = statistics.mean(abs(a) for a in err_a) - statistics.mean(abs(b) for b in err_b)
    return {"point": point, "ci_lo": diffs[lo_idx], "ci_hi": diffs[hi_idx], "n_boot": len(diffs)}


def embed_mol_with_timeout(mol, max_attempts=3, timeout_s=20, ff_max_iters=200, base_seed=42):
    """Embed `mol` (ETKDGv3) in the caller's atom order, with a per-attempt wall-clock
    `timeout_s` (seconds; calibrated empirically against RDKit 2026.09.1 -- a timeout of N
    reliably returns in ~N seconds on a molecule chosen to fail). Attempt 0 uses the
    deterministic starting geometry; attempts 1.. use random starting coordinates. On success,
    optimizes geometry (MMFF, UFF fallback), mirroring csp5's own post-embed step. Returns
    (embedded_mol, elapsed_seconds). Raises RuntimeError on failure, with a reason prefix of
    "embed_timeout" (an attempt ran close to the full timeout) or "embed_fail" (every attempt
    failed fast, for a chemistry reason unrelated to the time budget) and the elapsed seconds.

    Deviation (2026-10-14, quick task 261013-knr): replaces reliance on
    `csp5._runtime.cascade_core.embed_mol_conformers_canonical`, which calls RDKit's ETKDGv3
    with `timeout=0` (no limit). A handful of large fused/macrocyclic COCONUT natural products
    (150-200 heavy atoms, >10 rings) then hang indefinitely on a random-coordinate retry --
    confirmed empirically: the same molecule that stalled 7 production workers for 3h44m with
    zero output returns `cid=-1` in ~3.1s/~8.1s wall time when given `timeout=3`/`timeout=8`
    respectively, via plain `AllChem.EmbedMolecule`. Atom order is preserved (no canonical
    renumbering), which is required for CSP5's atom_index to keep meaning the 0-based molblock
    index.

    Second deviation (2026-10-14, found after the first production run completed and gave
    CSP5-vs-experiment MAE ~25-28 ppm on the referee -- chemically impossible): this function
    originally embedded `mol` AS GIVEN, without adding explicit hydrogens first. COCONUT and
    NMRShiftDB2 molblocks normally carry only IMPLICIT hydrogens (no H atoms in the connection
    table), so ETKDG was placing 3D coordinates for the heavy-atom skeleton only -- CSP5's
    geometry-based GNN then saw a conformer with no hydrogen positions at all, which corrupted
    every prediction. The validation that passed before the first production run (the
    embedder-swap check in `00_positive_control.py`) did not catch this, because Exp22K's own
    `mol_block` already carries explicit hydrogens (confirmed: entry 0 has 40 atoms vs 16 heavy
    atoms) -- so that check exercised only the already-all-explicit-H path. `csp5._runtime
    .cascade_core._canonical_embedding_mol` always calls `Chem.AddHs(Chem.Mol(mol))` before
    embedding for exactly this reason; this function now does the same. `Chem.AddHs` appends
    new hydrogens after the existing atoms without reordering them, so heavy-atom indices 0..
    N_heavy-1 are unchanged -- no canonical-order round trip is needed here, unlike csp5's own
    implementation (which separately needs one because it also canonicalizes atom order).
    """
    m = Chem.Mol(mol)
    if m.GetNumConformers():
        m.RemoveAllConformers()
    m = Chem.AddHs(m)
    t_start = time.perf_counter()
    cid = -1
    attempt_seconds = []
    for attempt in range(max(1, int(max_attempts))):
        params = AllChem.ETKDGv3()
        params.timeout = int(timeout_s)
        params.useRandomCoords = attempt > 0
        params.randomSeed = (int(base_seed) + attempt) & 0x7FFFFFFF
        t0 = time.perf_counter()
        cid = AllChem.EmbedMolecule(m, params)
        attempt_seconds.append(time.perf_counter() - t0)
        if cid == 0:
            break
    dt_total = time.perf_counter() - t_start
    if cid != 0:
        was_timeout = any(s >= 0.9 * timeout_s for s in attempt_seconds)
        reason = "embed_timeout" if was_timeout else "embed_fail"
        raise RuntimeError(f"{reason} after {len(attempt_seconds)} attempt(s), {dt_total:.1f}s")

    optimized = False
    try:
        if AllChem.MMFFHasAllMoleculeParams(m):
            status = AllChem.MMFFOptimizeMolecule(m, maxIters=int(ff_max_iters))
            optimized = status in (0, 1)
    except Exception:  # noqa: BLE001 - force-field optimisation can fail for many reasons
        optimized = False
    if not optimized:
        try:
            AllChem.UFFOptimizeMolecule(m, maxIters=int(ff_max_iters))
        except Exception:  # noqa: BLE001
            pass
    dt_total = time.perf_counter() - t_start
    return m, dt_total


def self_check(mol, idx_set):
    """True iff every index in idx_set is a carbon atom index of mol and the set does not
    exceed the molecule's carbon count."""
    carbons = {a.GetIdx() for a in mol.GetAtoms() if a.GetAtomicNum() == 6}
    idx_set = set(idx_set)
    if not idx_set <= carbons:
        return False
    if len(idx_set) > len(carbons):
        return False
    return True
