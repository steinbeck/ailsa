"""Download the raw NMR experiments of BMRB metabolomics entry bmse000667 (alpha-terpineol).

Usage: python download_bmrb.py --dest DIR

BMRB publishes the entry as a plain directory tree (no archive). This script fetches the
experiments that process_fid.py needs into DIR/raw/<experiment>/ and, for the two template
folders, the entry's own pdata/1 (only used for the numeric processing-parameter layout).
The data are not redistributed with AILSA; see README.md in this folder for the credit.

Stdlib only. The destination must be outside the git repository.
"""
# ruff: noqa: E501
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

BASE = "https://bmrb.io/ftp/pub/bmrb/metabolomics/entry_directories/bmse000667/nmr/set01/"
# experiment folder -> files to fetch (relative to the experiment folder)
RAW_FILES = ("acqus", "acqu", "pulseprogram")
EXPERIMENTS = {
    "1H": RAW_FILES + ("fid",),
    "13C": RAW_FILES + ("fid",),
    "DEPT_90": RAW_FILES + ("fid",),
    "DEPT_135": RAW_FILES + ("fid",),
    "1H_13C_HSQC": RAW_FILES + ("acqu2", "acqu2s", "ser"),
    "1H_13C_HMBC": RAW_FILES + ("acqu2", "acqu2s", "ser"),
    "HH_COSY": RAW_FILES + ("acqu2", "acqu2s", "ser"),
}
# template pdata folders (numeric procs layout for process_fid.py --template-1d/-2d)
TEMPLATES = {
    "1H": ("pdata/1/procs", "pdata/1/1r", "pdata/1/1i"),
    "1H_13C_HSQC": (
        "pdata/1/procs",
        "pdata/1/proc2s",
        "pdata/1/2rr",
        "pdata/1/2ri",
        "pdata/1/2ir",
        "pdata/1/2ii",
    ),
}
OPTIONAL = {"acqu2", "acqu2s"}  # absent in 1D experiments listings; tolerate a 404


def safe_join(dest: Path, name: str) -> Path:
    """Resolve `name` below `dest`; reject absolute paths and '..' components (zip-slip guard)."""
    posix = PurePosixPath(name.replace("\\", "/"))
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise ValueError(f"unsafe path rejected: {name!r}")
    target = (dest / Path(*posix.parts)).resolve()
    root = dest.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"unsafe path rejected: {name!r}")
    return target


def inside_repo(path: Path) -> bool:
    here = Path(__file__).resolve().parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=here,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    root = Path(out).resolve()
    p = path.resolve()
    return p == root or root in p.parents


def fetch(url: str, target: Path, digest: hashlib._Hash) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 (fixed https BMRB host)
        data = resp.read()
    target.write_bytes(data)
    digest.update(target.name.encode() + b"\0" + hashlib.sha256(data).digest())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dest", required=True, type=Path, help="new folder for the download (outside the git repository)")
    args = ap.parse_args(argv)
    dest: Path = args.dest
    if inside_repo(dest):
        print(f"refusing: {dest} is inside the git repository; the example data stay out of it", file=sys.stderr)
        return 2
    raw = dest / "raw"
    digest = hashlib.sha256()
    try:
        for exp, files in EXPERIMENTS.items():
            wanted = list(files) + (list(TEMPLATES[exp]) if exp in TEMPLATES else [])
            for rel in wanted:
                url = f"{BASE}{exp}/{rel}"
                target = safe_join(raw, f"{exp}/{rel}")
                try:
                    fetch(url, target, digest)
                except urllib.error.HTTPError as err:
                    if err.code == 404 and rel in OPTIONAL:
                        continue
                    raise
                print(f"fetched {exp}/{rel}")
    except (urllib.error.URLError, OSError, ValueError) as err:
        print(f"download failed: {err}", file=sys.stderr)
        return 1
    print(f"sha256 over all fetched files: {digest.hexdigest()}")
    print(f"raw data in {raw}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
