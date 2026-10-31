"""ailsa case: a guided, step-by-step CASE workflow for agents with a small context.

Each command does one deterministic step, prints a short report, and ends with the
command that usually comes next. The state lives in ``<dataset>/analysis/problem.json``.
"""

from __future__ import annotations

import json
import shlex
import sys
import warnings
from collections.abc import Mapping
from pathlib import Path

import click

from ailsa.case import edit as ed
from ailsa.case.checks import check_problem
from ailsa.case.model import PROBLEM_FILE, Problem, dbe, parse_formula


def _analysis_dir(dataset: str, analysis: str | None) -> Path:
    return Path(analysis) if analysis else Path(dataset) / "analysis"


def _load(dataset: str, analysis: str | None) -> tuple[Problem, Path]:
    adir = _analysis_dir(dataset, analysis)
    if not (adir / PROBLEM_FILE).exists():
        click.echo(f"No problem in {adir}. First run: ailsa case setup {shlex.quote(dataset)}")
        sys.exit(1)
    return Problem.load(adir), adir


def _ds(dataset: str, analysis: str | None = None) -> str:
    """The dataset argument (and a non-default analysis folder) for a printed command."""
    text = shlex.quote(dataset)
    return text + (f" --analysis {shlex.quote(analysis)}" if analysis else "")


def _emit(data: Mapping[str, object], output_format: str, text: list[str]) -> None:
    if output_format == "json":
        click.echo(json.dumps(data, indent=1))
    else:
        click.echo("\n".join(text))


ANALYSIS = click.option(
    "--analysis",
    default=None,
    type=click.Path(),
    help="Analysis folder (default: DATASET/analysis).",
)
FORMAT = click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)


@click.group()
def case() -> None:
    """Guided structure elucidation, one step per command.

    \b
    Order:
      ailsa case scan DATASET      which spectra are there
      ailsa case setup DATASET     peaks -> atoms and correlations
      ailsa case check DATASET     what to verify or fix
      ailsa case edit DATASET ...  fix it (repeat check/edit as needed)
      ailsa case solve DATASET     run the LSD solver
      ailsa case rank DATASET      rank the candidate structures
      ailsa case report DATASET    write analysis/final_results.md
    """
    # Reader warnings (e.g. about padded Bruker data) mean nothing to an agent and
    # would only clutter the reports it has to read.
    warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- scan


@case.command("scan")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@FORMAT
def scan_cmd(dataset: str, output_format: str) -> None:
    """List the experiments of a Bruker dataset and check the tools.

    DATASET is the folder with the numbered experiment folders.
    """
    from ailsa.case.scan import KINDS, scan_dataset
    from ailsa.lsd.runner import LSDRunner

    result = scan_dataset(Path(dataset))
    lsd_ok = LSDRunner.is_available() and LSDRunner.is_outlsd_available()
    try:
        from ailsa.prediction.resolver import resolve_c13_predictor

        resolve_c13_predictor()
        predict_ok = True
    except Exception:
        predict_ok = False
    chosen = {k: v.expno for k, v in result.chosen.items()}
    text = [f"Dataset: {result.dataset}", ""]
    text.append("Experiments (kind: chosen expno; others):")
    for kind in KINDS:
        if kind in result.chosen:
            alts = [e.expno for e in result.alternatives(kind)]
            extra = f"   others: {', '.join(alts)}" if alts else ""
            edited = " (edited)" if result.chosen[kind].edited else ""
            text.append(f"  {kind:9} {result.chosen[kind].expno}{edited}{extra}")
    others = sorted({e.kind for e in result.experiments} - set(KINDS))
    if others:
        text.append(f"  not used: {', '.join(others)}")
    text.append("")
    text.append(f"Solvent (acquisition parameters): {result.solvent or 'unknown'}")
    text.append(
        f"Formula file: {result.formula} ({result.formula_file})"
        if result.formula
        else "Formula file: none found"
    )
    text.append(f"LSD solver: {'ok' if lsd_ok else 'MISSING - install LSD and outlsd'}")
    text.append(
        f"13C prediction: {'ok' if predict_ok else 'MISSING - run: ailsa database download'}"
    )
    problems = []
    if "13C" not in result.chosen and "APT" not in result.chosen:
        problems.append("no processed 13C or APT spectrum")
    if "HSQC" not in result.chosen:
        problems.append("no HSQC")
    if "HMBC" not in result.chosen:
        problems.append("no HMBC")
    if problems:
        text.append("WARNING: " + "; ".join(problems))
    text.append("")
    formula = result.formula or "FORMULA"
    text.append(f"NEXT: ailsa case setup {_ds(dataset)} --formula {formula}")
    data = {
        "dataset": str(result.dataset),
        "experiments": [e.to_dict() for e in result.experiments],
        "chosen": chosen,
        "solvent": result.solvent,
        "formula": result.formula,
        "formula_file": result.formula_file,
        "lsd_available": lsd_ok,
        "prediction_available": predict_ok,
        "warnings": problems,
    }
    _emit(data, output_format, text)


# -------------------------------------------------------------------------- setup


@case.command("setup")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@click.option("--formula", default=None, help="Molecular formula, e.g. C10H16O.")
@click.option(
    "--use",
    "use",
    multiple=True,
    metavar="KIND=EXPNO",
    help="Use this experiment for a kind (e.g. --use HSQC=21); EXPNO 'none' skips the kind.",
)
@click.option("--force", is_flag=True, help="Replace an existing problem.")
@ANALYSIS
@FORMAT
def setup_cmd(
    dataset: str,
    formula: str | None,
    use: tuple[str, ...],
    force: bool,
    analysis: str | None,
    output_format: str,
) -> None:
    """Pick peaks and build atoms and correlations from the spectra."""
    from ailsa.case.build import BuildInput, build_problem, choose_experiments
    from ailsa.case.scan import scan_dataset

    adir = _analysis_dir(dataset, analysis)
    if (adir / PROBLEM_FILE).exists() and not force:
        click.echo(
            f"A problem already exists in {adir}. "
            f"Continue with: ailsa case check {_ds(dataset, analysis)}\n"
            "(or start over with --force)"
        )
        sys.exit(1)
    scan = scan_dataset(Path(dataset))
    formula = formula or scan.formula
    if not formula:
        click.echo("No formula given and no formula file found. Add --formula C..H..")
        sys.exit(1)
    try:
        parse_formula(formula)
        overrides = dict(_split_use(u) for u in use)
        experiments = choose_experiments(scan, overrides)
        problem = build_problem(
            BuildInput(
                dataset=Path(dataset).resolve(),
                formula=formula,
                experiments=experiments,
                solvent=scan.solvent,
            )
        )
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)
    problem.save(adir)
    _print_check(problem, dataset, analysis, output_format, header="Setup done.")


def _split_use(text: str) -> tuple[str, str]:
    if "=" not in text:
        raise ValueError(f"--use expects KIND=EXPNO, got {text!r}")
    kind, expno = text.split("=", 1)
    return kind.strip(), expno.strip()


# -------------------------------------------------------------------------- check


@case.command("check")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@ANALYSIS
@FORMAT
def check_cmd(dataset: str, analysis: str | None, output_format: str) -> None:
    """Show the atoms, the checks, and what to verify."""
    problem, _ = _load(dataset, analysis)
    _print_check(problem, dataset, analysis, output_format)


def _atom_rows(problem: Problem) -> list[str]:
    rows = []
    bonded = {b.b: b.a for b in problem.bonds} | {b.a: b.b for b in problem.bonds}
    for a in problem.atoms:
        if a.copy_of is not None:
            continue
        group = problem.group_of(a.id)
        hs = ", ".join(f"{h:.2f}" for h in a.h_shifts) or "-"
        shift = f"{a.shift:7.2f}" if a.shift is not None else "       "
        extra = (
            f"  x{len(group)} ({' '.join('C' + str(g) for g in group)})" if len(group) > 1 else ""
        )
        if a.id in bonded:
            extra += f"  bonded to {problem.atom(bonded[a.id]).label}"
        mult = (
            a.mult
            if a.element == "C"
            else (f"{a.element}H{a.hydrogens}" if a.hydrogens else a.element)
        )
        rows.append(f"  {a.label:5} {shift}  {mult:4} sp{a.hyb}  H: {hs}{extra}")
    return rows


def _print_check(
    problem: Problem, dataset: str, analysis: str | None, output_format: str, header: str = ""
) -> None:
    result = check_problem(problem)
    counts = parse_formula(problem.formula)
    n_c = len(problem.carbons())
    hetero = len(problem.atoms) - n_c
    used = [c for c in problem.correlations if c.use]
    hmbc = [c for c in problem.correlations if c.kind == "HMBC"]
    cosy = [c for c in problem.correlations if c.kind == "COSY"]
    text = [header] if header else []
    text.append(
        f"Problem: {problem.formula}, DBE {dbe(counts):g}, {len(problem.atoms)} atoms "
        f"({n_c} C, {hetero} other), solvent {problem.solvent or 'unknown'}"
    )
    text.append("Spectra: " + ", ".join(f"{k} {v}" for k, v in problem.spectra.items()))
    text.append("")
    text.append("Atoms (label, 13C shift, type, hybridisation, 1H shifts):")
    text += _atom_rows(problem)
    text.append(
        f"Correlations: {sum(c.use for c in hmbc)} HMBC in use, "
        f"{sum(not c.use for c in hmbc)} not used; {sum(c.use for c in cosy)} COSY in use "
        f"(of {len(cosy)}). List: ailsa case show {_ds(dataset, analysis)} --correlations"
    )
    text.append(
        f"Checks: hydrogens {result.facts.get('hydrogens')} (formula {counts.get('H', 0)}); "
        f"sp2 atoms {result.facts.get('sp2')}; rings {result.facts.get('rings'):g}"
    )
    if problem.unassigned:
        text.append("")
        text.append("Peaks with no atom (may point to a missing carbon):")
        for u in problem.unassigned[:8]:
            text.append(f"  {u.kind} {u.c_shift}/{u.h_shift}: {u.text}")
    text.append("")
    if result.errors:
        text.append("ERRORS (fix these before solving):")
        text += [f"  - {e}" for e in result.errors]
        text.append("")
    if problem.assumptions:
        text.append("TO VERIFY (assumed by setup; change only if the data say otherwise):")
        for i, a in enumerate(problem.assumptions, start=1):
            text.append(f"  {i}. {a.text}")
            if a.fix:
                fix = a.fix.replace("DATASET", _ds(dataset, analysis))
                command, _, hint = fix.partition("  (")
                hint = f"  ({hint}" if hint else ""
                text.append(f'     change: {command} --reason "..."{hint}')
        text.append("")
    if result.errors:
        text.append(
            f'NEXT: fix the errors with ailsa case edit {_ds(dataset, analysis)} ... --reason "..."'
        )
    else:
        text.append(f"NEXT: ailsa case solve {_ds(dataset, analysis)}")
    data = {
        "ready": result.ready,
        "errors": result.errors,
        "facts": result.facts,
        "assumptions": [a.model_dump() for a in problem.assumptions],
        "atoms": [a.model_dump() for a in problem.atoms],
        "correlations_used": len(used),
        "unassigned": [u.model_dump() for u in problem.unassigned],
    }
    _emit(data, output_format, text)


# --------------------------------------------------------------------------- show


@case.command("show")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@click.option("--correlations", is_flag=True, help="List every HMBC/COSY correlation.")
@click.option("--history", is_flag=True, help="List every change made so far.")
@ANALYSIS
@FORMAT
def show_cmd(
    dataset: str, correlations: bool, history: bool, analysis: str | None, output_format: str
) -> None:
    """Show correlations or the change history."""
    problem, _ = _load(dataset, analysis)
    text: list[str] = []
    if correlations or not history:
        text.append("Correlations (id, use, carbon(s) <- proton on, shifts C/H, SNR, note):")
        for c in problem.correlations:
            xs = " ".join(
                problem.atom(x).label for x in c.x if any(a.id == x for a in problem.atoms)
            )
            flag = "yes" if c.use else "no "
            label = problem.atom(c.y).label if any(a.id == c.y for a in problem.atoms) else "?"
            text.append(
                f"  {c.id:5} {flag} {c.kind} {xs} <- H on {label}   {c.c_shift}/{c.h_shift}"
                f"  snr {c.snr or 0:.0f}  {c.reason}"
            )
    if history:
        text.append("History:")
        for h in problem.history:
            text.append(
                f"  {h.time} {h.action}: {h.detail}" + (f" ({h.reason})" if h.reason else "")
            )
    data = {
        "correlations": [c.model_dump() for c in problem.correlations],
        "history": [h.model_dump() for h in problem.history],
    }
    _emit(data, output_format, text)


# --------------------------------------------------------------------------- edit


@case.command("edit")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@click.option("--mult", multiple=True, metavar="ID=TYPE", help="Carbon type: C, CH, CH2 or CH3.")
@click.option("--hyb", multiple=True, metavar="ID=HYB", help="Hybridisation: sp, sp2 or sp3.")
@click.option("--copies", multiple=True, metavar="ID=N", help="Number of equivalent carbons.")
@click.option("--add-carbon", multiple=True, metavar="SHIFT[:TYPE[:HYB]]", help="Add a carbon.")
@click.option("--remove", multiple=True, metavar="ID", help="Remove a carbon (noise, impurity).")
@click.option("--hetero-h", multiple=True, metavar="ID=N", help="Hydrogens on an O/N/S atom.")
@click.option("--drop", default=None, metavar="IDS", help="Stop using correlations, e.g. B3,B7.")
@click.option("--use", "use_ids", default=None, metavar="IDS", help="Use correlations again.")
@click.option("--bond", multiple=True, metavar="A-B", help="Require a bond between two atoms.")
@click.option("--unbond", multiple=True, metavar="A-B", help="Remove a required bond.")
@click.option("--small-rings/--no-small-rings", default=None, help="Allow 3- and 4-membered rings.")
@click.option("--reason", required=True, help="Why: the observation behind the change.")
@ANALYSIS
@FORMAT
def edit_cmd(
    dataset: str,
    mult: tuple[str, ...],
    hyb: tuple[str, ...],
    copies: tuple[str, ...],
    add_carbon: tuple[str, ...],
    remove: tuple[str, ...],
    hetero_h: tuple[str, ...],
    drop: str | None,
    use_ids: str | None,
    bond: tuple[str, ...],
    unbond: tuple[str, ...],
    small_rings: bool | None,
    reason: str,
    analysis: str | None,
    output_format: str,
) -> None:
    """Change the problem; every change is logged with its reason."""
    problem, adir = _load(dataset, analysis)
    done: list[str] = []
    try:
        for spec in remove:
            done.append(ed.remove_atom(problem, spec))
        for spec in add_carbon:
            done.append(ed.add_carbon(problem, spec))
        for spec in mult:
            done.append(ed.set_mult(problem, spec))
        for spec in hyb:
            done.append(ed.set_hyb(problem, spec))
        for spec in copies:
            done.append(ed.set_copies(problem, spec))
        for spec in hetero_h:
            done.append(ed.set_hetero_h(problem, spec))
        if drop:
            done.append(ed.set_use(problem, drop, use=False))
        if use_ids:
            done.append(ed.set_use(problem, use_ids, use=True))
        for spec in bond:
            done.append(ed.set_bond(problem, spec, present=True))
        for spec in unbond:
            done.append(ed.set_bond(problem, spec, present=False))
        if small_rings is not None:
            problem.small_rings_allowed = small_rings
            done.append("small rings " + ("allowed" if small_rings else "excluded"))
    except ed.EditError as exc:
        click.echo(f"Error: {exc}. Nothing was changed.")
        sys.exit(1)
    if not done:
        click.echo("Nothing to change: give at least one option (see ailsa case edit --help).")
        sys.exit(1)
    for d in done:
        problem.log("edit", d, reason)
    problem.save(adir)
    _print_check(problem, dataset, analysis, output_format, header="Changed: " + "; ".join(done))


# -------------------------------------------------------------------------- solve


@case.command("solve")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--elim",
    type=click.IntRange(0, 3),
    default=None,
    help="Correlations the solver may drop (default: as few as needed, 0-3).",
)
@click.option("--max-solutions", default=2000, show_default=True, help="Stop after this many.")
@click.option("--timeout", default=600, show_default=True, help="Seconds per solver run.")
@click.option(
    "--methyl-4j", is_flag=True, help="Let HMBC from methyl protons to sp2 carbons span four bonds."
)
@ANALYSIS
@FORMAT
def solve_cmd(
    dataset: str,
    elim: int | None,
    max_solutions: int,
    timeout: int,
    methyl_4j: bool,
    analysis: str | None,
    output_format: str,
) -> None:
    """Run the LSD solver; drop correlations only when no structure fits."""
    from ailsa.case.solve import solve

    problem, adir = _load(dataset, analysis)
    result = check_problem(problem)
    if not result.ready:
        click.echo("Cannot solve yet. Fix these first (see ailsa case check):")
        for e in result.errors:
            click.echo(f"  - {e}")
        sys.exit(1)
    try:
        outcome = solve(
            problem,
            adir,
            elim=elim,
            max_solutions=max_solutions,
            timeout=timeout,
            methyl_4j=methyl_4j,
        )
    except RuntimeError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)
    problem.save(adir)
    text = ["Solver runs:"]
    for r in outcome.runs:
        note = " (limit reached: the list is incomplete)" if r.limit_reached else ""
        note += f" ERROR: {r.error}" if r.error else ""
        text.append(
            f"  run {r.number}: solver may ignore up to {r.elim} correlation(s) "
            f"-> {r.solutions} structure(s){note}"
        )
    found = sum(r.solutions for r in outcome.runs)
    if found and not any(r.limit_reached for r in outcome.runs):
        text.append("Every structure that fits these runs is in the list.")
    text.append("")
    if any(r.error for r in outcome.runs):
        text.append(
            "The solver rejected the input. Check the atoms: ailsa case check "
            + _ds(dataset, analysis)
        )
        text.append(f"NEXT: ailsa case check {_ds(dataset, analysis)}")
    elif found == 0:
        text.append(
            "No structure fits even when the solver may drop three correlations. Something in "
            "the atom table is wrong (a multiplicity, a hybridisation, the symmetry, or the "
            "hydrogens on O/N), or several correlations are wrong."
        )
        text.append(f"NEXT: ailsa case check {_ds(dataset, analysis)}  (then edit and solve again)")
    else:
        text.append(f"NEXT: ailsa case rank {_ds(dataset, analysis)}")
    data = {
        "runs": [r.model_dump() for r in outcome.runs],
        "structures": found,
        "error": next((r.error for r in outcome.runs if r.error), ""),
    }
    _emit(data, output_format, text)


# --------------------------------------------------------------------------- rank


@case.command("rank")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@click.option("--top", default=10, show_default=True, help="Number of candidates to list.")
@ANALYSIS
@FORMAT
def rank_cmd(dataset: str, top: int, analysis: str | None, output_format: str) -> None:
    """Rank the structures of the latest solve by predicted 13C shifts."""
    from ailsa.case.rank import rank_problem

    problem, adir = _load(dataset, analysis)
    try:
        result = rank_problem(problem, adir, top=top)
    except (ValueError, RuntimeError) as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)
    problem.save(adir)
    text = [
        f"Top {len(result.candidates)} of {result.distinct} distinct structures "
        f"({result.total} solutions from runs {', '.join(map(str, result.runs))}).",
        "MAE = mean |predicted - observed| 13C shift over all carbons, atom by atom; "
        "lower is better.",
        "",
        "Rank  MAE   max-error(atom)  unexplained HMBC   SMILES",
    ]
    for c in result.candidates:
        viol = ",".join(c.violated) or "-"
        text.append(
            f"{c.rank:4}  {c.mae:4.2f}  {c.max_error:5.1f} ({c.worst_atom:4})  "
            f"{viol:16}  {c.smiles}"
        )
    if result.candidates:
        best = result.candidates[0]
        ident = best.identity or {}
        text.append("")
        in_db = (
            "in the reference database" if ident.get("matched") else "not in the reference database"
        )
        text.append(f"Best candidate is {in_db}.")
        if len(result.candidates) > 1:
            gap = result.candidates[1].mae - best.mae
            text.append(f"Margin to rank 2: {gap:.2f} ppm MAE.")
    text.append("")
    text.append(f'NEXT: ailsa case report {_ds(dataset, analysis)} --note "your assessment"')
    data = {
        "runs": result.runs,
        "total_solutions": result.total,
        "candidates": [c.__dict__ for c in result.candidates],
    }
    _emit(data, output_format, text)


# ------------------------------------------------------------------------- report


@case.command("report")
@click.argument("dataset", type=click.Path(exists=True, file_okay=False))
@click.option("--note", multiple=True, help="Your assessment (repeatable).")
@ANALYSIS
@FORMAT
def report_cmd(
    dataset: str, note: tuple[str, ...], analysis: str | None, output_format: str
) -> None:
    """Write analysis/final_results.md from the problem and the ranking."""
    from ailsa.case.report import write_report

    problem, adir = _load(dataset, analysis)
    try:
        path = write_report(problem, adir, list(note))
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        sys.exit(1)
    problem.save(adir)
    _emit({"report": str(path)}, output_format, [f"Report written: {path}", "DONE"])
