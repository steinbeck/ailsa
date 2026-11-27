"""The old web view stays removed.

It was retired together with the frontier skill's wiring to the run record;
this test keeps it from coming back.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from ailsa.cli.main import _COMMANDS, cli

ROOT = Path(__file__).resolve().parent.parent


def test_no_tracked_webview_files() -> None:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "src/ailsa/webview"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        pytest.skip("git not available")
    if proc.returncode != 0:
        pytest.skip("not a git work tree")
    assert proc.stdout.strip() == ""


def test_no_webview_python_modules() -> None:
    folder = ROOT / "src" / "ailsa" / "webview"
    if folder.exists():
        assert list(folder.rglob("*.py")) == []
    assert not (ROOT / "src" / "ailsa" / "cli" / "webview.py").exists()


def test_webview_command_unknown() -> None:
    assert "webview" not in _COMMANDS
    result = CliRunner().invoke(cli, ["webview", "--help"])
    assert result.exit_code != 0
    assert "No such command" in result.output


def test_no_webview_dependencies() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for word in ("webview", "fastapi", "uvicorn", "httpx"):
        assert word not in text, word


def test_record_excludes_no_webview() -> None:
    from ailsa.record.toolrec import EXCLUDED

    assert "webview" not in EXCLUDED


def test_no_webview_in_skills_or_runner() -> None:
    files = [p for p in (ROOT / "src" / "ailsa" / "skills").rglob("*") if p.is_file()]
    files.append(ROOT / "tests" / "case-benchmark" / "blind_case_run.sh")
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert "webview" not in text.lower(), str(path)
