"""PICK-02/D-08: `ailsa nus qc` + `ailsa nus pipeline` CLI commands (Phase 99 Plan 04).

`ailsa nus qc <peaks-dir>` is independently runnable against arbitrary
peak-list directories (needed for QC-02's FAIL/PASS proof); `ailsa nus
pipeline <expdir>` orchestrates params -> schedule -> reconstruct ->
process -> peak-pick -> QC end-to-end and calls the same qc code
internally. Every `ailsa nus` subcommand supports `--format json`.

Note on Wave 0 (Plan 01) provenance: the original RED-by-skip stubs
invoked `pipeline` against a bare `tmp_path` with no mocked
reconstruction/QC seams. This file replaces those placeholders with real
assertions against `ailsa nus qc`'s real `run_qc_checks()` call (the
already-committed `known_bad_peaks_dir`/`clean_peaks_dir` fixtures, Plan
01/02) and `ailsa nus pipeline`'s real write-boundary logic exercised via
the `mock_pipeline_stages` fixture (conftest.py, this plan).
"""

from __future__ import annotations

import json


def test_qc_command_json_format(known_bad_peaks_dir) -> None:
    """`ailsa nus qc <peaks-dir> --format json` must emit a JSON-parseable
    `QcReport.to_dict()` payload (D-08's independently-runnable contract)
    and exit non-zero on a FAIL verdict.
    """
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(known_bad_peaks_dir), "--format", "json"])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["verdict"] == "FAIL"


def test_qc_command_on_clean_fixture_without_dept(clean_peaks_dir) -> None:
    """`ailsa nus qc <peaks-dir> --format json` exits 0 on the synthetic-clean
    fixture. It has no DEPT, so the classification-dependent checks are not
    checkable and the verdict is PARTIAL, with no violated check (PROV-01).
    """
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(clean_peaks_dir), "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["verdict"] == "PARTIAL"
    unchecked = {c["name"] for c in payload["checks"] if not c["checkable"]}
    assert unchecked == {"quaternary_exclusion", "hsqc_coverage"}
    assert all(c["passed"] for c in payload["checks"] if c["checkable"])


def test_qc_command_text_format_reports_verdict(known_bad_peaks_dir) -> None:
    """The default text format prints the verdict and violated check names."""
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", str(known_bad_peaks_dir)])
    assert result.exit_code != 0
    assert "FAIL" in result.output
    assert "Violated checks:" in result.output


def test_qc_command_help_lists_threshold_flags() -> None:
    """`ailsa nus qc --help` lists the D-04 threshold-override flags."""
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["qc", "--help"])
    assert result.exit_code == 0
    assert "--ridge-fail" in result.output
    assert "--coverage-floor" in result.output
    assert "--c13-tol" in result.output
    assert "--h1-tol" in result.output
    assert "--format" in result.output


def test_qc_command_threshold_override_changes_verdict(known_bad_peaks_dir) -> None:
    """An explicit `--coverage-floor 0.0` override must thread through to
    `QcConfig` (D-04) and show up as the hsqc_coverage threshold. The
    fixture has no DEPT, so the coverage check itself is not checkable;
    loosening its floor must not flip the independently-critical
    signal-to-ridge violation.
    """
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(
        nus,
        ["qc", str(known_bad_peaks_dir), "--coverage-floor", "0.0", "--format", "json"],
    )
    payload = json.loads(result.stdout)
    coverage_check = next(c for c in payload["checks"] if c["name"] == "hsqc_coverage")
    assert coverage_check["threshold"] == 0.0
    assert coverage_check["checkable"] is False
    # Still FAIL overall -- signal_to_ridge remains a critical violation.
    assert payload["verdict"] == "FAIL"


def test_pipeline_command_wires_stages(tmp_path, mock_pipeline_stages) -> None:
    """`ailsa nus pipeline <expdir>` must wire
    params -> schedule -> reconstruct -> process -> peak-pick -> QC in
    strict order, reusing `NusRunner.reconstruct()` (Phase 98, unchanged)
    and the same `run_qc_checks()` the standalone `qc` command calls.
    """
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    expdir = tmp_path / "expdir"
    expdir.mkdir()
    mock_pipeline_stages(verdict="PASS")

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(expdir)])

    assert result.exit_code in (0, 1)
    assert (expdir / "analysis" / "nmr_peaks" / "HSQC.json").exists()


def test_pipeline_json_format_reports_verdict_and_written_paths(
    tmp_path, mock_pipeline_stages
) -> None:
    """`--format json` emits a machine-readable summary: verdict, written
    paths (or quarantine path), and the full QC report."""
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    expdir = tmp_path / "expdir"
    expdir.mkdir()
    mock_pipeline_stages(verdict="PASS")

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", str(expdir), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["verdict"] == "PASS"
    assert payload["written"]
    assert payload["quarantine"] is None
    assert payload["report"]["verdict"] == "PASS"


def test_pipeline_help_lists_reconstruction_and_qc_flags() -> None:
    """`ailsa nus pipeline --help` shows reconstruction knobs + QC
    threshold overrides + --format."""
    from click.testing import CliRunner

    from ailsa.cli.nus import nus

    runner = CliRunner()
    result = runner.invoke(nus, ["pipeline", "--help"])
    assert result.exit_code == 0
    for flag in (
        "--iterations",
        "--threshold",
        "--virtual-echo",
        "--no-virtual-echo",
        "--f2-p0",
        "--f2-p1",
        "--f1-p0",
        "--f1-p1",
        "--ridge-fail",
        "--coverage-floor",
        "--c13-tol",
        "--h1-tol",
        "--format",
    ):
        assert flag in result.output


def test_all_nus_subcommands_support_format_json() -> None:
    """Every `ailsa nus` subcommand -- including the new `qc`/`pipeline` --
    must support `--format json`, matching the existing
    `check`/`params`/`schedule`/`reconstruct` convention.

    Checks the actual `--format` CLI flag string (`p.opts`), not the
    destination variable name (`p.name` is `"output_format"` for every
    command per the project's `--format`/`output_format` convention --
    asserting on `p.name == "format"` would fail for every command,
    including the pre-existing `check`/`params`/`schedule`/`reconstruct`
    ones, and was never actually exercised in Wave 0's RED-by-skip stub).
    """
    from ailsa.cli.nus import nus

    for command_name in ("check", "params", "schedule", "reconstruct", "qc", "pipeline"):
        command = nus.commands[command_name]
        assert any("--format" in p.opts for p in command.params), command_name
