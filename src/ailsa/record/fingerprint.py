"""Dataset content fingerprint and the prior-run / legacy-result scans (REC-06a, D-04).

The fingerprint covers file contents and relative paths only (no mtimes, no folder name),
so a renamed or copied dataset keeps it. Standard library only.
"""

from __future__ import annotations

import fnmatch
import hashlib
import os
from pathlib import Path
from typing import Any

from ailsa.record.events import MARKER
from ailsa.record.log import first_event

EXCLUDE_DIRS = {"analysis", "__MACOSX", ".git"}
EXCLUDE_FILES = {".DS_Store"}
SAMPLE_ABOVE = 256 * 1024 * 1024
_MIB = 1024 * 1024
_LEGACY_FILES = ("CASE-PROGRESS.md", "final_results.md", "*.sol", "solutions.smi")


def _hash_file(path: Path, size: int) -> tuple[str, bool]:
    """sha256 of the file, or of first + last MiB plus size when it is very large."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        if size > SAMPLE_ABOVE:
            h.update(fh.read(_MIB))
            fh.seek(max(size - _MIB, 0))
            h.update(fh.read(_MIB))
            h.update(str(size).encode("ascii"))
            return h.hexdigest(), True
        while True:
            block = fh.read(_MIB)
            if not block:
                break
            h.update(block)
    return h.hexdigest(), False


def dataset_fingerprint(dataset: Path) -> dict[str, Any]:
    """Content fingerprint of a dataset tree."""
    root = Path(dataset)
    entries: list[tuple[str, int, str]] = []
    sampled = False
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        keep = []
        for d in dirnames:
            if d in EXCLUDE_DIRS or (here / d).is_symlink():
                continue
            if os.path.lexists(here / d / MARKER):
                continue
            keep.append(d)
        dirnames[:] = keep
        for name in filenames:
            path = here / name
            if name in EXCLUDE_FILES or path.is_symlink() or not path.is_file():
                continue
            size = path.stat().st_size
            digest, was_sampled = _hash_file(path, size)
            sampled = sampled or was_sampled
            total += size
            entries.append((path.relative_to(root).as_posix(), size, digest))
    entries.sort()
    lines = "\n".join(f"{rel}\t{size}\t{digest}" for rel, size, digest in entries)
    overall = hashlib.sha256(lines.encode("utf-8")).hexdigest()
    return {
        "fingerprint": f"sha256:{overall}",
        "mode": "sampled" if sampled else "full",
        "files": len(entries),
        "bytes": total,
    }


def find_prior_runs(workspace: Path, fingerprint: str) -> list[str]:
    """Run folder names whose first event carries ``fingerprint`` (reads first lines only)."""
    ws = Path(workspace)
    if not ws.is_dir():
        return []
    found: list[str] = []
    for child in sorted(ws.iterdir()):
        if not child.is_dir() or not os.path.lexists(child / MARKER):
            continue
        event = first_event(child)
        if not event:
            continue
        payload = event.get("payload")
        dataset = payload.get("dataset") if isinstance(payload, dict) else None
        value = None
        if isinstance(dataset, dict):
            value = dataset.get("fingerprint") or dataset.get("dataset_fingerprint")
        elif isinstance(payload, dict):
            value = payload.get("dataset_fingerprint")
        if value == fingerprint:
            found.append(child.name)
    return found


def legacy_results(dataset: Path, max_depth: int = 4) -> list[str]:
    """Relative paths of earlier-result artefacts inside the dataset tree."""
    root = Path(dataset)
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        here = Path(dirpath)
        depth = len(here.relative_to(root).parts)
        if depth >= max_depth:
            dirnames[:] = []
        keep = []
        for d in sorted(dirnames):
            if (here / d).is_symlink():
                continue
            rel = (here / d).relative_to(root).as_posix()
            if d == "analysis" or d.startswith("iteration_"):
                found.append(rel)
                continue
            keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            if any(fnmatch.fnmatch(name, pat) for pat in _LEGACY_FILES):
                found.append((here / name).relative_to(root).as_posix())
    return sorted(found)


def workspace_overlaps(workspace: Path, dataset: Path) -> str | None:
    """A message when the workspace and the dataset folder contain one another."""
    ws = Path(workspace).resolve()
    ds = Path(dataset).resolve()
    if ws == ds or ds in ws.parents:
        return "the workspace is inside the dataset folder; run folders must live outside the data"
    if ws in ds.parents:
        return "the dataset folder is inside the workspace; run folders must live outside the data"
    return None
