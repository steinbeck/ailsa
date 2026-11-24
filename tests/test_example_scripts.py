"""Light checks for the public example-dataset scripts (BMRB bmse000667; data not in the repo)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FOLDER = REPO / "scripts" / "example-terpineol"
FORBIDDEN = {"fid", "ser", "acqus", "1r", "2rr", "procs"}


@pytest.mark.parametrize("script", ["process_fid.py", "download_bmrb.py"])
def test_help_exits_zero(script: str) -> None:
    result = subprocess.run(
        [sys.executable, str(FOLDER / script), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_readme_credit_and_env_var() -> None:
    text = (FOLDER / "README.md").read_text(encoding="utf-8")
    assert "bmse000667" in text
    assert "AILSA_EXAMPLE_TERPINEOL" in text
    assert "acknowledg" in text.lower()


def test_no_nmr_data_tracked() -> None:
    out = subprocess.run(
        ["git", "ls-files", "scripts/example-terpineol"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    ).stdout.split()
    if not out:
        pytest.skip("not a git checkout")
    names = {Path(p).name for p in out}
    assert not names & FORBIDDEN


def _load_downloader():
    spec = importlib.util.spec_from_file_location("download_bmrb", FOLDER / "download_bmrb.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zip_slip_guard_rejects_traversal(tmp_path: Path) -> None:
    mod = _load_downloader()
    for bad in ("../evil", "/etc/passwd", "a/../../evil"):
        with pytest.raises(ValueError):
            mod.safe_join(tmp_path, bad)
    ok = mod.safe_join(tmp_path, "1H/fid")
    assert tmp_path.resolve() in ok.parents


def test_downloader_refuses_destination_inside_repo(tmp_path: Path) -> None:
    mod = _load_downloader()
    assert mod.inside_repo(REPO / "somewhere") is True
    assert mod.inside_repo(tmp_path) is False
