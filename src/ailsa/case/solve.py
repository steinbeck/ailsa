"""Run the LSD solver on a problem, dropping correlations only when nothing fits.

The first run uses every correlation in use. When it finds no structure, the solver
may drop one correlation more per run (ELIM 1, 2, 3): a few HMBC peaks of a real
dataset are four-bond couplings or misassignments. Escalation stops at the first run
that finds a structure, so the solver drops as little data as possible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ailsa.case.lsdfile import render
from ailsa.case.model import Problem, RunRecord, utc_now
from ailsa.lsd.runner import LSDRunner

RUNS_DIR = "runs"
MAX_ELIM = 3


@dataclass
class SolveResult:
    """The runs of one ``solve`` call."""

    runs: list[RunRecord]

    @property
    def final(self) -> RunRecord | None:
        return self.runs[-1] if self.runs else None


def solve(
    problem: Problem,
    analysis_dir: Path,
    elim: int | None = None,
    max_solutions: int = 2000,
    timeout: int = 600,
    extra_level: bool = True,
    methyl_4j: bool = False,
) -> SolveResult:
    """Run LSD on ``problem``; with ``elim=None`` escalate from 0 to 3 as needed.

    Every run gets its own directory ``runs/run_NN`` with the LSD input, the solver's
    output and ``solutions.smi``. The runs are appended to ``problem.runs``.
    """
    runner = LSDRunner()
    if runner.lsd_path is None:
        raise RuntimeError("LSD is not installed or not on PATH (check with: ailsa lsd check)")
    levels = [elim] if elim is not None else list(range(MAX_ELIM + 1))
    batch = max((r.batch for r in problem.runs), default=0) + 1
    done: list[RunRecord] = []
    for level in levels:
        number = len(problem.runs) + 1
        run_dir = analysis_dir / RUNS_DIR / f"run_{number:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        lsd_file = run_dir / "compound.lsd"
        lsd_file.write_text(
            render(problem, elim=level, max_solutions=max_solutions, methyl_4j=methyl_4j)
        )
        result = runner.run_file(lsd_file, output_dir=run_dir, timeout=timeout)
        count = result.solution_count if result.return_code == 0 or result.success else 0
        error = ""
        if not result.success and count > 0:
            error = "solutions found but not converted to SMILES"
        elif result.return_code not in (0,) and count == 0:
            error = _lsd_error(result.stdout, result.stderr)
        record = RunRecord(
            number=number,
            batch=batch,
            directory=str(run_dir.relative_to(analysis_dir)),
            elim=level,
            solutions=count,
            max_solutions=max_solutions,
            limit_reached=count >= max_solutions,
            success=result.success,
            error=error,
            time=utc_now(),
        )
        problem.runs.append(record)
        done.append(record)
        problem.log("solve", f"run {number}: ELIM {level}, {count} solution(s)")
        if error:
            break
        if count > 0:
            found = [r for r in done if r.solutions > 0]
            if not extra_level or elim is not None or len(found) > 1 or record.limit_reached:
                break
    return SolveResult(runs=done)


def _lsd_error(stdout: str, stderr: str) -> str:
    """The solver's own error line, if it reported one."""
    for text in (stderr, stdout):
        for line in text.splitlines():
            low = line.lower()
            if "error" in low and "no solution" not in low:
                return line.strip()[:200]
    return ""
