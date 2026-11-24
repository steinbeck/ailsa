"""Experiment inventory of a Bruker dataset for the run record (REC-28).

Covers every immediate experiment folder, including unreadable ones. Title files are never
opened and non-numeric folder names are replaced by aliases, so a blind run records nothing
that could name the compound. Standard library only at module level.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from ailsa.record.events import exp_id
from ailsa.record.fsutil import sha256_file

_JCAMP_SUFFIXES = (".dx", ".jdx")
_DROP_HEADERS = {"TITLE", "OWNER"}
_DATA_BLOCK = re.compile(
    r"^##(XYDATA|XYPOINTS|PEAK TABLE|PEAKTABLE|DATA TABLE|DATATABLE|NTUPLES|PAGE)\b", re.I
)
_JCAMP_MAX_DEPTH = 4
_SOURCE_NAMES = (
    "acqus",
    "acqu2s",
    "pulseprogram",
    "fid",
    "ser",
    "pdata/1/procs",
    "pdata/1/proc2s",
    "pdata/1/1r",
    "pdata/1/2rr",
)


def _source_files(folder: Path, label: str) -> list[dict[str, str]]:
    files = []
    for name in _SOURCE_NAMES:
        path = folder / name
        if path.is_symlink() or not path.is_file():
            continue
        files.append({"path": f"{label}/{name}", "sha256": sha256_file(path)})
    return files


def _entry(exp: Any, label: str, folder_alias: str | None) -> dict[str, Any]:
    kind = exp.kind
    unknown = kind == "2D-other" or kind.startswith("1D-")
    entry: dict[str, Any] = {
        "id": exp_id(label),
        "folder_alias": folder_alias,
        "kind": kind,
        "nucleus": exp.nucleus or None,
        "nucleus_f1": exp.nucleus_f1,
        "pulse_program": exp.pulse_program or None,
        "processed": exp.processed,
        "raw": exp.raw,
        "edited": exp.edited,
        "scans": exp.scans,
        "solvent": exp.solvent,
        "sfo1_mhz": exp.sfo1_mhz,
        "sfo1_f1_mhz": exp.sfo1_f1_mhz,
        "temperature_k": exp.temperature_k,
        "sw_hz": exp.sw_hz,
        "nus": None,
        "readable": not unknown,
        "reason": f"unknown experiment type: {exp.pulse_program or kind}" if unknown else None,
        "source_files": _source_files(exp.path, label),
    }
    if exp.nus_fraction is not None or exp.nus_schedule:
        entry["nus"] = {
            "fraction": exp.nus_fraction,
            "schedule_present": bool(exp.nus_schedule),
        }
    return entry


def _jcamp_headers(path: Path) -> dict[str, str]:
    headers: dict[str, str] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if _DATA_BLOCK.match(line):
                break
            match = re.match(r"^##([^=]+)=\s*(.*)$", line.rstrip("\n"))
            if not match:
                continue
            key = match.group(1).strip()
            if key.upper() in _DROP_HEADERS:
                continue
            headers[key] = match.group(2).strip()
    return headers


def _jcamp_files(dataset: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(dataset, followlinks=False):
        here = Path(dirpath)
        if len(here.relative_to(dataset).parts) >= _JCAMP_MAX_DEPTH:
            dirnames[:] = []
        dirnames[:] = sorted(d for d in dirnames if d != "analysis")
        for name in sorted(filenames):
            path = here / name
            if not name.lower().endswith(_JCAMP_SUFFIXES) or path.is_symlink():
                continue
            found.append(
                {
                    "path": path.relative_to(dataset).as_posix(),
                    "sha256": sha256_file(path),
                    "headers": _jcamp_headers(path),
                }
            )
    return found


def _labelled_folders(dataset: Path) -> list[tuple[Path, Any, str, str | None]]:
    """(folder, experiment or None, label, alias) for every experiment folder, in order.

    Same aliasing rule as scan_dataset: numeric folder names are their own label, other
    readable ones become x1, x2, ... and unreadable ones u1, u2, ...
    """
    from ailsa.case.scan import _expno_key, read_experiment

    folders = sorted(
        (p for p in Path(dataset).iterdir() if p.is_dir() and not p.is_symlink()),
        key=lambda p: _expno_key(p.name),
    )
    out: list[tuple[Path, Any, str, str | None]] = []
    aliases = 0
    unreadable_aliases = 0
    for folder in folders:
        exp = read_experiment(folder)
        if folder.name.isdigit():
            label, alias = folder.name, None
        elif exp is not None:
            aliases += 1
            label = alias = f"x{aliases}"
        else:
            unreadable_aliases += 1
            label = alias = f"u{unreadable_aliases}"
        out.append((folder, exp, label, alias))
    return out


def experiment_label(exp_dir: str | os.PathLike[str]) -> str:
    """The inventory label of an experiment folder (its expno, or its x/u alias).

    Record ids and run-folder paths use this label, never a non-numeric folder name, which
    could name the compound. A folder the inventory would not list gets a hash alias.
    """
    folder = Path(exp_dir)
    if folder.name.isdigit():
        return folder.name
    try:
        for candidate, _exp, label, _alias in _labelled_folders(folder.parent):
            if candidate.name == folder.name:
                return label
    except OSError:
        pass
    return "x" + hashlib.sha256(folder.name.encode("utf-8")).hexdigest()[:8]


def build_inventory(dataset: Path, *, blind: bool, fingerprint: str) -> dict[str, Any]:
    """Inventory dict matching the ``ExperimentInventory`` contract."""
    dataset = Path(dataset).resolve()
    entries: list[dict[str, Any]] = []
    for folder, exp, label, alias in _labelled_folders(dataset):
        if exp is not None:
            entry = _entry(exp, label, alias)
        else:
            has_acqus = (folder / "acqus").is_file()
            entry = {
                "id": exp_id(label),
                "folder_alias": alias,
                "readable": False,
                "reason": "parameters unreadable" if has_acqus else "no acqus",
                "source_files": [],
            }
        entries.append(entry)
    return {
        "schema": "ailsa.experiment-inventory",
        "schema_version": "1",
        "dataset_fingerprint": fingerprint,
        "blind": blind,
        "experiments": entries,
        "jcamp_files": _jcamp_files(dataset),
        "unreadable": sum(1 for e in entries if not e["readable"]),
    }


def scanned_payload(inventory: dict[str, Any]) -> dict[str, Any]:
    """Payload of the ``spectra.scanned`` event for an inventory (one form for every writer)."""
    return {
        "experiments": [
            {"id": e.get("id"), "kind": e.get("kind"), "readable": bool(e.get("readable"))}
            for e in inventory["experiments"]
        ],
        "unreadable": inventory["unreadable"],
    }
