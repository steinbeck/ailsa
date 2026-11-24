"""Shared fixtures for run-record tests."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from ailsa.record.workspace import create_run_dir


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ws = tmp_path / "ws"
    monkeypatch.setenv("AILSA_WORKSPACE", str(ws))
    monkeypatch.setenv("AILSA_CONFIG", str(tmp_path / "config.json"))
    for name in ("AILSA_RUN_DIR", "AILSA_REQUIRE_RUN", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)
    return ws


def make_shim(bin_dir: Path, name: str, script_text: str) -> Path:
    bin_dir.mkdir(parents=True, exist_ok=True)
    path = bin_dir / name
    path.write_text(script_text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


@pytest.fixture
def shim_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return bin_dir


@pytest.fixture
def new_run(workspace: Path) -> tuple[str, Path]:
    return create_run_dir(workspace, "fixture")
