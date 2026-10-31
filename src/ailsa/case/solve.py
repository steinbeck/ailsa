"""Run the LSD solver on a problem, dropping correlations only when nothing fits.

The first run uses every correlation in use. When it finds no structure, the solver
may drop one correlation more per run (ELIM 1, 2, 3): a few HMBC peaks of a real
dataset are four-bond couplings or misassignments. Escalation stops one level after
the first run that finds a structure, so the solver drops as little data as possible
while the ranking still sees the near alternatives.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ailsa.case.lsdfile import render
from ailsa.case.model import Problem, RunRecord, utc_now
from ailsa.case.variants import Variant, heteroatom_variants
from ailsa.lsd.runner import LSDRunner

RUNS_DIR = "runs"
MAX_ELIM = 3


@dataclass
class SolveResult:
    """The runs of one ``solve`` call."""

    runs: list[RunRecord]
    budget_reached: bool = False

    @property
    def final(self) -> RunRecord | None:
        return self.runs[-1] if self.runs else None


@dataclass
class _Settings:
    runner: LSDRunner
    analysis_dir: Path
    batch: int
    elim: int | None
    max_solutions: int
    timeout: int
    extra_level: bool
    methyl_4j: bool
    deadline: float


def solve(
    problem: Problem,
    analysis_dir: Path,
    elim: int | None = None,
    max_solutions: int = 20000,
    timeout: int = 600,
    extra_level: bool = True,
    methyl_4j: bool = False,
    variants: bool = True,
    budget: int = 1800,
) -> SolveResult:
    """Run LSD on ``problem``; with ``elim=None`` escalate from 0 to 3 as needed.

    With ``variants``, the alternative heteroatom hybridisations of
    :func:`ailsa.case.variants.heteroatom_variants` are run as well, each with its own
    escalation; the ranking then compares all their structures. Every run gets its own
    directory ``runs/run_NN`` with the LSD input, the solver's output and
    ``solutions.smi``. The runs are appended to ``problem.runs`` under one batch number.
    No new run starts after ``budget`` seconds.
    """
    runner = LSDRunner()
    if runner.lsd_path is None:
        raise RuntimeError("LSD is not installed or not on PATH (check with: ailsa lsd check)")
    settings = _Settings(
        runner=runner,
        analysis_dir=analysis_dir,
        batch=max((r.batch for r in problem.runs), default=0) + 1,
        elim=elim,
        max_solutions=max_solutions,
        timeout=timeout,
        extra_level=extra_level,
        methyl_4j=methyl_4j,
        deadline=time.monotonic() + budget,
    )
    plans = [Variant(label="")]
    if variants:
        plans += heteroatom_variants(problem)
    done: list[RunRecord] = []
    for plan in plans:
        if time.monotonic() >= settings.deadline:
            break
        target = plan.apply(problem) if plan.hyb else problem
        done += _escalate(problem, target, plan.label, settings)
        if any(r.error for r in done):
            break
    return SolveResult(runs=done, budget_reached=time.monotonic() >= settings.deadline)


def _escalate(problem: Problem, target: Problem, label: str, s: _Settings) -> list[RunRecord]:
    """The ELIM escalation for one atom table; records go to ``problem``.

    A run that hits the time limit keeps the structures found until then, and ends the
    escalation: a higher ELIM level only takes longer.
    """
    levels = [s.elim] if s.elim is not None else list(range(MAX_ELIM + 1))
    done: list[RunRecord] = []
    for level in levels:
        left = int(s.deadline - time.monotonic())
        if left <= 0:
            break
        number = len(problem.runs) + 1
        run_dir = s.analysis_dir / RUNS_DIR / f"run_{number:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        lsd_file = run_dir / "compound.lsd"
        lsd_file.write_text(
            render(target, elim=level, max_solutions=s.max_solutions, methyl_4j=s.methyl_4j)
        )
        result = s.runner.run_file(lsd_file, output_dir=run_dir, timeout=min(s.timeout, left))
        timed_out = "timed out" in result.stderr
        count = result.solution_count if (result.return_code == 0 or result.success) else 0
        if timed_out:
            count = _counter(run_dir)
        error = ""
        if count > 0 and not (run_dir / "compound.sol").exists():
            error = "the solver reported structures but wrote no solution file"
        elif result.return_code != 0 and count == 0 and not timed_out:
            error = _lsd_error(result.stdout, result.stderr)
        record = RunRecord(
            number=number,
            batch=s.batch,
            variant=label,
            directory=str(run_dir.relative_to(s.analysis_dir)),
            elim=level,
            solutions=count,
            max_solutions=s.max_solutions,
            limit_reached=count >= s.max_solutions or timed_out,
            success=result.success,
            error=error,
            time=utc_now(),
        )
        problem.runs.append(record)
        done.append(record)
        what = f" ({label})" if label else ""
        stop = " (time limit)" if timed_out else ""
        problem.log("solve", f"run {number}{what}: ELIM {level}, {count} solution(s){stop}")
        if error or timed_out:
            break
        if count > 0:
            found = [r for r in done if r.solutions > 0]
            if not s.extra_level or s.elim is not None or len(found) > 1 or record.limit_reached:
                break
    return done


def _counter(run_dir: Path) -> int:
    """Solutions LSD had written when it was stopped, from its ``solncounter`` file."""
    path = run_dir / "solncounter"
    try:
        return int(path.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return 0


def _lsd_error(stdout: str, stderr: str) -> str:
    """The solver's own error line, if it reported one."""
    for text in (stderr, stdout):
        for line in text.splitlines():
            low = line.lower()
            if "error" in low and "no solution" not in low:
                return line.strip()[:200]
    return ""
