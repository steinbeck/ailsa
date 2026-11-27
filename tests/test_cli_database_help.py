"""The database download help credits the COCONUT shift source."""

from __future__ import annotations

from click.testing import CliRunner

from ailsa.cli import cli


def _help() -> str:
    result = CliRunner().invoke(cli, ["database", "download", "--help"])
    assert result.exit_code == 0
    return result.output


def test_download_help_carries_credit() -> None:
    out = _help()
    assert "zenodo.6561449" in out
    assert "predicted" in out
    assert "CC BY 4.0" in out
