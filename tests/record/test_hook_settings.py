"""Hook settings generator and reversible installer (tmp files only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ailsa.record.hooksettings import HOOK_EVENTS, build_settings, install, is_ours, uninstall

PY = "/abs/python"
OTHER = {"type": "command", "command": "/usr/bin/notify", "args": ["--done"]}


def count_ours(data: dict) -> int:
    return sum(
        1
        for groups in data.get("hooks", {}).values()
        for g in groups
        for h in g["hooks"]
        if is_ours(h)
    )


def test_build_settings_shape():
    s = build_settings(PY)
    assert set(s["hooks"]) == {e for e, _, _ in HOOK_EVENTS}
    assert len(s["hooks"]) == 13
    ptu = s["hooks"]["PostToolUse"][0]
    assert ptu["matcher"] == "Bash|Agent|SendMessage|SubagentHandback"
    assert ptu["hooks"][0]["async"] is True
    assert s["hooks"]["SessionEnd"][0]["hooks"][0]["timeout"] == 30
    h = s["hooks"]["Stop"][0]["hooks"][0]
    assert h == {
        "type": "command",
        "command": PY,
        "args": ["-m", "ailsa.record.hook"],
        "timeout": 10,
    }
    assert "autoMemoryEnabled" not in s
    assert build_settings(PY, auto_memory=False)["autoMemoryEnabled"] is False


def test_is_ours():
    assert is_ours({"command": PY, "args": ["-m", "ailsa.record.hook"]})
    assert is_ours({"command": "ailsa-hook"})
    assert not is_ours(OTHER)
    assert not is_ours("nope")


def test_install_missing_file_creates(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    assert install(path, PY) is None
    data = json.loads(path.read_text())
    assert count_ours(data) == 13 and set(data) == {"hooks"}


def test_install_merges_and_backs_up(tmp_path):
    path = tmp_path / "settings.json"
    start = {
        "model": "x",
        "hooks": {"Stop": [{"hooks": [OTHER]}], "Custom": [{"hooks": [OTHER]}]},
    }
    path.write_text(json.dumps(start))
    backup = install(path, PY)
    assert backup is not None and ".ailsa-backup-" in backup.name
    assert json.loads(backup.read_text()) == start
    data = json.loads(path.read_text())
    assert data["model"] == "x" and count_ours(data) == 13
    assert data["hooks"]["Stop"][0] == {"hooks": [OTHER]}
    assert data["hooks"]["Custom"] == [{"hooks": [OTHER]}]


def test_install_idempotent(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [OTHER]}]}}))
    install(path, PY)
    before = path.read_text()
    backups = sorted(tmp_path.glob("*.ailsa-backup-*"))
    assert install(path, PY) is None
    assert path.read_text() == before
    assert count_ours(json.loads(before)) == 13
    assert sorted(tmp_path.glob("*.ailsa-backup-*")) == backups


def test_install_new_python_replaces_ours(tmp_path):
    path = tmp_path / "settings.json"
    install(path, PY)
    install(path, "/other/python")
    data = json.loads(path.read_text())
    assert count_ours(data) == 13
    assert "/abs/python" not in path.read_text()


def test_uninstall_removes_only_ours(tmp_path):
    path = tmp_path / "settings.json"
    start = {
        "hooks": {
            "Stop": [{"hooks": [OTHER]}],
            "Custom": [{"matcher": "m", "hooks": [OTHER]}],
        },
        "other": [1, 2],
    }
    path.write_text(json.dumps(start))
    install(path, PY)
    assert uninstall(path) == 13
    assert json.loads(path.read_text()) == start
    assert uninstall(path) == 0


def test_uninstall_drops_empty_hooks_and_missing_file(tmp_path):
    path = tmp_path / "settings.json"
    install(path, PY)
    assert uninstall(path) == 13
    assert json.loads(path.read_text()) == {}
    assert uninstall(tmp_path / "absent.json") == 0


def test_mixed_group_keeps_foreign_handler(tmp_path):
    path = tmp_path / "settings.json"
    ours = {"type": "command", "command": PY, "args": ["-m", "ailsa.record.hook"]}
    path.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [OTHER, ours]}]}}))
    assert uninstall(path) == 1
    assert json.loads(path.read_text())["hooks"]["Stop"] == [{"hooks": [OTHER]}]


@pytest.mark.parametrize("text", ["{bad", "[1]"])
def test_install_refuses_invalid(tmp_path: Path, text: str):
    path = tmp_path / "settings.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        install(path, PY)
    assert path.read_text() == text
    assert not list(tmp_path.glob("*.ailsa-backup-*"))
