"""Startup cost and lazy-import guards (REC-04)."""

from __future__ import annotations

import json
import subprocess
import sys
import time

import click

HEAVY = ["rdkit", "scipy", "nmrglue", "numpy"]

_PROBE = (
    "import sys, json\n"
    "{body}\n"
    "print(json.dumps(sorted(m for m in {heavy!r} if m in sys.modules)))\n"
)


def _heavy_after(body: str) -> list[str]:
    code = _PROBE.format(body=body, heavy=HEAVY)
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_import_ailsa_is_light() -> None:
    assert _heavy_after("import ailsa") == []


def test_all_public_names_resolve() -> None:
    import ailsa

    for name in ailsa.__all__:
        assert getattr(ailsa, name) is not None, name


def test_top_level_imports_no_circularity() -> None:
    code = (
        "from ailsa import BrukerReader, DEPTGuidedPicker\n"
        "import ailsa.lsd\n"
        "print('ok')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    assert proc.stdout.strip() == "ok"


def test_version_single_source() -> None:
    import ailsa
    from ailsa import _version

    assert ailsa.__version__ == "0.1.0"
    assert ailsa.__version__ == _version.__version__


def test_run_help_is_light() -> None:
    body = (
        "from ailsa.cli import cli\n"
        "cli.main(['run', '--help'], standalone_mode=False)"
    )
    assert _heavy_after(body) == []


def test_version_is_fast() -> None:
    times = []
    out = ""
    for _ in range(3):
        start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, "-m", "ailsa.cli", "--version"],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        times.append(time.perf_counter() - start)
        out = proc.stdout
    assert "0.1.0" in out
    assert min(times) < 1.0, times


def test_registry_entries_resolve() -> None:
    from ailsa.cli.main import _COMMANDS, cli

    expected = {
        "analyze", "case", "database", "dereplicate", "detect", "fetch",
        "fragment", "identify", "jcamp", "lsd", "nus", "pick", "predict",
        "pylsd", "read", "skill", "visualize", "run", "spectra",
        "peaks", "model",
    }  # fmt: skip
    assert expected <= set(cli.commands)
    assert expected <= set(_COMMANDS)
    ctx = click.Context(cli)
    for name in _COMMANDS:
        assert isinstance(cli.get_command(ctx, name), click.Command), name
    assert cli.get_command(ctx, "no-such-command") is None


def test_help_lists_new_groups() -> None:
    from click.testing import CliRunner

    from ailsa.cli import cli

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Computer-Assisted Structure Elucidation" in result.output
    for word in ("run", "spectra", "peaks", "model"):
        assert word in result.output
