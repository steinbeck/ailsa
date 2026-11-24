"""`ailsa run hooks show|install|uninstall`; only temporary settings files are touched."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner

from ailsa.cli.run import run
from ailsa.record.hooksettings import HOOK_EVENTS


def _invoke(*args: str) -> Any:
    return CliRunner().invoke(run, ["hooks", *args])


def test_show_prints_the_settings_block() -> None:
    res = _invoke("show")
    assert res.exit_code == 0, res.output
    data = json.loads(res.stdout)
    assert set(data["hooks"]) == {name for name, _, _ in HOOK_EVENTS}


def test_install_twice_and_uninstall(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    other = {"type": "command", "command": "/usr/bin/true"}
    target.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [other]}]}, "theme": "dark"}))
    first = _invoke("install", "--settings", str(target))
    assert first.exit_code == 0, first.output
    assert "backup:" in first.stdout and f"installed {len(HOOK_EVENTS)}" in first.stdout
    assert len(list(tmp_path.glob("settings.json.ailsa-backup-*"))) == 1
    after = target.read_text()
    second = _invoke("install", "--settings", str(target))
    assert "already installed" in second.stdout
    assert target.read_text() == after
    assert len(list(tmp_path.glob("settings.json.ailsa-backup-*"))) == 1
    gone = _invoke("uninstall", "--settings", str(target))
    assert gone.exit_code == 0
    assert f"removed {len(HOOK_EVENTS)}" in gone.stdout
    data = json.loads(target.read_text())
    assert data["theme"] == "dark"
    assert data["hooks"] == {"Stop": [{"hooks": [other]}]}


def test_install_creates_a_missing_file(tmp_path: Path) -> None:
    target = tmp_path / "new" / "settings.json"
    res = _invoke("install", "--settings", str(target))
    assert res.exit_code == 0, res.output
    assert "backup:" not in res.stdout
    assert json.loads(target.read_text())["hooks"]


def test_uninstall_of_a_missing_file_is_harmless(tmp_path: Path) -> None:
    res = _invoke("uninstall", "--settings", str(tmp_path / "nope.json"))
    assert res.exit_code == 0 and "removed 0" in res.stdout


def test_broken_settings_file_fails_cleanly(tmp_path: Path) -> None:
    target = tmp_path / "settings.json"
    target.write_text("{not json")
    res = _invoke("install", "--settings", str(target))
    assert res.exit_code == 1 and "not valid JSON" in res.stderr
    assert target.read_text() == "{not json"


def test_default_target_is_the_user_file_in_help() -> None:
    for command in ("install", "uninstall"):
        res = _invoke(command, "--help")
        assert "~/.claude/settings.json" in res.output
