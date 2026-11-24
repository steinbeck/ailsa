"""Process the public BMRB raw data (FIDs only) into Bruker pdata that AILSA can read.

Usage: python process_fid.py --raw DIR --out DIR --template-1d DIR --template-2d DIR --plots DIR

Data: BMRB entry bmse000667 (see README.md in this folder)

Decisions, all made from the data alone (no knowledge of the compound):
- referencing: on the TMS line present in the sample (0.00 ppm in 1H and 13C);
- 1D phase: ACME autophase; DEPT-135 takes DEPT-90's phase (same sequence, same receiver path);
- HSQC (edited, echo/antiecho): F2 and F1 phase chosen for pure absorption at the strongest
  cross-peaks; the global sign is set so that cross-peak signs agree with DEPT-135
  (CH/CH3 up, CH2 down), the Bruker convention for edited HSQC;
- HMBC and COSY: magnitude mode, as acquired (QF);
- F1 orientation of the heteronuclear spectra: the one whose F1 projection matches the 13C
  spectrum; COSY: the one that makes the matrix symmetric about the diagonal.
"""
# ruff: noqa: E501, E702, E741, B007, B023, B905
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import nmrglue as ng
import numpy as np

EXPS = [  # out number, raw folder, kind, line broadening (Hz), size
    ("1", "1H", "1d", 0.3, 65536),
    ("2", "13C", "1d", 1.0, 65536),
    ("3", "DEPT_90", "1d", 1.0, 65536),
    ("4", "DEPT_135", "1d", 1.0, 65536),
    ("5", "1H_13C_HSQC", "hsqc", None, (1024, 1024)),
    ("6", "1H_13C_HMBC", "mag", None, (1024, 2048)),
    ("7", "HH_COSY", "mag", None, (1024, 1024)),
]
KEEP = ("acqu", "acqus", "acqu2", "acqu2s", "pulseprogram", "fid", "ser")


def clean_copy(src: Path, dst: Path) -> None:
    """Copy the raw files AILSA needs; drop path/user comment lines and the BMRB files."""
    dst.mkdir(parents=True, exist_ok=True)
    for name in KEEP:
        f = src / name
        if not f.exists():
            continue
        if name.startswith("acqu"):
            lines = f.read_text(errors="ignore").splitlines()
            lines = [ln for ln in lines if not ln.startswith("$$")]
            lines = [re.sub(r"^##OWNER=.*", "##OWNER= nmr", ln) for ln in lines]
            (dst / name).write_text("\n".join(lines) + "\n")
        else:
            shutil.copy2(f, dst / name)


def template_procs(tdir: Path, key: str) -> dict:
    dic, _ = ng.bruker.read_pdata(str(tdir))
    d = {k: v for k, v in dic[key].items() if not k.startswith("_")}
    return d


def axis_offset(center_ppm: float, sw_hz: float, sf: float) -> float:
    return center_ppm + sw_hz / (2 * sf)


def ppm_axis(offset: float, sw_hz: float, sf: float, n: int) -> np.ndarray:
    return offset - np.arange(n) * (sw_hz / sf) / n


def f2_ft(dic, data, size, window):
    data = ng.bruker.remove_digital_filter(dic, data)
    if window == "em":
        pass
    elif window == "sine":
        data = ng.proc_base.sp(data, off=0.0, end=1.0, pow=1.0)
    elif window == "cos2":
        data = ng.proc_base.sp(data, off=0.5, end=1.0, pow=2.0)
    data = ng.proc_base.zf_size(data, size)
    data = ng.proc_base.fft(data)
    return ng.proc_base.rev(data)


def find_line(spec_abs, ppm, lo, hi):
    m = (ppm >= lo) & (ppm <= hi)
    i = np.argmax(np.where(m, spec_abs, -np.inf))
    return float(ppm[i]), float(spec_abs[i])


def write_pdata(expdir: Path, data: np.ndarray, procs: dict, proc2s: dict | None = None, title: str | None = None) -> None:
    pdir = expdir / "pdata" / "1"
    pdir.mkdir(parents=True, exist_ok=True)
    scale = 2 ** 28 / max(1e-30, float(np.max(np.abs(data))))
    idata = np.round(data * scale).astype("<i4")
    dic = {"procs": procs}
    if proc2s is not None:
        dic["proc2s"] = proc2s
    ng.bruker.write_pdata(str(pdir), dic, idata, write_procs=True, overwrite=True, big=False, isfloat=False)
    (pdir / "title").write_text((title or expdir.name) + "\n")


def base_procs(t: dict, si: int, offset: float, sw_hz: float, sf: float, extra: dict | None = None,
               axnuc: str = "", spectyp: str = "") -> dict:
    p = dict(t)
    # never carry text over from the template datasets (titles, solvent regions, spectrum types, user fields)
    for k, v in list(p.items()):
        if isinstance(v, str):
            p[k] = ""
    p.update({"AXNUC": axnuc, "SPECTYP": spectyp, "AXNAME": t.get("AXNAME", "")})
    p.update({"SI": si, "OFFSET": offset, "SW_p": sw_hz, "SF": sf, "FTSIZE": si, "NC_proc": 0,
              "BYTORDP": 0, "DTYPP": 0, "XDIM": si, "PHC0": 0, "PHC1": 0, "SR": 0})
    if extra:
        p.update(extra)
    p["_comments"] = []
    p["_coreheader"] = ["##TITLE= Parameter file", "##JCAMPDX= 5.0", "##DATATYPE= Parameter Values",
                        "##ORIGIN= AILSA example processing (nmrglue)", "##OWNER= nmr"]
    return p


def _repo_root() -> Path | None:
    """Root of the git repository this script lives in (None if not in one)."""
    here = Path(__file__).resolve().parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=here, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(out).resolve() if out else None


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--raw", required=True, type=Path, help="BMRB raw set folder (contains 1H, 13C, ...)")
    ap.add_argument("--out", required=True, type=Path, help="output dataset folder (must be outside the git repository)")
    ap.add_argument("--template-1d", required=True, type=Path, help="any Bruker 1D pdata/1 folder (numeric procs layout only)")
    ap.add_argument("--template-2d", required=True, type=Path, help="any Bruker 2D pdata/1 folder (numeric procs layout only)")
    ap.add_argument("--plots", required=True, type=Path, help="folder for the diagnostic plots and processing log")
    args = ap.parse_args(argv)
    RAW, OUT, T1D, T2D, PLOTS = args.raw, args.out, args.template_1d, args.template_2d, args.plots

    root = _repo_root()
    if root is not None:
        for target in (OUT, PLOTS):
            if _inside(target.resolve(), root):
                print(f"refusing: {target} is inside the git repository; the example data stay out of it", file=sys.stderr)
                return 2

    log: dict = {}

    # ------------------------------------------------------------------ 1D
    T1 = template_procs(T1D, "procs")
    T2 = template_procs(T2D, "procs")
    T2b = template_procs(T2D, "proc2s")
    spectra1d: dict = {}
    dept90_phase = None
    cal = {}  # nucleus -> ppm correction (subtract from axis)
    for num, raw, kind, lb, size in EXPS:
        if kind != "1d":
            continue
        src, dst = RAW / raw, OUT / num
        clean_copy(src, dst)
        dic, fid = ng.bruker.read(str(src))
        a = dic["acqus"]
        sw, bf, o1 = a["SW_h"], a["BF1"], a["O1"]
        fid = ng.bruker.remove_digital_filter(dic, fid)
        fid = ng.proc_base.em(fid, lb=lb / sw)
        spec = ng.proc_base.rev(ng.proc_base.fft(ng.proc_base.zf_size(fid, size)))
        if raw == "DEPT_135":
            p0, p1 = dept90_phase
            spec = ng.proc_base.ps(spec, p0=p0, p1=p1)
        else:
            spec, (p0, p1) = ng.proc_autophase.autops(spec, "acme", return_phases=True, disp=False)
            if raw == "DEPT_90":
                dept90_phase = (p0, p1)
        real = ng.proc_bl.baseline_corrector(spec.real.copy(), wd=20)
        off0 = axis_offset(o1 / bf, sw, bf)
        ppm = ppm_axis(off0, sw, bf, size)
        nuc = a["NUC1"]
        if raw == "1H":
            tms, _ = find_line(np.abs(real), ppm, -0.4, 0.4)
            cal[nuc] = tms
        elif raw == "13C":
            # no visible TMS line in 13C: reference on acetone-d6 (CD3 septet centre 29.84, C=O 206.26)
            cd3, _ = find_line(np.abs(real), ppm, 27.0, 32.0)
            co, _ = find_line(np.abs(real), ppm, 203.5, 208.5)
            cal[nuc] = ((cd3 - 29.84) + (co - 206.26)) / 2
            log["13C referencing"] = {"cd3_raw": round(cd3, 3), "co_raw": round(co, 3), "spread_ppm": round(abs((cd3 - 29.84) - (co - 206.26)), 3)}
        off = off0 - cal[nuc]
        sf_cal = bf * (1 + cal[nuc] * 1e-6)  # nmrglue/TopSpin reference via SF (SR folded in), not OFFSET
        spectra1d[raw] = (real, ppm - cal[nuc])
        write_pdata(dst, real, base_procs(T1, size, off, sw, sf_cal,
                                          {"PHC0": float(p0), "PHC1": float(p1), "LB": float(lb), "WDW": 1},
                                          axnuc=nuc, spectyp=raw.replace("_", "")))
        log[raw] = {"phase": [round(p0, 1), round(p1, 1)], "tms_correction_ppm": round(cal[nuc], 4)}

    # solvent check (acetone-d6): 1H 2.05, 13C 29.84 and 206.26
    h_real, h_ppm = spectra1d["1H"]
    c_real, c_ppm = spectra1d["13C"]
    log["check"] = {
        "1H acetone (expect 2.05)": round(find_line(np.abs(h_real), h_ppm, 2.0, 2.1)[0], 3),
        "13C acetone CD3 (expect 29.84)": round(find_line(np.abs(c_real), c_ppm, 28.5, 31.0)[0], 2),
        "13C acetone C=O (expect 206.26)": round(find_line(np.abs(c_real), c_ppm, 205.0, 207.5)[0], 2),
    }


    def proj_match(proj_f1, f1_ppm, ref_real, ref_ppm):
        """Correlation of an F1 projection with a 1D reference spectrum on a common grid."""
        grid = np.linspace(max(f1_ppm.min(), ref_ppm.min()), min(f1_ppm.max(), ref_ppm.max()), 4000)
        a = np.interp(grid, f1_ppm[::-1], proj_f1[::-1])
        r = np.interp(grid, ref_ppm[::-1], np.abs(ref_real)[::-1])
        r[(np.abs(grid - 29.84) < 1.2) | (np.abs(grid - 206.26) < 1.5)] = 0.0  # solvent: no protons
        step = grid[1] - grid[0]
        k = np.exp(-0.5 * (np.arange(-60, 61) * step / 0.4) ** 2)
        r = np.convolve(r, k / k.sum(), mode="same")
        a = np.convolve(a, k / k.sum(), mode="same")
        a = (a - a.mean()) / (a.std() + 1e-30)
        r = (r - r.mean()) / (r.std() + 1e-30)
        return float(np.mean(a * r))


    def f1_geometry(dic, homonuclear: bool):
        a, a2 = dic["acqus"], dic["acqu2s"]
        sf1 = a2["SFO1"]
        sw1 = a2["SW"] * sf1
        if homonuclear:
            bf_f1, center = a["BF1"], a["O1"] / a["BF1"]
            nuc_f1 = a["NUC1"]
        else:
            bf_f1, center = a["BF2"], a["O2"] / a["BF2"]
            nuc_f1 = a["NUC2"]
        return sw1, bf_f1, center, nuc_f1


    def write_2d(num, raw, mat, dic, f1_si, f2_si, homonuclear, title=None):
        a = dic["acqus"]
        sw2, bf2, o1 = a["SW_h"], a["BF1"], a["O1"]
        off2 = axis_offset(o1 / bf2, sw2, bf2) - cal[a["NUC1"]]
        sw1, bf_f1, center1, nuc1 = f1_geometry(dic, homonuclear)
        off1 = axis_offset(center1, sw1, bf_f1) - cal.get(nuc1, 0.0)
        styp = {"1H_13C_HSQC": "HSQC", "1H_13C_HMBC": "HMBC", "HH_COSY": "COSY"}[raw]
        procs = base_procs(T2, f2_si, off2, sw2, bf2 * (1 + cal[a["NUC1"]] * 1e-6), axnuc=a["NUC1"], spectyp=styp)
        proc2s = base_procs(T2b, f1_si, off1, sw1, bf_f1 * (1 + cal.get(nuc1, 0.0) * 1e-6), axnuc=nuc1, spectyp=styp)
        write_pdata(OUT / num, mat, procs, proc2s, title)
        return ppm_axis(off1, sw1, bf_f1, f1_si), ppm_axis(off2, sw2, bf2, f2_si)


    # ------------------------------------------------------------------ magnitude 2D (HMBC, COSY)
    for num, raw, kind, _, size in EXPS:
        if kind != "mag":
            continue
        s1, s2 = size
        src = RAW / raw
        clean_copy(src, OUT / num)
        dic, data = ng.bruker.read(str(src))
        homo = dic["acqus"]["NUC2"] in ("off", "1H") or raw == "HH_COSY"
        d = f2_ft(dic, data, s2, "sine")
        d = d.T
        d = ng.proc_base.sp(d, off=0.0, end=1.0, pow=1.0)
        d = ng.proc_base.zf_size(d, s1)
        d = ng.proc_base.fft(d)
        best = None
        for flip in (False, True):
            m = np.abs(d).T
            if flip:
                m = m[::-1]
            if homo:
                score = float(np.corrcoef(m.ravel(), m.T.ravel())[0, 1]) if m.shape[0] == m.shape[1] else 0.0
            else:
                sw1, bf_f1, center1, nuc1 = f1_geometry(dic, False)
                f1_ppm = ppm_axis(axis_offset(center1, sw1, bf_f1) - cal.get(nuc1, 0.0), sw1, bf_f1, s1)
                score = proj_match(m.max(axis=1), f1_ppm, c_real, c_ppm)
            if best is None or score > best[0]:
                best = (score, flip, m)
        score, flip, mat = best
        f1p, f2p = write_2d(num, raw, mat, dic, s1, s2, homo)
        log[raw] = {"f1_flipped": flip, "orientation_score": round(score, 3)}
        if raw == "1H_13C_HMBC":
            hmbc = (mat, f1p, f2p)
        else:
            cosy = (mat, f1p, f2p)

    # ------------------------------------------------------------------ edited HSQC (echo/antiecho)
    num, raw, _, _, (s1, s2) = EXPS[4]
    src = RAW / raw
    clean_copy(src, OUT / num)
    dic, data = ng.bruker.read(str(src))
    d = f2_ft(dic, data, s2, "cos2")
    E, A = d[0::2], d[1::2]
    dept_real, dept_ppm = spectra1d["DEPT_135"]
    d90_real, _ = spectra1d["DEPT_90"]
    sw1, bf_f1, center1, nuc1 = f1_geometry(dic, False)
    f1_ppm = ppm_axis(axis_offset(center1, sw1, bf_f1) - cal.get(nuc1, 0.0), sw1, bf_f1, s1)


    def t1_ft(z):
        z = ng.proc_base.sp(z.T, off=0.5, end=1.0, pow=2.0)
        z = ng.proc_base.zf_size(z, s1)
        return ng.proc_base.fft(z).T


    def peaks_of(MAG, n=12):
        """Strongest local maxima, ignoring t1-noise ridge columns (strong singlets streak along F1)."""
        colmed = np.median(MAG, axis=0)
        ridge = colmed > 6 * np.median(colmed)
        ridge = np.convolve(ridge.astype(float), np.ones(7), mode="same") > 0
        work = MAG * (~ridge)[None, :]
        flat = np.argsort(work.ravel())[::-1]
        out = []
        for idx in flat[:20000]:
            i, j = divmod(int(idx), MAG.shape[1])
            if work[i, j] <= 0:
                break
            if any(abs(i - pi) < 6 and abs(j - pj) < 6 for pi, pj in out):
                continue
            out.append((i, j))
            if len(out) >= n:
                break
        return out


    def expected_signs(peaks, f1_ppm):
        """Expected sign of each cross-peak from DEPT-135 (CH/CH3 up, CH2 down); None if ambiguous."""
        out = []
        for i, _ in peaks:
            c = f1_ppm[i]
            m = np.abs(dept_ppm - c) < 1.0
            seg = dept_real[m]
            if seg.size == 0 or np.max(np.abs(seg)) < 0.05 * np.max(np.abs(dept_real)):
                out.append(None)
                continue
            pos, neg = seg.max(), -seg.min()
            if pos > 2.5 * neg:
                out.append(1.0)
            elif neg > 2.5 * pos:
                out.append(-1.0)
            else:
                out.append(None)
        return out


    def phase_search(ZA, ZB, MAG, peaks, signs):
        """Phases that make each cross-peak absorptive with its DEPT-derived sign."""
        n1, n2 = MAG.shape
        keep = [k for k, sgn in enumerate(signs) if sgn is not None]
        if len(keep) < 3:
            keep = list(range(len(peaks)))
            sg = np.ones(len(keep))
            signed = False
        else:
            sg = np.array([signs[k] for k in keep])
            signed = True
        pi_ = np.array([peaks[k][0] for k in keep]); pj_ = np.array([peaks[k][1] for k in keep])
        za_p, zb_p, mag_p = ZA[pi_, pj_], ZB[pi_, pj_], MAG[pi_, pj_] + 1e-30
        hint = log["1H"]["phase"][1]  # same SW, same digital filter; only DE differs (~40 deg)
        p0s, p1s = np.arange(0, 360, 5), np.arange(hint - 150, hint + 151, 10)
        q0s, q1s = np.arange(0, 360, 10), np.array([0.0, -180.0, 180.0, -360.0, 360.0])
        P0 = np.radians(p0s)[:, None, None, None, None]
        P1 = np.radians(p1s)[None, :, None, None, None]
        Q0 = np.radians(q0s)[None, None, :, None, None]
        Q1 = np.radians(q1s)[None, None, None, :, None]
        phi2 = P0 + P1 * (pj_ / n2)
        z = np.cos(phi2) * za_p - np.sin(phi2) * zb_p
        rr = (z * np.exp(1j * (Q0 + Q1 * (pi_ / n1)))).real / mag_p
        q = np.mean(rr * sg if signed else np.abs(rr), axis=-1)
        k = np.unravel_index(np.argmax(q), q.shape)
        return float(q[k]), (float(p0s[k[0]]), float(p1s[k[1]]), float(q0s[k[2]]), float(q1s[k[3]])), int(len(keep)), signed


    def apply_phase(ZA, ZB, ph):
        p0, p1, q0, q1 = (np.radians(x) for x in ph)
        n1, n2 = ZA.shape
        phi2 = p0 + p1 * np.arange(n2) / n2
        Z = np.cos(phi2)[None, :] * ZA - np.sin(phi2)[None, :] * ZB
        phi1 = q0 + q1 * np.arange(n1) / n1
        return (Z * np.exp(1j * phi1)[:, None]).real


    results = []
    for theta in (0, 90, 180, 270):      # relative F2 phase of the antiecho before combining
        Ar = A * np.exp(1j * np.radians(theta))
        for ea_sign in (1, -1):
            C = E + Ar
            S = (E - Ar) * (1j * ea_sign)
            ZA0 = t1_ft(C.real + 1j * S.real)
            ZB0 = t1_ft(C.imag + 1j * S.imag)
            for flip in (False, True):
                za, zb = (ZA0[::-1], ZB0[::-1]) if flip else (ZA0, ZB0)
                mag = np.sqrt(np.abs(za) ** 2 + np.abs(zb) ** 2)
                orient = proj_match(mag.max(axis=1), f1_ppm, c_real, c_ppm)
                if orient < 0.4:
                    continue
                pk = peaks_of(mag, n=16)
                sg = expected_signs(pk, f1_ppm)
                q, ph, nused, signed = phase_search(za, zb, mag, pk, sg)
                results.append((q, orient, theta, ea_sign, flip, za, zb, mag, pk, ph, nused, signed))
    q, score, theta, ea_sign, flip, ZA, ZB, MAG, peaks, ph, nused, signed = max(results, key=lambda r: r[0])
    log["hsqc_candidates"] = sorted([(round(r[0], 3), round(r[1], 3), r[2], r[3], r[4]) for r in results], reverse=True)[:6]
    RR = apply_phase(ZA, ZB, ph)
    # global sign: the signed F1 projection (CH/CH3 up, CH2 down) must correlate with DEPT-135
    colmed = np.median(MAG, axis=0)
    ridge = np.convolve((colmed > 6 * np.median(colmed)).astype(float), np.ones(7), mode="same") > 0
    proj = (RR * (~ridge)[None, :]).sum(axis=1)
    grid = np.linspace(10, 140, 3000)
    a_ = np.interp(grid, f1_ppm[::-1], proj[::-1])
    r_ = np.interp(grid, dept_ppm[::-1], dept_real[::-1])
    k = np.exp(-0.5 * (np.arange(-150, 151) * (grid[1] - grid[0]) / 0.8) ** 2)
    r_ = np.convolve(r_, k / k.sum(), mode="same")
    sign_corr = float(np.corrcoef(a_, r_)[0, 1])
    if sign_corr < 0:
        RR = -RR
        sign_corr = -sign_corr
    # The phase-sensitive result could not be phased reliably (128 increments over 236 ppm: broad,
    # overlapping F1 lines). Write the hypercomplex magnitude instead and say so in the title.
    f1p, f2p = write_2d(num, raw, MAG, dic, s1, s2, False,
                        title="HSQC, processed in magnitude mode: edited signs not retained (multiplicities from DEPT)")
    log[raw] = {"written": "magnitude", "theta": theta, "ea_sign": ea_sign, "f1_flipped": flip, "orientation_score": round(score, 3),
                "signed_absorption_quality": round(q, 3), "peaks_used": nused, "signed_by_dept": signed, "phase_f2_p0_p1_f1_p0_p1": [float(x) for x in ph], "dept_projection_correlation": round(sign_corr, 3)}
    hsqc = (MAG, f1p, f2p)

    (OUT / "Molecular-Formula.txt").write_text("C10H18O\n")
    PLOTS.mkdir(parents=True, exist_ok=True)
    (PLOTS / "processing-log.json").write_text(json.dumps(log, indent=2))
    np.savez_compressed(PLOTS / "arrays.npz", hsqcproj=proj, hsqcridge=ridge, h=h_real, hp=h_ppm, c=c_real, cp=c_ppm,
                        d135=dept_real, d135p=dept_ppm, d90=d90_real,
                        hsqc=hsqc[0].astype("f4"), hsqc1=hsqc[1], hsqc2=hsqc[2],
                        hmbc=hmbc[0].astype("f4"), hmbc1=hmbc[1], hmbc2=hmbc[2],
                        cosy=cosy[0].astype("f4"), cosy1=cosy[1], cosy2=cosy[2])
    print(json.dumps(log, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
