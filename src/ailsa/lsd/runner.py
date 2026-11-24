"""LSD (Logic for Structure Determination) runner."""

import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from ailsa.lsd.generator import LSDInputGenerator
from ailsa.lsd.models import LSDProblem


def _invoke_outlsd(
    outlsd_path: Path, sol_file: Path, output_dir: Path
) -> "Path | None":
    """Convert .sol to SMILES via outlsd.

    Correct call: outlsd 5 < compound.sol > solutions.smi
    Source: orchestrator.py _run_outlsd (the correct implementation).
    Both LSDRunner._run_outlsd and PyLSDOrchestrator._run_outlsd
    delegate here so there is a single implementation.

    Args:
        outlsd_path: Absolute path to outlsd binary.
        sol_file: Path to the .sol file produced by LSD.
        output_dir: Directory where solutions.smi will be written.

    Returns:
        Path to solutions.smi if conversion succeeded, else None.
    """
    smiles_file = output_dir / "solutions.smi"
    try:
        with sol_file.open("r") as fh:
            proc = subprocess.run(
                [str(outlsd_path), "5"],  # "5" = SMILES mode (required)
                stdin=fh,                  # .sol file (NOT the .lsd file)
                capture_output=True,
                text=True,
                timeout=30,
                cwd=output_dir,
            )
        stdout = proc.stdout.strip()
        # Fail-loud: detect known error patterns before writing to disk
        if not stdout:
            raise RuntimeError(
                "outlsd produced no output — .sol file may be incomplete "
                "(likely cause: ring3/ring4 filter files missing from output_dir)"
            )
        if "This is not a file for OUTLSD" in stdout:
            raise RuntimeError(
                f"outlsd rejected .sol file: {stdout[:200]!r}. "
                "Likely cause: ring3/ring4 filter files missing from output_dir, "
                "causing LSD to produce a partial .sol (input echo only). "
                "Fix: ensure _execute_lsd copies filter files (FIX-01A)."
            )
        if stdout.startswith("outlsd:"):
            raise RuntimeError(f"outlsd error: {stdout[:200]!r}")
        # Validate first non-empty line is parseable SMILES (structural guard against
        # unknown outlsd error output that slips past the string checks above).
        lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
        if not lines:
            raise RuntimeError("outlsd produced no parseable lines")
        try:
            from rdkit import Chem, RDLogger

            RDLogger.DisableLog("rdApp.*")
            first_smiles = lines[0].split()[0]
            if Chem.MolFromSmiles(first_smiles) is None:
                raise RuntimeError(
                    f"outlsd output is not valid SMILES: {lines[0][:100]!r}. "
                    "Full output may be an unrecognised error message."
                )
        except ImportError:
            # RDKit not available — string checks above are the last line of defence
            pass
        # Output passes all checks — write to disk
        smiles_file.write_text(proc.stdout)
        return smiles_file
    except RuntimeError:
        raise  # Propagate fail-loud errors to _execute_lsd exception handler
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "outlsd timed out after 30 seconds — .sol file may be very large"
        ) from exc
    except Exception:
        pass
    return None


_MAXS = re.compile(r"^\s*MAXS\s+(\d+)", re.IGNORECASE)
_TIME_STOP = re.compile(
    # LSD 3.5.3 on MAXT: "Aborted by user (time limit) after N solutions." (stderr)
    r"aborted by user \(time limit\)"
    r"|(time limit|maximum time|maxt)[^\n]*(reached|exceeded|elapsed)"
    r"|(reached|exceeded)[^\n]*(time limit|maximum time|maxt)",
    re.IGNORECASE,
)


RESULT_FILES = ("solutions.smi", "solncounter")


def result_file_names(stem: str) -> tuple[str, ...]:
    """Files one solve leaves behind as its result: ``<stem>.sol`` plus RESULT_FILES."""
    return (f"{stem}.sol", *RESULT_FILES)


def clear_solver_outputs(folder: Path | str, stem: str, extra: tuple[str, ...] = ()) -> None:
    """Remove an earlier solve's result files so they can never pose as the next solve's.

    A re-solve in the same folder that fails (input error, no solution, time stop) would
    otherwise leave the previous ``.sol``, ``solutions.smi`` and ``solncounter`` in place.
    """
    for name in (*result_file_names(stem), *extra):
        (Path(folder) / name).unlink(missing_ok=True)


def read_solncounter(run_dir: Path | str) -> int | None:
    """Solutions LSD had written when it stopped, from its ``solncounter`` file."""
    try:
        return int((Path(run_dir) / "solncounter").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None


def maxs_limit(lsd_text: str) -> int | None:
    """The first ``MAXS <n>`` command of an LSD input (comment lines ignored)."""
    for line in lsd_text.splitlines():
        if line.lstrip().startswith(";"):
            continue
        match = _MAXS.match(line)
        if match:
            return int(match.group(1))
    return None


def classify_outcome(
    *,
    started: bool,
    blocked: bool,
    error_line: str | None,
    timed_out: bool,
    count: int,
    limit: int | None,
    no_solution_text: bool,
    sol_exists: bool,
    smiles_ok: bool | None,
    conversion_skipped: bool,
) -> tuple[str, str | None]:
    """Typed solver outcome and, where the SMILES file is absent, the reason (REC-14)."""
    if not started:
        return "not_run", "not_run"
    if blocked:
        return "blocked", "blocked"
    if error_line:
        return "error", "error"
    if timed_out:
        return "timeout", "timeout"
    if count <= 0 or no_solution_text:
        return "no_solution", "no_solution"
    reason: str | None = None
    if conversion_skipped:
        reason = "conversion_skipped_large"
    elif smiles_ok is False or not sol_exists:
        reason = "conversion_failed"
    if limit is not None and count >= limit:
        return "limit_reached", reason
    return "solutions", reason


@dataclass
class LSDResult:
    """Result from LSD execution.

    Attributes:
        success: Whether LSD completed successfully
        solution_count: Number of solutions found
        solutions: List of solution file contents
        output_files: Paths to generated output files
        stdout: Standard output from LSD
        stderr: Standard error from LSD
        return_code: Process return code
        input_file: Path to the input file used
        output_dir: Directory containing output files
    """

    success: bool
    solution_count: int
    solutions: list[str] = field(default_factory=list)
    output_files: list[Path] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    input_file: Path | None = None
    output_dir: Path | None = None
    # Added for the run record (every field has a default; existing semantics unchanged).
    elapsed_s: float = 0.0
    timed_out: bool = False
    partial_count: int | None = None
    limit: int | None = None
    outcome: str = "not_run"
    error_line: str | None = None
    smiles_absent_reason: str | None = None
    lsd_version: str | None = None
    lsd_sha256: str | None = None
    found_count: int = 0

    def summary(self) -> str:
        """Return a summary of the result."""
        status = "Success" if self.success else "Failed"
        lines = [
            f"LSD Result: {status}",
            f"  Solutions found: {self.solution_count}",
            f"  Return code: {self.return_code}",
        ]
        if self.output_files:
            lines.append(f"  Output files: {len(self.output_files)}")
        if self.stderr and not self.success:
            lines.append(f"  Error: {self.stderr[:200]}")
        return "\n".join(lines)


class LSDRunner:
    """Execute LSD solver.

    Manages execution of the LSD program as a subprocess,
    handling input file creation and output file parsing.

    After LSD runs successfully, automatically runs outlsd to convert
    solutions to SMILES format for downstream ranking.
    """

    # Common locations to search for LSD
    SEARCH_PATHS = [
        "/usr/local/bin/lsd",
        "/usr/bin/lsd",
        "~/.local/bin/lsd",
        "~/bin/lsd",  # Common user bin directory
        "~/LSD/lsd",
        "~/PyLSD/LSD/lsd",
        "~/LSD-3.5.3/lsd",  # Default extraction location
    ]

    # Common locations for outlsd
    OUTLSD_SEARCH_PATHS = [
        "/usr/local/bin/outlsd",
        "/usr/bin/outlsd",
        "~/.local/bin/outlsd",
        "~/bin/outlsd",
        "~/LSD/outlsd",
        "~/PyLSD/LSD/outlsd",
        "~/LSD-3.5.3/outlsd",
    ]

    def __init__(self, lsd_path: str | Path | None = None):
        """Initialize with path to LSD executable.

        Args:
            lsd_path: Path to LSD executable. If None, will search
                     in PATH and common locations.
        """
        if lsd_path:
            self.lsd_path = Path(lsd_path).expanduser()
        else:
            self.lsd_path = self._find_lsd()
        self.outlsd_path = self._find_outlsd()

    def run(
        self,
        problem: LSDProblem,
        output_dir: Path | None = None,
        timeout: int = 60,
        keep_files: bool = False,
    ) -> LSDResult:
        """Run LSD on problem and return results.

        Args:
            problem: LSD problem to solve
            output_dir: Directory for output files. If None, uses temp dir.
            timeout: Maximum execution time in seconds
            keep_files: If True, don't clean up temp files

        Returns:
            LSDResult with solution information

        Raises:
            FileNotFoundError: If LSD executable not found
            RuntimeError: If LSD execution fails critically
        """
        if self.lsd_path is None:
            raise FileNotFoundError(
                "LSD executable not found. Install LSD or provide path."
            )

        # Create output directory
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            cleanup = False
        else:
            output_dir = Path(tempfile.mkdtemp(prefix="lsd_"))
            cleanup = not keep_files

        try:
            # Write input file
            input_file = output_dir / f"{problem.name}.lsd"
            LSDInputGenerator.write_file(problem, input_file)

            # Run LSD
            result = self._execute_lsd(input_file, output_dir, timeout)
            result.input_file = input_file
            result.output_dir = output_dir

            return result

        finally:
            if cleanup and output_dir.exists():
                shutil.rmtree(output_dir, ignore_errors=True)

    def run_file(
        self,
        input_file: Path | str,
        output_dir: Path | None = None,
        timeout: int = 60,
    ) -> LSDResult:
        """Run LSD on an existing input file.

        Args:
            input_file: Path to LSD input file
            output_dir: Directory for output files
            timeout: Maximum execution time in seconds

        Returns:
            LSDResult with solution information
        """
        if self.lsd_path is None:
            raise FileNotFoundError(
                "LSD executable not found. Install LSD or provide path."
            )

        input_file = Path(input_file)
        if not input_file.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        if output_dir is None:
            output_dir = input_file.parent

        result = self._execute_lsd(input_file, output_dir, timeout)
        result.input_file = input_file
        result.output_dir = output_dir

        return result

    def _execute_lsd(
        self,
        input_file: Path,
        output_dir: Path,
        timeout: int,
    ) -> LSDResult:
        """Execute LSD subprocess.

        Args:
            input_file: Path to input file
            output_dir: Working directory
            timeout: Timeout in seconds

        Returns:
            LSDResult with execution information
        """
        started_at = time.monotonic()
        limit: int | None = None
        try:
            limit = maxs_limit(input_file.read_text(errors="replace"))
        except OSError:
            limit = None
        try:
            # LSD command: lsd compound.lsd (file-argument mode, relative path)
            # LSD-3.4.9 writes {stem}.sol to CWD only when given a RELATIVE path.
            # With an absolute path, LSD runs but does not write a .sol file.
            # Solution: copy input file to output_dir if not already there, then
            # invoke LSD with the filename only (relative path in CWD=output_dir).
            if input_file.parent.resolve() != output_dir.resolve():
                dest = output_dir / input_file.name
                shutil.copy2(str(input_file), str(dest))
                lsd_input_name = input_file.name
            else:
                lsd_input_name = input_file.name
            # Copy bundled ring3/ring4 filter files so DEFF F1 "ring3" / DEFF F2 "ring4" resolve.
            # Unconditional - matches write_file() behavior; idempotent if already present.
            LSDInputGenerator._write_filter_files(output_dir)
            # Result files of an earlier solve here must not pose as this solve's result.
            clear_solver_outputs(output_dir, input_file.stem)
            proc = subprocess.run(
                [str(self.lsd_path), lsd_input_name],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=output_dir,
                stdin=subprocess.DEVNULL,
            )
            elapsed = time.monotonic() - started_at
            combined = proc.stdout + "\n" + proc.stderr

            # An input error ("error 420 - 6 commands read" plus an explanation on the next
            # line) must be reported as such, not as a failed SMILES conversion.
            lsd_error = self._lsd_error(combined)
            if lsd_error:
                outcome, absent = classify_outcome(
                    started=True, blocked=False, error_line=lsd_error, timed_out=False,
                    count=0, limit=limit, no_solution_text=False, sol_exists=False,
                    smiles_ok=None, conversion_skipped=False,
                )
                return LSDResult(
                    success=False,
                    solution_count=0,
                    stdout=proc.stdout,
                    stderr=lsd_error,
                    return_code=proc.returncode or 1,
                    elapsed_s=elapsed,
                    limit=limit,
                    outcome=outcome,
                    error_line=lsd_error,
                    smiles_absent_reason=absent,
                )

            # Find output files
            output_files = list(output_dir.glob("*.sol")) + list(output_dir.glob("*.out"))

            # Count solutions from output (check both stdout and stderr)
            solution_count = self._count_solutions(proc.stdout, output_files, proc.stderr)

            # Read solution contents
            solutions = []
            for sol_file_item in sorted(output_dir.glob("*.sol")):
                solutions.append(sol_file_item.read_text())

            # .sol file is written to output_dir with the input file's stem
            sol_file = output_dir / f"{input_file.stem}.sol"

            # LSD's own time limit (MAXT) stops it with a partial result; never "0 solutions".
            time_stop = bool(_TIME_STOP.search(combined))
            if time_stop:
                partial = read_solncounter(output_dir)
                partial = solution_count if partial is None else partial
                outcome, absent = classify_outcome(
                    started=True, blocked=False, error_line=None, timed_out=True,
                    count=partial, limit=limit, no_solution_text=False,
                    sol_exists=sol_file.exists(), smiles_ok=None, conversion_skipped=False,
                )
                return LSDResult(
                    success=False,
                    solution_count=solution_count,
                    solutions=solutions,
                    output_files=output_files,
                    stdout=proc.stdout,
                    stderr=proc.stderr,
                    return_code=proc.returncode,
                    elapsed_s=elapsed,
                    timed_out=True,
                    partial_count=partial,
                    limit=limit,
                    outcome=outcome,
                    smiles_absent_reason=absent,
                    found_count=partial,
                )

            # Run outlsd to convert solutions to SMILES if available
            smiles_path: Path | None = None
            conversion_error: str | None = None
            if sol_file.exists() and solution_count > 0 and self.outlsd_path:
                try:
                    smiles_path = self._run_outlsd(output_dir, input_file)
                except RuntimeError as exc:
                    conversion_error = str(exc)
            # Re-scan for output files to include .smi
            output_files = (
                list(output_dir.glob("*.sol"))
                + list(output_dir.glob("*.out"))
                + list(output_dir.glob("*.smi"))
            )
            no_solution_text = "No solution found" in combined
            outcome, absent = classify_outcome(
                started=True, blocked=False, error_line=None, timed_out=False,
                count=solution_count, limit=limit, no_solution_text=no_solution_text,
                sol_exists=sol_file.exists(),
                smiles_ok=(smiles_path is not None) if solution_count > 0 else None,
                conversion_skipped=False,
            )
            if conversion_error is not None:
                # Old contract: a fail-loud conversion error reads as a failed run.
                return LSDResult(
                    success=False,
                    solution_count=0,
                    stderr=conversion_error,
                    return_code=-1,
                    elapsed_s=elapsed,
                    limit=limit,
                    outcome=outcome,
                    smiles_absent_reason="conversion_failed",
                    found_count=solution_count,
                )
            # Success requires .sol file AND SMILES conversion (no silent false-positive)
            success = sol_file.exists() and smiles_path is not None

            return LSDResult(
                success=success,
                solution_count=solution_count,
                solutions=solutions,
                output_files=output_files,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
                elapsed_s=elapsed,
                limit=limit,
                outcome=outcome,
                smiles_absent_reason=absent,
                found_count=solution_count,
            )

        except subprocess.TimeoutExpired:
            partial = read_solncounter(output_dir)
            count = partial if partial is not None else 0
            return LSDResult(
                success=False,
                solution_count=0,
                stderr=f"LSD execution timed out after {timeout} seconds",
                return_code=-1,
                elapsed_s=time.monotonic() - started_at,
                timed_out=True,
                partial_count=count,
                limit=limit,
                outcome="timeout",
                smiles_absent_reason="timeout",
                found_count=count,
            )

        except Exception as e:
            return LSDResult(
                success=False,
                solution_count=0,
                stderr=str(e),
                return_code=-1,
                elapsed_s=time.monotonic() - started_at,
                limit=limit,
                outcome="error",
                error_line=str(e)[:300],
                smiles_absent_reason="error",
            )

    def _count_solutions(
        self, stdout: str, output_files: list[Path], stderr: str = ""
    ) -> int:
        """Count number of solutions from LSD output.

        Args:
            stdout: LSD standard output
            output_files: List of output files
            stderr: LSD standard error (LSD often writes here)

        Returns:
            Number of solutions found
        """
        import re

        # Try to parse from stdout and stderr (LSD writes to stderr)
        for text in [stdout, stderr]:
            for line in text.split("\n"):
                if "solution" in line.lower():
                    # Try to extract number
                    match = re.search(r"(\d+)\s+solution", line.lower())
                    if match:
                        return int(match.group(1))

        # Fallback: the solution counter LSD writes next to its output. A .sol file alone
        # proves nothing: LSD writes one (the input echo) even when it finds no structure.
        for f in output_files:
            counter = f.parent / "solncounter"
            if counter.exists():
                try:
                    return int(counter.read_text().split()[0])
                except (ValueError, IndexError):
                    return 0
        return 0

    @staticmethod
    def _lsd_error(text: str) -> str:
        """LSD's own error report ("LSD error 420: <explanation>"), or "" if there is none."""
        import re

        lines = text.splitlines()
        for i, line in enumerate(lines):
            match = re.match(r"\s*error (\d+)\b", line)
            if match:
                detail = lines[i + 1].strip() if i + 1 < len(lines) else ""
                return f"LSD error {match.group(1)}: {detail}".rstrip(": ")
        return ""

    @classmethod
    def _find_lsd(cls) -> Path | None:
        """Try to find LSD executable.

        Returns:
            Path to LSD executable, or None if not found
        """
        # Check PATH first
        lsd_in_path = shutil.which("lsd")
        if lsd_in_path:
            return Path(lsd_in_path)

        # Check common locations
        for path_str in cls.SEARCH_PATHS:
            path = Path(path_str).expanduser()
            if path.exists() and path.is_file():
                return path

        return None

    @classmethod
    def _find_outlsd(cls) -> Path | None:
        """Try to find outlsd executable for SMILES conversion.

        Returns:
            Path to outlsd executable, or None if not found
        """
        # Check PATH first
        outlsd_in_path = shutil.which("outlsd")
        if outlsd_in_path:
            return Path(outlsd_in_path)

        # Check common locations
        for path_str in cls.OUTLSD_SEARCH_PATHS:
            path = Path(path_str).expanduser()
            if path.exists() and path.is_file():
                return path

        return None

    def _run_outlsd(self, output_dir: Path, input_file: Path) -> "Path | None":
        """Run outlsd to convert solutions to SMILES.

        Delegates to the module-level _invoke_outlsd helper.
        Correct call: outlsd 5 < {stem}.sol > solutions.smi

        Args:
            output_dir: Directory containing the .sol file from LSD.
            input_file: Original LSD input file (used to derive .sol filename).

        Returns:
            Path to solutions.smi if conversion succeeded, else None.
        """
        if self.outlsd_path is None:
            return None
        sol_file = output_dir / f"{input_file.stem}.sol"
        if not sol_file.exists():
            return None
        return _invoke_outlsd(self.outlsd_path, sol_file, output_dir)

    @classmethod
    def is_available(cls) -> bool:
        """Check if LSD is available on the system.

        Returns:
            True if LSD executable is found
        """
        return cls._find_lsd() is not None

    @classmethod
    def is_outlsd_available(cls) -> bool:
        """Check if outlsd (SMILES converter) is available.

        Returns:
            True if outlsd executable is found
        """
        return cls._find_outlsd() is not None

    @classmethod
    def get_version(cls) -> str | None:
        """Get LSD version if available.

        Returns:
            Version string, or None if not available
        """
        lsd_path = cls._find_lsd()
        if lsd_path is None:
            return None

        try:
            # LSD has no --version: it prints its banner and exits non-zero, so the
            # return code is ignored and the banner is parsed.
            from ailsa.record.env import parse_lsd_banner

            with tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [str(lsd_path), "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    stdin=subprocess.DEVNULL,
                    cwd=tmp,
                )
            version = parse_lsd_banner(result.stdout + "\n" + result.stderr)
            if version:
                return version
        except Exception:
            pass

        return "unknown"
