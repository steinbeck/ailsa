"""Find and classify the experiments of a Bruker dataset.

Reads only the acquisition parameter files (``acqus``, ``acqu2s``), never the data, so
it is fast and works on unprocessed folders too. The title file is deliberately not
read: it may name the compound.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FORMULA_FILES = (
    "molecular-formula.txt",
    "molecular_formula.txt",
    "molecularformula.txt",
    "formula.txt",
    "molform.txt",
)

# Kinds whose raw data setup can process when no processed spectrum exists. Not DEPT
# or APT: their signs carry the information, and automatic phasing is unreliable.
RAW_OK = ("13C", "HSQC", "HMBC", "COSY")

# Kinds the guided workflow uses, in the order they are reported.
KINDS = (
    "13C",
    "DEPT-135",
    "DEPT-90",
    "APT",
    "HSQC",
    "HMBC",
    "COSY",
    "1H",
)


@dataclass
class Experiment:
    """One numbered experiment folder."""

    expno: str
    path: Path
    kind: str
    pulse_program: str
    nucleus: str
    nucleus_f1: str | None
    scans: int
    solvent: str | None
    processed: bool
    edited: bool = False
    raw: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "expno": self.expno,
            "kind": self.kind,
            "pulse_program": self.pulse_program,
            "scans": self.scans,
            "processed": self.processed,
            "raw": self.raw,
            "edited": self.edited,
        }


@dataclass
class ScanResult:
    """All experiments of a dataset and the one chosen per kind."""

    dataset: Path
    experiments: list[Experiment] = field(default_factory=list)
    chosen: dict[str, Experiment] = field(default_factory=dict)
    formula: str | None = None
    formula_file: str | None = None
    solvent: str | None = None

    def alternatives(self, kind: str) -> list[Experiment]:
        """Usable experiments of ``kind`` other than the chosen one."""
        chosen = self.chosen.get(kind)
        return [e for e in self.experiments if e.kind == kind and e.processed and e is not chosen]


def _param(text: str, key: str) -> str | None:
    match = re.search(rf"^##\${re.escape(key)}=\s*(.*)$", text, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    if value.startswith("<") and value.endswith(">"):
        value = value[1:-1]
    return value.strip()


def classify(pulse_program: str, nucleus: str, nucleus_f1: str | None, is_2d: bool) -> str:
    """Experiment kind from the pulse program name and the nuclei."""
    pp = pulse_program.lower()
    if not is_2d:
        if nucleus == "13C":
            if "deptq" in pp:
                return "DEPTQ"
            if "dept" in pp:
                if "90" in pp:
                    return "DEPT-90"
                if "45" in pp:
                    return "DEPT-45"
                return "DEPT-135"
            if "jmod" in pp or "apt" in pp:
                return "APT"
            return "13C"
        if nucleus == "1H":
            return "1H"
        return f"1D-{nucleus}"
    hetero = nucleus_f1 is not None and nucleus_f1 != nucleus
    if hetero and nucleus_f1 != "13C":
        base = classify(pulse_program, nucleus, "13C", is_2d)
        return f"{base}-{nucleus_f1}" if base in ("HSQC", "HMBC") else "2D-other"
    if "hmbc" in pp:
        return "HMBC"
    if "inv4" in pp:
        if "lr" in pp or "lplr" in pp:
            return "HMBC"
        return "HSQC"
    if "tocsy" in pp and hetero:
        return "HSQC-TOCSY"
    if "hsqc" in pp or "hmqc" in pp:
        return "HSQC"
    if "h2bc" in pp:
        return "H2BC"
    if "cosy" in pp:
        return "COSY"
    if "tocsy" in pp or "mlev" in pp or "dipsi" in pp:
        return "TOCSY"
    if "noesy" in pp:
        return "NOESY"
    if "roesy" in pp:
        return "ROESY"
    return "2D-other"


def read_experiment(path: Path) -> Experiment | None:
    """Parse one experiment folder; ``None`` if it has no ``acqus``."""
    acqus = path / "acqus"
    if not acqus.is_file():
        return None
    text = acqus.read_text(errors="replace")
    acqu2s = path / "acqu2s"
    is_2d = acqu2s.is_file()
    pulse_program = _param(text, "PULPROG") or ""
    nucleus = _param(text, "NUC1") or ""
    nucleus_f1 = None
    if is_2d:
        nucleus_f1 = _param(acqu2s.read_text(errors="replace"), "NUC1")
    try:
        scans = int(float(_param(text, "NS") or 0))
    except ValueError:
        scans = 0
    solvent = _param(text, "SOLVENT") or None
    processed_file = "2rr" if is_2d else "1r"
    processed = (path / "pdata" / "1" / processed_file).is_file()
    raw = (path / ("ser" if is_2d else "fid")).is_file()
    kind = classify(pulse_program, nucleus, nucleus_f1, is_2d)
    edited = kind == "HSQC" and "hsqced" in pulse_program.lower()
    return Experiment(
        expno=path.name,
        path=path,
        kind=kind,
        pulse_program=pulse_program,
        nucleus=nucleus,
        nucleus_f1=nucleus_f1,
        scans=scans,
        solvent=solvent,
        processed=processed,
        edited=edited,
        raw=raw,
    )


def _expno_key(expno: str) -> tuple[int, str]:
    return (int(expno), expno) if expno.isdigit() else (10**9, expno)


def find_formula(dataset: Path) -> tuple[str | None, str | None]:
    """A molecular formula from a sidecar file in the dataset, if there is one."""
    candidates = [dataset / name for name in FORMULA_FILES]
    candidates += sorted(dataset.glob("*.formula"))
    for path in candidates:
        if not path.is_file():
            continue
        text = re.sub(r"\s+", "", path.read_text(errors="replace"))
        if re.fullmatch(r"([A-Z][a-z]?\d*)+", text):
            return text, path.name
    return None, None


def scan_dataset(dataset: Path) -> ScanResult:
    """Classify every experiment of ``dataset`` and choose one per kind.

    Choice per kind: processed data first, then most scans, then lowest experiment
    number. An edited HSQC is preferred over a plain one. Without processed data, a raw
    13C, HSQC, HMBC or COSY experiment is chosen (setup processes it).
    """
    dataset = dataset.resolve()
    result = ScanResult(dataset=dataset)
    folders = [p for p in dataset.iterdir() if p.is_dir()]
    aliases = 0
    for folder in sorted(folders, key=lambda p: _expno_key(p.name)):
        experiment = read_experiment(folder)
        if experiment is not None:
            if not experiment.expno.isdigit():
                # A folder name other than a number may name the compound; never show it.
                aliases += 1
                experiment.expno = f"x{aliases}"
            result.experiments.append(experiment)
    for kind in {e.kind for e in result.experiments}:
        usable = [e for e in result.experiments if e.kind == kind and e.processed]
        if not usable and kind in RAW_OK:
            # No processed spectrum: setup processes the raw data itself.
            usable = [e for e in result.experiments if e.kind == kind and e.raw]
        if not usable:
            continue
        usable.sort(key=lambda e: (not e.processed, not e.edited, -e.scans, _expno_key(e.expno)))
        result.chosen[kind] = usable[0]
    solvents = [e.solvent for e in result.experiments if e.solvent]
    result.solvent = max(set(solvents), key=solvents.count) if solvents else None
    result.formula, result.formula_file = find_formula(dataset)
    return result
