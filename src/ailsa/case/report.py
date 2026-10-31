"""The final report of a guided CASE run: ``analysis/final_results.md``.

Written from the problem and the ranking, so every number in it comes from a tool.
The model adds only its assessment. The identity is stated by the identity tool's
verdict: a trivial name only when the reference database confirms it.
"""

from __future__ import annotations

import json
from pathlib import Path

from ailsa.case.model import Problem, utc_now
from ailsa.case.rank import RANKING_FILE

REPORT_FILE = "final_results.md"


def _identity_lines(identity: dict[str, object] | None) -> list[str]:
    if not identity:
        return ["- **Identity:** not derived"]
    lines = [
        f"- **InChIKey:** {identity.get('inchi_key', '-')}",
        f"- **Canonical SMILES:** `{identity.get('canonical_smiles', '-')}`",
    ]
    if identity.get("matched"):
        name = str(identity.get("name") or "")
        source = identity.get("source", "reference DB")
        if name and not name.upper().startswith("CNP"):
            lines.append(f"- **In the reference database:** yes ({source}), stored name: {name}")
        else:
            lines.append(f"- **In the reference database:** yes ({source} {name}), no trivial name")
    else:
        lines.append("- **In the reference database:** no (novel or not covered)")
    return lines


def write_report(problem: Problem, analysis_dir: Path, notes: list[str]) -> Path:
    """Write ``final_results.md`` and return its path."""
    ranking_path = analysis_dir / RANKING_FILE
    if not ranking_path.exists():
        raise ValueError("no ranking yet: run `ailsa case rank` first")
    ranking = json.loads(ranking_path.read_text())
    cands = ranking["candidates"]
    top = cands[0] if cands else None
    lines = [
        "# CASE Results",
        "",
        f"**Formula:** {problem.formula}  ",
        f"**Written (UTC):** {utc_now()}  ",
        f"**Spectra used:** {', '.join(f'{k} {v}' for k, v in problem.spectra.items())}  ",
        f"**Solver runs:** {len(problem.runs)}; ranked {ranking['distinct_structures']} distinct "
        f"structures from {ranking['total_solutions']} solutions",
        "",
        "## Proposed structure",
        "",
    ]
    if top is None:
        lines.append("No structure could be ranked.")
    else:
        lines += [
            f"- **SMILES:** `{top['smiles']}`",
            f"- **Mean error, predicted vs observed 13C (assigned):** {top['mae']:.2f} ppm; "
            f"largest {top['max_error']:.1f} ppm at {top['worst_atom']}",
            f"- **HMBC correlations not explained (more than three bonds):** "
            f"{', '.join(top['violated']) or 'none'}",
            *_identity_lines(top.get("identity")),
        ]
    lines += ["", "## Assessment", ""]
    lines += [n.strip() for n in notes if n.strip()] or ["(none given)"]
    lines += [
        "",
        "## Top Candidates",
        "",
        "| Rank | SMILES | MAE (ppm) | Max error (ppm) | Unexplained HMBC |",
        "|---:|---|---:|---:|---|",
    ]
    for c in cands[:10]:
        lines.append(
            f"| {c['rank']} | `{c['smiles']}` | {c['mae']:.2f} | {c['max_error']:.1f} | "
            f"{', '.join(c['violated']) or '-'} |"
        )
    lines += ["", "## Assumptions and edits", ""]
    for a in problem.assumptions:
        lines.append(f"- {a.text}")
    for h in problem.history:
        if h.action == "edit":
            lines.append(f"- edit: {h.detail}" + (f" ({h.reason})" if h.reason else ""))
    lines += ["", "## Solver runs", "", "| Run | ELIM | Solutions | Note |", "|---:|---:|---:|---|"]
    for r in problem.runs:
        note = "limit reached" if r.limit_reached else (r.error or "")
        lines.append(f"| {r.number} | {r.elim} | {r.solutions} | {note} |")
    lines.append("")
    path = analysis_dir / REPORT_FILE
    path.write_text("\n".join(lines))
    problem.log("report", f"wrote {REPORT_FILE}")
    return path
